# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+

"""Ansible filter plugins for computing NetBird configuration diffs."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type


def _extract_peer_id(peer):
    """Extract peer ID from either a dict or plain string."""
    if isinstance(peer, dict):
        return peer.get('id', '')
    return peer or ''


def _extract_ids(items):
    """Extract IDs from a list that may contain dicts or plain strings."""
    if not items:
        return []
    return [item['id'] if isinstance(item, dict) else item for item in items]


def _classify(desired_list, current_map, protected=None):
    """Classify resources into new/existing/remove/orphaned.

    Returns (present_names, remove_names, orphaned_names) where
    present_names includes both new and existing.
    """
    protected = protected or []
    present_names = []
    remove_names = []

    for item in desired_list:
        name = item.get('name', '')
        state = item.get('state', 'present')
        if state == 'absent':
            if name in current_map:
                remove_names.append(name)
        else:
            present_names.append(name)

    current_names = set(current_map.keys())
    desired_names = set(item.get('name', '') for item in desired_list)
    orphaned = sorted(current_names - desired_names - set(protected))

    return present_names, remove_names, orphaned


def _resolve_peer_name(peer_value, peer_ids, peer_id_name):
    """Resolve a peer field value (UUID or name) to a human-readable name.

    The API may store peer as a UUID or as a name (legacy data created
    before name-to-ID resolution was added). This handles both cases.
    """
    if not peer_value:
        return ''
    peer_id = _extract_peer_id(peer_value)
    # UUID → name via reverse map
    name = peer_id_name.get(peer_id, '')
    if name:
        return name
    # Already a name (exists as a key in name→ID map)
    if peer_id in peer_ids:
        return peer_id
    # Unknown — return as-is
    return peer_id


def _compare_network(current, desired, peer_ids, peer_id_name):
    """Compare a single network (including routers) and return list of change descriptions."""
    diffs = []

    # Description
    cur_desc = current.get('description') or ''
    des_desc = desired.get('description') or ''
    if cur_desc != des_desc:
        diffs.append('description: "{0}" \u2192 "{1}"'.format(cur_desc, des_desc))

    # Routers — match by resolved peer name (handles both UUID and name in API)
    current_routers = current.get('routers') or []
    desired_routers = desired.get('routers') or []

    cr_by_label = {}
    for cr in current_routers:
        label = _resolve_peer_name(cr.get('peer'), peer_ids, peer_id_name)
        if not label and cr.get('peer_groups'):
            label = 'peer_groups'
        cr_by_label[label] = cr

    matched = set()
    for dr in desired_routers:
        label = dr.get('peer') or ''
        if not label and dr.get('peer_groups'):
            label = 'peer_groups'

        if label in cr_by_label:
            cr = cr_by_label[label]
            matched.add(label)

            cr_metric = int(cr.get('metric') or 9999)
            dr_metric = int(dr.get('metric') or 9999)
            if cr_metric != dr_metric:
                diffs.append('router[{0}]: metric {1} \u2192 {2}'.format(label, cr_metric, dr_metric))

            cr_masq = bool(cr.get('masquerade', False))
            dr_masq = bool(dr.get('masquerade', False))
            if cr_masq != dr_masq:
                diffs.append('router[{0}]: masquerade {1} \u2192 {2}'.format(label, cr_masq, dr_masq))

            cr_enabled = bool(cr.get('enabled', True))
            dr_enabled = bool(dr.get('enabled', True))
            if cr_enabled != dr_enabled:
                diffs.append('router[{0}]: enabled {1} \u2192 {2}'.format(label, cr_enabled, dr_enabled))
        else:
            diffs.append('router[{0}]: + NEW'.format(label))

    for label in cr_by_label:
        if label not in matched:
            diffs.append('router[{0}]: - REMOVED'.format(label))

    return diffs


def _compare_dns(current, desired, group_ids):
    """Compare a single DNS nameserver group and return list of change descriptions."""
    diffs = []

    if (current.get('description') or '') != (desired.get('description') or ''):
        diffs.append('description changed')

    if bool(current.get('enabled', True)) != bool(desired.get('enabled', True)):
        diffs.append('enabled: {0} \u2192 {1}'.format(current.get('enabled', True), desired.get('enabled', True)))

    if bool(current.get('primary', False)) != bool(desired.get('primary', False)):
        diffs.append('primary: {0} \u2192 {1}'.format(current.get('primary', False), desired.get('primary', False)))

    cur_domains = sorted(current.get('domains') or [])
    des_domains = sorted(desired.get('domains') or [])
    if cur_domains != des_domains:
        diffs.append('domains changed')

    cur_ns = sorted(ns.get('ip', '') for ns in (current.get('nameservers') or []))
    des_ns = sorted(ns.get('ip', '') for ns in (desired.get('nameservers') or []))
    if cur_ns != des_ns:
        diffs.append('nameservers changed')

    cur_groups = sorted(_extract_ids(current.get('groups') or []))
    des_groups = sorted(group_ids.get(g, g) for g in (desired.get('groups') or []))
    if cur_groups != des_groups:
        diffs.append('groups changed')

    return diffs


def _compare_policy(current, desired):
    """Compare a single policy and return list of change descriptions."""
    diffs = []

    if (current.get('description') or '') != (desired.get('description') or ''):
        diffs.append('description changed')

    if bool(current.get('enabled', True)) != bool(desired.get('enabled', True)):
        diffs.append('enabled: {0} \u2192 {1}'.format(current.get('enabled', True), desired.get('enabled', True)))

    cur_rules = len(current.get('rules') or [])
    des_rules = len(desired.get('rules') or [])
    if cur_rules != des_rules:
        diffs.append('rules: {0} \u2192 {1}'.format(cur_rules, des_rules))

    return diffs


def netbird_diff(desired_list, current_map, resource_type='simple', **kwargs):
    """Compute diff between desired config and current API state.

    Args:
        desired_list: list of desired resource dicts from YAML config
        current_map: dict mapping resource names to current API state
        resource_type: 'network', 'dns', 'policy', or 'simple'
        **kwargs: peer_ids, peer_id_name, group_ids, protected

    Returns:
        dict with: new, changed (dict of name: [changes]), unchanged, remove, orphaned
    """
    if not isinstance(desired_list, list):
        desired_list = []
    if not isinstance(current_map, dict):
        current_map = {}

    peer_ids = kwargs.get('peer_ids') or {}
    peer_id_name = kwargs.get('peer_id_name') or {}
    group_ids = kwargs.get('group_ids') or {}
    protected = kwargs.get('protected') or []

    present_names, remove_names, orphaned = _classify(desired_list, current_map, protected)

    new_names = []
    changed = {}
    unchanged = []

    desired_by_name = {item['name']: item for item in desired_list if 'name' in item}

    for name in present_names:
        if name not in current_map:
            new_names.append(name)
            continue

        current = current_map[name]
        desired = desired_by_name.get(name, {})

        if resource_type == 'network':
            diffs = _compare_network(current, desired, peer_ids, peer_id_name)
        elif resource_type == 'dns':
            diffs = _compare_dns(current, desired, group_ids)
        elif resource_type == 'policy':
            diffs = _compare_policy(current, desired)
        else:
            diffs = []

        if diffs:
            changed[name] = diffs
        else:
            unchanged.append(name)

    return {
        'new': new_names,
        'changed': changed,
        'unchanged': unchanged,
        'remove': remove_names,
        'orphaned': orphaned,
    }


def netbird_format_diff(diff_result, title, pad=60):
    """Format a diff result dict into display lines.

    Args:
        diff_result: output from netbird_diff filter
        title: section title (e.g. "Networks", "Groups")
        pad: total width of the title bar

    Returns:
        list of formatted strings
    """
    if not isinstance(diff_result, dict):
        return ['── {0} ──'.format(title), '  (error: invalid diff data)']

    separator = '── {0} '.format(title).ljust(pad, '─')
    lines = [separator]

    new = diff_result.get('new', [])
    changed = diff_result.get('changed', {})
    unchanged = diff_result.get('unchanged', [])
    remove = diff_result.get('remove', [])
    orphaned = diff_result.get('orphaned', [])

    has_content = any([new, changed, unchanged, remove, orphaned])

    if not has_content:
        lines.append('  (not configured \u2014 skipped)')
        return lines

    if not any([new, changed, remove, orphaned]) and unchanged:
        # Only unchanged resources
        for name in unchanged:
            lines.append('  = OK:      "{0}"'.format(name))
        return lines

    for name in new:
        lines.append('  + ADD:     "{0}"'.format(name))
    for name in remove:
        lines.append('  - REMOVE:  "{0}"'.format(name))
    for name in orphaned:
        lines.append('  - ORPHAN:  "{0}" (not in config)'.format(name))
    for name, changes in changed.items():
        lines.append('  ~ CHANGED: "{0}"'.format(name))
        for change in changes:
            lines.append('      {0}'.format(change))
    for name in unchanged:
        lines.append('  = OK:      "{0}"'.format(name))

    return lines


class FilterModule(object):
    """NetBird diff filter plugins."""

    def filters(self):
        return {
            'netbird_diff': netbird_diff,
            'netbird_format_diff': netbird_format_diff,
        }

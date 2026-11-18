# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+

"""Ansible filter plugins for computing NetBird configuration diffs."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.common.validation import check_type_bool as _check_type_bool

from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    extract_ids as _extract_ids,
)


_SERVICE_SKIP = frozenset((
    'id', 'meta', 'proxy_cluster', 'port_auto_assigned', 'terminated', 'state'
))

_AN_SKIP = frozenset(('id', 'created_at', 'updated_at', 'state'))
_AN_PROVIDER_SKIP = frozenset(('id', 'api_key', 'created_at', 'updated_at', 'state'))
_TARGET_OPTIONS = ('direct_upstream', 'skip_tls_verify', 'path_rewrite',
                   'proxy_protocol')
_TARGET_BOOL_OPTIONS = frozenset(('direct_upstream', 'skip_tls_verify',
                                  'proxy_protocol'))
# What netbird_service sends for a target option the config leaves out.
_MODULE_TARGET_DEFAULTS = {'direct_upstream': True, 'skip_tls_verify': False,
                           'proxy_protocol': False, 'enabled': True}


def _normalize(value):
    """Recursively normalize a value for stable comparison.

    - dicts: sorted by key, None values dropped
    - lists of dicts: sorted by JSON repr (order-independent)
    - lists of scalars: sorted
    - strings/bools/ints: returned as-is
    """
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items())
                if v is not None}
    if isinstance(value, list):
        normalized = [_normalize(v) for v in value]
        try:
            return sorted(normalized, key=repr)
        except TypeError:
            return normalized
    return value


def _deep_diff(current, desired, path=''):
    """Recursively compare two normalized structures.

    Returns a list of human-readable change descriptions.
    """
    diffs = []
    if isinstance(desired, dict) and isinstance(current, dict):
        all_keys = sorted(set(list(current.keys()) + list(desired.keys())))
        for key in all_keys:
            sub = '{0}.{1}'.format(path, key) if path else key
            if key not in current:
                diffs.append('{0}: + added'.format(sub))
            elif key not in desired:
                diffs.append('{0}: - removed'.format(sub))
            else:
                diffs.extend(
                    _deep_diff(current[key], desired[key], sub))
    elif isinstance(desired, list) and isinstance(current, list):
        if len(current) != len(desired):
            diffs.append('{0}: {1} \u2192 {2} items'.format(
                path or 'list', len(current), len(desired)))
        elif current != desired:
            diffs.append('{0}: changed'.format(path or 'list'))
    elif current != desired:
        diffs.append('{0}: {1} \u2192 {2}'.format(
            path or 'value', current, desired))
    return diffs


def _extract_peer_id(peer):
    """Extract peer ID from either a dict or plain string."""
    if isinstance(peer, dict):
        return peer.get('id', '')
    return peer or ''


def _effective_name(item):
    """The name the API will have stored for this config entry.

    A DNS zone's name follows its domain when omitted, so an entry may declare
    a domain alone. Reading ``name`` directly yields '' for those, which
    reports the entry as a new zone called '' and the real zone as orphaned.

    Falling back to ``domain`` is inert for every other resource type here --
    networks, policies, groups, setup keys and posture checks have no ``domain``
    key, and a nameserver group's is ``domains``, plural.
    """
    name = item.get('name') or ''
    if name:
        return name
    return item.get('domain') or ''


def _item_key(item, key_field=None):
    """Return the lookup key for a config item.

    When *key_field* is given (e.g. ``'domain'`` for services), use that
    field directly.  Otherwise fall back to :func:`_effective_name`.
    """
    if key_field:
        return item.get(key_field) or _effective_name(item)
    return _effective_name(item)


def _classify(desired_list, current_map, protected=None,
              key_field=None):
    """Classify resources into new/existing/remove/orphaned.

    Returns (present_names, remove_names, orphaned_names) where
    present_names includes both new and existing.
    """
    protected = protected or []
    present_names = []
    remove_names = []

    for item in desired_list:
        name = _item_key(item, key_field)
        state = item.get('state', 'present')
        if state == 'absent':
            if name in current_map:
                remove_names.append(name)
        else:
            present_names.append(name)

    current_names = set(current_map.keys())
    desired_names = set(
        _item_key(item, key_field) for item in desired_list)
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


def _flatten_target(target):
    """Flatten a target's nested ``options`` dict to top-level keys.

    The API returns targets with ``options: {direct_upstream: true, ...}``
    while the export template (and the module's input schema) writes these
    as top-level keys.  Normalizing to the flat shape lets the comparison
    work on either representation.

    Missing boolean options are filled in so both sides say what is really
    meant. An API target (one with ``options``; ``_compare_service`` gives
    every API target one) omits a boolean when it is false. A config target
    (``netbird_service`` input, which has no ``options`` key) gets the module's
    defaults for absent keys, because those are what an apply sends: a config
    that leaves out ``direct_upstream`` applies it as true, so the preview has
    to show that change rather than skip the key. The same goes for
    ``enabled``: left out, the module applies it as true, which re-enables a
    disabled target. An explicit null is left as is -- the module rejects it
    -- so it reads as a change.
    """
    flat = {k: v for k, v in target.items() if k != 'options'}
    if 'options' in target:
        options = target.get('options')
        if not isinstance(options, dict):
            options = {}
        for key in _TARGET_OPTIONS:
            if options.get(key) is not None:
                flat.setdefault(key, options[key])
            elif key in _TARGET_BOOL_OPTIONS:
                flat.setdefault(key, False)
        # The module reads a target without ``enabled`` as enabled.
        flat.setdefault('enabled', True)
    else:
        for key, default in _MODULE_TARGET_DEFAULTS.items():
            flat.setdefault(key, default)
            # The module's argument parsing converts quoted and numeric
            # booleans ("off", "yes", 1, 0) with this same check; anything it
            # would reject is left as is, so it reads as a change rather than
            # as a valid value.
            if flat[key] is not None and not isinstance(flat[key], bool):
                try:
                    flat[key] = _check_type_bool(flat[key])
                except (TypeError, ValueError):
                    pass
    return flat


def _unsupported_nested_options(target):
    # A presence marker rather than the value: ``options: null`` is rejected
    # by the module too, and a None value would be dropped before comparing.
    flat = {k: v for k, v in target.items() if k != 'options'}
    flat['options (not a netbird_service target option)'] = True
    return flat


def _target_match_key(target):
    """Pair a desired target with its API counterpart.

    The export omits ``path`` when it is ``/``, and the API treats an unset
    path as ``/``, so both normalize to it. A subnet target's host is part of
    its identity (the API returns it as stored), as in ``netbird_service``;
    other types have their host rewritten by the API on read.
    """
    host = target.get('host') if (target.get('target_type') or 'subnet') == 'subnet' else None
    return (target.get('target_id'), host, target.get('port'),
            target.get('path') or '/')


def _take_match(candidates, target):
    """Pop the desired target matching ``target``, same enabled state first.

    A path may hold an enabled target and a disabled standby that share every
    key field; pairing them one-to-one keeps one from hiding the other.
    """
    pool = candidates.get(_target_match_key(target))
    if not pool:
        return None
    enabled = bool(target.get('enabled', True))
    protocol = target.get('protocol') or 'http'
    action = target.get('access_action') or 'inherit'

    # Same enabled state, protocol (module default http) and action first,
    # then the fewest other differences among the fields the config states:
    # standbys sharing a key are told apart by what they are, not by their
    # order in the list. An action only counts where the config states one.
    def rank(t):
        others = sum(1 for k, v in t.items()
                     if k not in ('enabled', 'protocol', 'access_action') and target.get(k) != v)
        return (bool(t.get('enabled', True)) != enabled,
                (t.get('protocol') or 'http') != protocol,
                'access_action' in t and t['access_action'] != action,
                others)
    match = min(pool, key=rank)
    pool.remove(match)
    return match


def _resolve_group_list(names, group_ids):
    """Resolve a list of group names to IDs using group_ids map.

    Values that are already known IDs pass through unchanged.
    """
    if not group_ids:
        return list(names)
    known_ids = set(group_ids.values())
    return [group_ids.get(n, n) if n not in known_ids else n
            for n in names]


def _compare_service(current, desired, group_ids=None):
    """Compare a single service using recursive normalized diff.

    Server-computed fields (id, meta, proxy_cluster, etc.) are excluded.
    Only fields present in the desired config are compared, so omitted
    optional fields do not trigger false positives.

    group_ids resolves exported group names back to IDs before comparison
    (access_groups and auth.bearer_auth.distribution_groups).

    Targets are flattened from the API's nested options shape to match the
    export's flat shape.

    Auth sub-dicts are filtered to only compare declared sub-keys (e.g.
    exported bearer_auth-only config does not report password_auth as
    removed).
    """
    group_ids = group_ids or {}

    # Read every API target as one: older servers leave ``options`` out
    # entirely when no option is set, which would otherwise look like a
    # config target and pick up the module's defaults.
    if isinstance(current.get('targets'), list):
        current = dict(current, targets=[
            dict(t, options=t.get('options') or {}) if isinstance(t, dict) else t
            for t in current['targets']])
    # A config target has no ``options`` (netbird_service rejects the key and
    # takes the options flat). Keep a nested one visible under a name that
    # says so, rather than read it as API data that happens to match.
    if isinstance(desired.get('targets'), list):
        desired = dict(desired, targets=[
            _unsupported_nested_options(t) if isinstance(t, dict) and 'options' in t else t
            for t in desired['targets']])

    cur = {k: _normalize(v) for k, v in current.items()
           if k not in _SERVICE_SKIP and v is not None}
    des = {k: _normalize(v) for k, v in desired.items()
           if k not in _SERVICE_SKIP and v is not None}

    # access_groups: normalize to sorted ID lists
    if 'access_groups' in cur:
        cur['access_groups'] = sorted(
            _extract_ids(current.get('access_groups') or []))
    if 'access_groups' in des:
        des['access_groups'] = sorted(
            _resolve_group_list(desired.get('access_groups') or [], group_ids))

    # targets: flatten nested options to top-level keys, then filter each
    # API target to only the keys its matched desired target declares (the
    # export omits defaults like path='/' and path_rewrite='preserve', and
    # different targets may declare different optional keys). The path is part
    # of the match: path-routed targets usually share one resource and port,
    # and without it they collapse onto a single desired target, so one
    # target's declared keys (path, access_action) leak onto the others.
    if 'targets' in des:
        des_flat = [_flatten_target(t)
                    for t in (desired.get('targets') or [])]
        des_by_key = {}
        for t in des_flat:
            # access_action: null is unset for the module, which then keeps the
            # current action, so it is not a declaration to compare.
            if 'access_action' in t and t['access_action'] is None:
                del t['access_action']
            if 'path' in t:
                t['path'] = t['path'] or '/'
            des_by_key.setdefault(_target_match_key(t), []).append(t)
        des['targets'] = _normalize(des_flat)
        if 'targets' in cur:
            filtered_cur_targets = []
            for t in (current.get('targets') or []):
                flat = _flatten_target(t)
                match = _take_match(des_by_key, flat)
                if match is not None:
                    # A server without per-target actions applies the
                    # service's authentication everywhere, which is what
                    # inherit means.
                    if 'access_action' in match:
                        flat.setdefault('access_action', 'inherit')
                    # The API may leave out a root path the config states.
                    if 'path' in match:
                        flat['path'] = flat.get('path') or '/'
                    flat = {k: v for k, v in flat.items() if k in match}
                filtered_cur_targets.append(flat)
            cur['targets'] = _normalize(filtered_cur_targets)
    elif 'targets' in cur:
        cur['targets'] = _normalize([
            _flatten_target(t) for t in (current.get('targets') or [])])

    # auth: resolve distribution_groups and filter to declared sub-keys
    cur_auth = current.get('auth')
    des_auth = desired.get('auth')
    if isinstance(des_auth, dict) and isinstance(cur_auth, dict):
        filtered_auth_cur = {}
        filtered_auth_des = {}
        for scheme in des_auth:
            if scheme in cur_auth:
                cur_scheme = dict(cur_auth[scheme] or {})
                des_scheme = dict(des_auth[scheme] or {})
                # resolve bearer distribution_groups names → IDs
                if scheme == 'bearer_auth':
                    if 'distribution_groups' in cur_scheme:
                        cur_scheme['distribution_groups'] = sorted(
                            _extract_ids(
                                cur_scheme.get('distribution_groups') or []))
                    if 'distribution_groups' in des_scheme:
                        des_scheme['distribution_groups'] = sorted(
                            _resolve_group_list(
                                des_scheme.get('distribution_groups') or [],
                                group_ids))
                filtered_auth_cur[scheme] = _normalize(cur_scheme)
                filtered_auth_des[scheme] = _normalize(des_scheme)
            else:
                filtered_auth_des[scheme] = _normalize(des_auth[scheme])
        cur['auth'] = filtered_auth_cur
        des['auth'] = filtered_auth_des
    elif 'auth' in des and des_auth is None:
        des.pop('auth', None)

    # compare only keys the desired config declares
    filtered_cur = {k: cur.get(k) for k in des if k in cur}
    return _deep_diff(filtered_cur, des)


def _compare_an_provider(current, desired):
    """Compare an agent-network provider, skipping sealed api_key.

    The API returns ``provider_id`` for the catalog type, but the module
    config uses ``catalog_provider_id``.  Normalize so comparison works.
    """
    cur = {k: _normalize(v) for k, v in current.items() if k not in _AN_PROVIDER_SKIP}
    if 'provider_id' in cur and 'catalog_provider_id' not in cur:
        cur['catalog_provider_id'] = cur.pop('provider_id')
    des = {k: _normalize(v) for k, v in desired.items() if k not in _AN_PROVIDER_SKIP}
    filtered_cur = {k: cur.get(k) for k in des if k in cur}
    return _deep_diff(filtered_cur, des)


def _compare_an_resource(current, desired, group_ids=None,
                         provider_ids=None, guardrail_ids=None):
    """Compare a generic AN resource (policy, guardrail, budget rule)."""
    group_ids = group_ids or {}
    provider_ids = provider_ids or {}
    guardrail_ids = guardrail_ids or {}
    cur = {k: _normalize(v) for k, v in current.items() if k not in _AN_SKIP}
    des = {k: _normalize(v) for k, v in desired.items() if k not in _AN_SKIP}

    for field in ('source_groups', 'target_groups'):
        if field in cur:
            cur[field] = sorted(_extract_ids(current.get(field) or []))
        if field in des:
            des[field] = sorted(
                group_ids.get(g, g) for g in (desired.get(field) or []))

    if 'destination_provider_ids' in cur:
        cur['destination_provider_ids'] = sorted(
            _extract_ids(current.get('destination_provider_ids') or []))
    if 'destination_provider_ids' in des:
        des['destination_provider_ids'] = sorted(
            provider_ids.get(n, n)
            for n in (desired.get('destination_provider_ids') or []))

    if 'guardrail_ids' in cur:
        cur['guardrail_ids'] = sorted(
            _extract_ids(current.get('guardrail_ids') or []))
    if 'guardrail_ids' in des:
        des['guardrail_ids'] = sorted(
            guardrail_ids.get(n, n)
            for n in (desired.get('guardrail_ids') or []))

    filtered_cur = {k: cur.get(k) for k in des if k in cur}
    return _deep_diff(filtered_cur, des)


def netbird_diff(desired_list, current_map, resource_type='simple', **kwargs):
    """Compute diff between desired config and current API state.

    Args:
        desired_list: list of desired resource dicts from YAML config
        current_map: dict mapping resource names to current API state
        resource_type: 'network', 'dns', 'policy', 'service', or 'simple'
        **kwargs: peer_ids, peer_id_name, group_ids, protected, key_field

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
    provider_ids = kwargs.get('provider_ids') or {}
    guardrail_ids = kwargs.get('guardrail_ids') or {}
    protected = kwargs.get('protected') or []
    key_field = kwargs.get('key_field')

    present_names, remove_names, orphaned = _classify(
        desired_list, current_map, protected, key_field=key_field)

    new_names = []
    changed = {}
    unchanged = []

    desired_by_name = {_item_key(item, key_field): item
                       for item in desired_list
                       if _item_key(item, key_field)}

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
        elif resource_type == 'service':
            diffs = _compare_service(current, desired, group_ids)
        elif resource_type == 'an_provider':
            diffs = _compare_an_provider(current, desired)
        elif resource_type in ('an_policy', 'an_guardrail', 'an_budget_rule'):
            diffs = _compare_an_resource(current, desired, group_ids,
                                         provider_ids, guardrail_ids)
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

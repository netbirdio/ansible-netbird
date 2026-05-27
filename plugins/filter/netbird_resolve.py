# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+

"""Ansible filter plugins for resolving NetBird name references to API IDs."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.errors import AnsibleFilterError


def _resolve_names(names, id_map, kind='group', context='', missing=None):
    """Resolve a list of names using an ID map.

    A value passes through unchanged if it is already a known API ID (i.e.
    appears as a value in id_map), which keeps YAML configs that reference
    groups/checks by raw ID working. An unknown value (neither a known name
    nor a known ID) raises AnsibleFilterError so that silent typos don't
    produce half-applied resources.

    When ``missing`` is a list, unresolved names are appended to it as
    ``{'kind', 'name', 'context'}`` dicts instead of raising. This is the
    pre-flight collection mode used by ``netbird_missing_refs`` -- it lets the
    configure role gather every bad reference up front and fail before any API
    mutation, rather than aborting mid-apply on the first one.
    """
    if not names:
        return []
    known_ids = set(id_map.values())
    resolved = []
    for name in names:
        if name in id_map:
            resolved.append(id_map[name])
        elif name in known_ids:
            resolved.append(name)
        elif missing is not None:
            missing.append({'kind': kind, 'name': name, 'context': context})
        else:
            raise AnsibleFilterError(
                "Unknown %s '%s'%s. It is neither a known %s name nor an "
                "existing %s ID. Check for typos or a missing %s definition."
                % (kind, name, (" in " + context) if context else '',
                   kind, kind, kind)
            )
    return resolved


def _resolve_setup_key(sk, group_ids, missing=None):
    """Resolve a single setup key's auto_groups."""
    result = dict(sk)
    if 'auto_groups' in sk:
        result['auto_groups'] = _resolve_names(
            sk['auto_groups'], group_ids,
            kind='group',
            context="setup key '%s' auto_groups" % sk.get('name', '<unnamed>'),
            missing=missing,
        )
    return result


def _resolve_resource_ref(resource, peer_ids, context='', missing=None):
    """Resolve {name, type: peer} to {id, type: peer} using peer_ids map.

    Non-peer resources (host/domain/subnet) pass through unchanged since their
    IDs in exported YAML are already concrete API IDs.

    Raises AnsibleFilterError if a peer name cannot be resolved to an ID, or
    appends to ``missing`` when collecting (see ``_resolve_names``).
    """
    if not isinstance(resource, dict):
        return resource
    if resource.get('type') == 'peer' and 'name' in resource and 'id' not in resource:
        name = resource['name']
        known_ids = set(peer_ids.values())
        if name in peer_ids:
            return {'id': peer_ids[name], 'type': 'peer'}
        if name in known_ids:
            return {'id': name, 'type': 'peer'}
        if missing is not None:
            missing.append({'kind': 'peer', 'name': name, 'context': context})
            return resource
        raise AnsibleFilterError(
            "Unknown peer '%s'%s. It is neither a known peer name nor an "
            "existing peer ID." % (name, (" in " + context) if context else '')
        )
    return resource


def _resolve_peer_id(peer_ref, peer_ids, context='', missing=None):
    """Resolve a single peer name or ID to an ID. Raises on unknown."""
    if peer_ref is None:
        return peer_ref
    known_ids = set(peer_ids.values())
    if peer_ref in peer_ids:
        return peer_ids[peer_ref]
    if peer_ref in known_ids:
        return peer_ref
    if missing is not None:
        missing.append({'kind': 'peer', 'name': peer_ref, 'context': context})
        return peer_ref
    raise AnsibleFilterError(
        "Unknown peer '%s'%s. It is neither a known peer name nor an "
        "existing peer ID." % (peer_ref, (" in " + context) if context else '')
    )


def _resolve_policy(policy, group_ids, posture_check_ids, peer_ids=None, missing=None):
    """Resolve a single policy's group, posture check, and peer references."""
    peer_ids = peer_ids or {}
    result = dict(policy)
    policy_name = policy.get('name', '<unnamed>')

    if 'source_posture_checks' in policy:
        result['source_posture_checks'] = _resolve_names(
            policy.get('source_posture_checks', []),
            posture_check_ids,
            kind='posture_check',
            context="policy '%s' source_posture_checks" % policy_name,
            missing=missing,
        )

    if 'rules' in policy:
        resolved_rules = []
        for rule in policy.get('rules', []):
            rule_name = rule.get('name', '<unnamed>')
            resolved_rule = dict(rule)
            resolved_rule['sources'] = _resolve_names(
                rule.get('sources', []),
                group_ids,
                kind='group',
                context="policy '%s' rule '%s' sources" % (policy_name, rule_name),
                missing=missing,
            )
            resolved_rule['destinations'] = _resolve_names(
                rule.get('destinations', []),
                group_ids,
                kind='group',
                context="policy '%s' rule '%s' destinations" % (policy_name, rule_name),
                missing=missing,
            )
            if rule.get('source_resource') is not None:
                resolved_rule['source_resource'] = _resolve_resource_ref(
                    rule['source_resource'], peer_ids,
                    context="policy '%s' rule '%s' source_resource" % (policy_name, rule_name),
                    missing=missing,
                )
            if rule.get('destination_resource') is not None:
                resolved_rule['destination_resource'] = _resolve_resource_ref(
                    rule['destination_resource'], peer_ids,
                    context="policy '%s' rule '%s' destination_resource" % (policy_name, rule_name),
                    missing=missing,
                )
            resolved_rules.append(resolved_rule)
        result['rules'] = resolved_rules

    return result


def _resolve_network(network, group_ids, peer_ids, missing=None):
    """Resolve a single network's group, peer, and peer_group references."""
    result = dict(network)
    network_name = network.get('name', '<unnamed>')

    if 'resources' in network:
        resolved_resources = []
        for resource in network.get('resources', []):
            resource_name = resource.get('name', resource.get('address', '<unnamed>'))
            resolved = dict(resource)
            if 'groups' in resource:
                resolved['groups'] = _resolve_names(
                    resource.get('groups', []),
                    group_ids,
                    kind='group',
                    context="network '%s' resource '%s' groups" % (network_name, resource_name),
                    missing=missing,
                )
            resolved_resources.append(resolved)
        result['resources'] = resolved_resources

    if 'routers' in network:
        resolved_routers = []
        for router in network.get('routers', []):
            resolved = dict(router)
            if 'peer' in router and router['peer'] is not None:
                resolved['peer'] = _resolve_peer_id(
                    router['peer'], peer_ids,
                    context="network '%s' router peer" % network_name,
                    missing=missing,
                )
            if 'peer_groups' in router:
                resolved['peer_groups'] = _resolve_names(
                    router.get('peer_groups', []),
                    group_ids,
                    kind='group',
                    context="network '%s' router peer_groups" % network_name,
                    missing=missing,
                )
            resolved_routers.append(resolved)
        result['routers'] = resolved_routers

    return result


def _resolve_dns_nameserver_group(ns, group_ids, missing=None):
    """Validate a single DNS nameserver group's group references."""
    result = dict(ns)
    if 'groups' in ns:
        result['groups'] = _resolve_names(
            ns.get('groups', []),
            group_ids,
            kind='group',
            context="DNS nameserver group '%s' groups" % ns.get('name', '<unnamed>'),
            missing=missing,
        )
    return result


def _resolve_dns_zone(zone, group_ids, missing=None):
    """Validate a single DNS zone's distribution_groups references."""
    result = dict(zone)
    if 'distribution_groups' in zone:
        result['distribution_groups'] = _resolve_names(
            zone.get('distribution_groups', []),
            group_ids,
            kind='group',
            context="DNS zone '%s' distribution_groups" % zone.get('name', '<unnamed>'),
            missing=missing,
        )
    return result


def _dispatch_resolve(item, resource_type, group_ids, peer_ids, posture_check_ids,
                      missing=None):
    """Resolve one config item by resource_type, returning the resolved dict.

    Shared by ``netbird_resolve_ids`` (raise mode) and ``netbird_missing_refs``
    (collect mode, via the ``missing`` accumulator). Unknown resource types
    pass through unchanged.
    """
    if resource_type == 'setup_key':
        return _resolve_setup_key(item, group_ids, missing=missing)
    if resource_type == 'policy':
        return _resolve_policy(item, group_ids, posture_check_ids, peer_ids, missing=missing)
    if resource_type == 'network':
        return _resolve_network(item, group_ids, peer_ids, missing=missing)
    if resource_type == 'dns_nameserver_group':
        return _resolve_dns_nameserver_group(item, group_ids, missing=missing)
    if resource_type == 'dns_zone':
        return _resolve_dns_zone(item, group_ids, missing=missing)
    return item


def netbird_resolve_ids(resource_list, resource_type, **kwargs):
    """Resolve human-readable names to API IDs in resource definitions.

    Args:
        resource_list: list of resource dicts from YAML config
        resource_type: 'network', 'policy', or 'setup_key'
        **kwargs: group_ids, peer_ids, posture_check_ids

    Returns:
        list of resource dicts with names replaced by IDs.

    Raises:
        AnsibleFilterError: if any referenced group/posture-check/peer name
            cannot be resolved to an ID. This prevents silent half-applies
            where typos produce policies with dropped references.
    """
    if not isinstance(resource_list, list):
        return []

    group_ids = kwargs.get('group_ids') or {}
    peer_ids = kwargs.get('peer_ids') or {}
    posture_check_ids = kwargs.get('posture_check_ids') or {}

    result = []
    for item in resource_list:
        if not isinstance(item, dict):
            result.append(item)
            continue
        result.append(_dispatch_resolve(
            item, resource_type, group_ids, peer_ids, posture_check_ids))

    return result


def netbird_missing_refs(resource_list, resource_type, **kwargs):
    """Collect every unresolved name reference without raising.

    Pre-flight counterpart of ``netbird_resolve_ids``: instead of aborting on
    the first bad reference, it walks the whole resource list and returns a
    list of ``{'kind', 'name', 'context'}`` dicts for each group/posture-check/
    peer name that is neither a known control-plane resource nor present in the
    supplied id maps. An empty result means the apply is safe to proceed.

    Args:
        resource_list: list of resource dicts from YAML config
        resource_type: 'network', 'policy', 'setup_key', 'dns_nameserver_group',
            or 'dns_zone'
        **kwargs: group_ids, peer_ids, posture_check_ids
    """
    if not isinstance(resource_list, list):
        return []

    group_ids = kwargs.get('group_ids') or {}
    peer_ids = kwargs.get('peer_ids') or {}
    posture_check_ids = kwargs.get('posture_check_ids') or {}

    missing = []
    for item in resource_list:
        if not isinstance(item, dict):
            continue
        _dispatch_resolve(
            item, resource_type, group_ids, peer_ids, posture_check_ids, missing=missing)

    return missing


def netbird_resolve_names(name_list, id_map, kind='group', context=''):
    """Resolve a simple list of names to IDs.

    Used for inline resolution (e.g., DNS zone distribution_groups).

    Raises AnsibleFilterError if a name is neither a known key nor a known
    value (ID) in the map.
    """
    if not isinstance(name_list, list):
        return []
    if not isinstance(id_map, dict):
        return name_list
    return _resolve_names(name_list, id_map, kind=kind, context=context)


def netbird_missing_names(name_list, id_map, kind='group', context=''):
    """Collect unresolved names from a flat list without raising.

    Pre-flight counterpart of ``netbird_resolve_names`` (e.g. for
    ``disabled_management_groups``). Returns a list of
    ``{'kind', 'name', 'context'}`` dicts for names that resolve to neither a
    known key nor a known value (ID) in the map.
    """
    if not isinstance(name_list, list) or not isinstance(id_map, dict):
        return []
    missing = []
    _resolve_names(name_list, id_map, kind=kind, context=context, missing=missing)
    return missing


def _as_port_int(value):
    """Coerce a port value to int, or None if it isn't an integer."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def netbird_value_problems(policies, setup_keys=None):
    """Collect structurally-invalid field VALUES without raising.

    A pre-flight companion to ``netbird_missing_refs`` for the small set of
    value checks that are unambiguous and stable regardless of NetBird API
    version (so they won't false-positive): policy rule ports / port ranges
    must be integers in 1-65535 with start <= end, and setup-key ``expires_in``
    must be a positive integer. Notably this catches inverted port ranges,
    which the NetBird API itself accepts silently.

    CIDR / DNS-record / posture-check value validation is deliberately NOT done
    here: those rules are API-version-specific and reimplementing them risks
    rejecting configs the API would accept. Returns a list of human-readable
    problem strings ([] means OK).
    """
    problems = []
    for pol in policies or []:
        if not isinstance(pol, dict):
            continue
        pname = pol.get('name', '<unnamed>')
        for rule in pol.get('rules') or []:
            if not isinstance(rule, dict):
                continue
            rname = rule.get('name', '<unnamed>')
            for port in rule.get('ports') or []:
                pv = _as_port_int(port)
                if pv is None or not (1 <= pv <= 65535):
                    problems.append(
                        "policy '%s' rule '%s': port %r is not an integer in 1-65535"
                        % (pname, rname, port))
            for pr in rule.get('port_ranges') or []:
                if not isinstance(pr, dict):
                    continue
                start, end = _as_port_int(pr.get('start')), _as_port_int(pr.get('end'))
                if (start is None or end is None
                        or not (1 <= start <= 65535) or not (1 <= end <= 65535)):
                    problems.append(
                        "policy '%s' rule '%s': port_range %r-%r is outside 1-65535"
                        % (pname, rname, pr.get('start'), pr.get('end')))
                elif start > end:
                    problems.append(
                        "policy '%s' rule '%s': port_range start > end (%d > %d)"
                        % (pname, rname, start, end))
    for sk in setup_keys or []:
        if not isinstance(sk, dict):
            continue
        if sk.get('expires_in') is not None:
            iv = _as_port_int(sk.get('expires_in'))
            if iv is None or iv <= 0:
                problems.append(
                    "setup key '%s': expires_in must be a positive integer (got %r)"
                    % (sk.get('name', '<unnamed>'), sk.get('expires_in')))
    return problems


class FilterModule(object):
    """NetBird name-to-ID resolution filter plugins."""

    def filters(self):
        return {
            'netbird_resolve_ids': netbird_resolve_ids,
            'netbird_resolve_names': netbird_resolve_names,
            'netbird_missing_refs': netbird_missing_refs,
            'netbird_missing_names': netbird_missing_names,
            'netbird_value_problems': netbird_value_problems,
        }

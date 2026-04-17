# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+

"""Ansible filter plugins for resolving NetBird name references to API IDs."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.errors import AnsibleFilterError


def _resolve_names(names, id_map, kind='group', context=''):
    """Resolve a list of names using an ID map.

    A value passes through unchanged if it is already a known API ID (i.e.
    appears as a value in id_map), which keeps YAML configs that reference
    groups/checks by raw ID working. An unknown value (neither a known name
    nor a known ID) raises AnsibleFilterError so that silent typos don't
    produce half-applied resources.
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
        else:
            raise AnsibleFilterError(
                "Unknown %s '%s'%s. It is neither a known %s name nor an "
                "existing %s ID. Check for typos or a missing %s definition."
                % (kind, name, (" in " + context) if context else '',
                   kind, kind, kind)
            )
    return resolved


def _resolve_setup_key(sk, group_ids):
    """Resolve a single setup key's auto_groups."""
    result = dict(sk)
    if 'auto_groups' in sk:
        result['auto_groups'] = _resolve_names(
            sk['auto_groups'], group_ids,
            kind='group',
            context="setup key '%s' auto_groups" % sk.get('name', '<unnamed>'),
        )
    return result


def _resolve_resource_ref(resource, peer_ids, context=''):
    """Resolve {name, type: peer} to {id, type: peer} using peer_ids map.

    Non-peer resources (host/domain/subnet) pass through unchanged since their
    IDs in exported YAML are already concrete API IDs.

    Raises AnsibleFilterError if a peer name cannot be resolved to an ID.
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
        raise AnsibleFilterError(
            "Unknown peer '%s'%s. It is neither a known peer name nor an "
            "existing peer ID." % (name, (" in " + context) if context else '')
        )
    return resource


def _resolve_peer_id(peer_ref, peer_ids, context=''):
    """Resolve a single peer name or ID to an ID. Raises on unknown."""
    if peer_ref is None:
        return peer_ref
    known_ids = set(peer_ids.values())
    if peer_ref in peer_ids:
        return peer_ids[peer_ref]
    if peer_ref in known_ids:
        return peer_ref
    raise AnsibleFilterError(
        "Unknown peer '%s'%s. It is neither a known peer name nor an "
        "existing peer ID." % (peer_ref, (" in " + context) if context else '')
    )


def _resolve_policy(policy, group_ids, posture_check_ids, peer_ids=None):
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
            )
            resolved_rule['destinations'] = _resolve_names(
                rule.get('destinations', []),
                group_ids,
                kind='group',
                context="policy '%s' rule '%s' destinations" % (policy_name, rule_name),
            )
            if rule.get('source_resource') is not None:
                resolved_rule['source_resource'] = _resolve_resource_ref(
                    rule['source_resource'], peer_ids,
                    context="policy '%s' rule '%s' source_resource" % (policy_name, rule_name),
                )
            if rule.get('destination_resource') is not None:
                resolved_rule['destination_resource'] = _resolve_resource_ref(
                    rule['destination_resource'], peer_ids,
                    context="policy '%s' rule '%s' destination_resource" % (policy_name, rule_name),
                )
            resolved_rules.append(resolved_rule)
        result['rules'] = resolved_rules

    return result


def _resolve_network(network, group_ids, peer_ids):
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
                )
            if 'peer_groups' in router:
                resolved['peer_groups'] = _resolve_names(
                    router.get('peer_groups', []),
                    group_ids,
                    kind='group',
                    context="network '%s' router peer_groups" % network_name,
                )
            resolved_routers.append(resolved)
        result['routers'] = resolved_routers

    return result


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

        if resource_type == 'setup_key':
            result.append(_resolve_setup_key(item, group_ids))
        elif resource_type == 'policy':
            result.append(_resolve_policy(item, group_ids, posture_check_ids, peer_ids))
        elif resource_type == 'network':
            result.append(_resolve_network(item, group_ids, peer_ids))
        else:
            result.append(item)

    return result


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


class FilterModule(object):
    """NetBird name-to-ID resolution filter plugins."""

    def filters(self):
        return {
            'netbird_resolve_ids': netbird_resolve_ids,
            'netbird_resolve_names': netbird_resolve_names,
        }

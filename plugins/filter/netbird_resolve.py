# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+

"""Ansible filter plugins for resolving NetBird name references to API IDs."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type


def _resolve_names(names, id_map):
    """Resolve a list of names using an ID map, falling back to original."""
    if not names:
        return []
    return [id_map.get(name, name) for name in names]


def _resolve_setup_key(sk, group_ids):
    """Resolve a single setup key's auto_groups."""
    result = dict(sk)
    if 'auto_groups' in sk:
        result['auto_groups'] = _resolve_names(sk['auto_groups'], group_ids)
    return result


def _resolve_policy(policy, group_ids, posture_check_ids):
    """Resolve a single policy's group and posture check references."""
    result = dict(policy)

    if 'source_posture_checks' in policy:
        result['source_posture_checks'] = _resolve_names(
            policy.get('source_posture_checks', []), posture_check_ids
        )

    if 'rules' in policy:
        resolved_rules = []
        for rule in policy.get('rules', []):
            resolved_rule = dict(rule)
            resolved_rule['sources'] = _resolve_names(
                rule.get('sources', []), group_ids
            )
            resolved_rule['destinations'] = _resolve_names(
                rule.get('destinations', []), group_ids
            )
            resolved_rules.append(resolved_rule)
        result['rules'] = resolved_rules

    return result


def _resolve_network(network, group_ids, peer_ids):
    """Resolve a single network's group, peer, and peer_group references."""
    result = dict(network)

    if 'resources' in network:
        resolved_resources = []
        for resource in network.get('resources', []):
            resolved = dict(resource)
            if 'groups' in resource:
                resolved['groups'] = _resolve_names(
                    resource.get('groups', []), group_ids
                )
            resolved_resources.append(resolved)
        result['resources'] = resolved_resources

    if 'routers' in network:
        resolved_routers = []
        for router in network.get('routers', []):
            resolved = dict(router)
            if 'peer' in router:
                resolved['peer'] = peer_ids.get(router['peer'], router['peer'])
            if 'peer_groups' in router:
                resolved['peer_groups'] = _resolve_names(
                    router.get('peer_groups', []), group_ids
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
        list of resource dicts with names replaced by IDs
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
            result.append(_resolve_policy(item, group_ids, posture_check_ids))
        elif resource_type == 'network':
            result.append(_resolve_network(item, group_ids, peer_ids))
        else:
            result.append(item)

    return result


def netbird_resolve_names(name_list, id_map):
    """Resolve a simple list of names to IDs.

    Used for inline resolution (e.g., DNS zone distribution_groups).
    Falls back to original name if not found in map.
    """
    if not isinstance(name_list, list):
        return []
    if not isinstance(id_map, dict):
        return name_list
    return _resolve_names(name_list, id_map)


class FilterModule(object):
    """NetBird name-to-ID resolution filter plugins."""

    def filters(self):
        return {
            'netbird_resolve_ids': netbird_resolve_ids,
            'netbird_resolve_names': netbird_resolve_names,
        }

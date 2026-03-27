#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird networks."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_network
short_description: Manage NetBird networks with routers and resources
description:
  - Create, update, and delete networks in NetBird.
  - Manage network routers (routing peers) and resources (network CIDRs/addresses).
  - This module provides full routing capabilities, replacing the deprecated routes API.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the network.
    type: str
    choices: ['present', 'absent']
    default: present
  network_id:
    description:
      - The unique identifier of the network.
      - Required when state is absent or when updating by ID.
    type: str
  name:
    description:
      - Name of the network.
      - Required when creating a new network.
    type: str
  description:
    description:
      - Description of the network.
    type: str
    default: ''
  routers:
    description:
      - List of routers (routing peers) for this network.
      - Routers are matched by peer or peer_groups combination.
      - Routers not in this list will be removed from the network.
      - Set to empty list to remove all routers.
      - Omit to leave existing routers unchanged.
    type: list
    elements: dict
    suboptions:
      peer:
        description:
          - Peer ID to use as the routing peer.
          - Either peer or peer_groups must be specified.
        type: str
      peer_groups:
        description:
          - List of peer group IDs to use as routing peers.
          - Either peer or peer_groups must be specified.
        type: list
        elements: str
      metric:
        description:
          - Route metric/priority (lower is higher priority).
        type: int
        default: 9999
      masquerade:
        description:
          - Whether to masquerade (NAT) traffic through this router.
        type: bool
        default: false
      enabled:
        description:
          - Whether the router is enabled.
        type: bool
        default: true
  resources:
    description:
      - List of resources (network addresses, CIDRs, or domains) for this network.
      - Resources are matched by address.
      - Resources not in this list will be removed from the network.
      - Set to empty list to remove all resources.
      - Omit to leave existing resources unchanged.
    type: list
    elements: dict
    suboptions:
      address:
        description:
          - Network address, CIDR, or domain name.
          - Supports direct hosts (1.1.1.1), subnets (172.16.0.0/16), domains (example.com), and wildcards (*.example.com).
        type: str
        required: true
      name:
        description:
          - Name of the resource.
        type: str
        default: ''
      description:
        description:
          - Description of the resource.
        type: str
        default: ''
      enabled:
        description:
          - Whether the resource is enabled.
        type: bool
        default: true
      groups:
        description:
          - List of group IDs that can access this resource.
        type: list
        elements: str
        default: []
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a simple network
  community.ansible_netbird.netbird_network:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "office-network"
    description: "Main office network"
    state: present

- name: Create a network with routers and resources (full routing)
  community.ansible_netbird.netbird_network:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "internal-network"
    description: "Internal corporate network"
    routers:
      - peer: "gateway-peer-id"
        metric: 100
        masquerade: true
    resources:
      - address: "172.16.0.0/16"
        name: "internal-range"
        description: "All internal IPs"
        groups:
          - "all-users-group-id"
    state: present

- name: Create HA network with multiple routers using peer groups
  community.ansible_netbird.netbird_network:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "ha-network"
    description: "High availability network with failover"
    routers:
      - peer_groups:
          - "primary-gateways-group"
        metric: 100
        masquerade: true
      - peer_groups:
          - "backup-gateways-group"
        metric: 200
        masquerade: true
    resources:
      - address: "192.168.0.0/16"
        name: "private-networks"
        groups:
          - "developers-group-id"
          - "ops-group-id"
      - address: "172.16.0.0/12"
        name: "docker-networks"
        groups:
          - "developers-group-id"
    state: present

- name: Create network with domain-based routing
  community.ansible_netbird.netbird_network:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "internal-services"
    description: "Route traffic to internal domains"
    routers:
      - peer: "dns-gateway-peer-id"
        metric: 100
        masquerade: true
    resources:
      # Route specific domain
      - address: "internal.example.com"
        name: "internal-portal"
        groups:
          - "all-users-group-id"
      # Route all subdomains with wildcard
      - address: "*.corp.example.com"
        name: "corp-subdomains"
        description: "All corporate subdomains"
        groups:
          - "employees-group-id"
      # Mix domains and IPs in the same network
      - address: "10.100.0.0/16"
        name: "backend-services"
        groups:
          - "developers-group-id"
    state: present

- name: Update network - add new resource
  community.ansible_netbird.netbird_network:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "internal-network"
    routers:
      - peer: "gateway-peer-id"
        metric: 100
        masquerade: true
    resources:
      - address: "172.16.0.0/16"
        name: "internal-range"
        groups:
          - "all-users-group-id"
      - address: "100.64.0.0/10"
        name: "cgnat-range"
        groups:
          - "all-users-group-id"
    state: present

- name: Remove all routers and resources from network
  community.ansible_netbird.netbird_network:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "internal-network"
    routers: []
    resources: []
    state: present

- name: Delete a network
  community.ansible_netbird.netbird_network:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    network_id: "network-id-123"
    state: absent
'''

RETURN = r'''
network:
  description: The network object.
  returned: success
  type: dict
  contains:
    id:
      description: Network ID.
      type: str
    name:
      description: Network name.
      type: str
    description:
      description: Network description.
      type: str
    routers:
      description: List of routers in the network.
      type: list
      elements: dict
      contains:
        id:
          description: Router ID.
          type: str
        peer:
          description: Peer ID for this router.
          type: str
        peer_groups:
          description: List of peer group IDs.
          type: list
        metric:
          description: Route metric.
          type: int
        masquerade:
          description: Whether masquerading is enabled.
          type: bool
    resources:
      description: List of resources in the network.
      type: list
      elements: dict
      contains:
        id:
          description: Resource ID.
          type: str
        address:
          description: Network address, CIDR, or domain name.
          type: str
        name:
          description: Resource name.
          type: str
        description:
          description: Resource description.
          type: str
        enabled:
          description: Whether the resource is enabled.
          type: bool
        groups:
          description: List of group IDs with access.
          type: list
    routing_peers_count:
      description: Number of routing peers.
      type: int
    resources_count:
      description: Number of resources.
      type: int
routers_changed:
  description: Whether any routers were modified.
  returned: success
  type: bool
resources_changed:
  description: Whether any resources were modified.
  returned: success
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    netbird_argument_spec
)


def find_network_by_name(api, name):
    """Find a network by name."""
    networks, _ = api.list_networks()
    for network in networks:
        if network.get('name') == name:
            return network
    return None


def network_needs_update(current, params):
    """Check if network needs to be updated."""
    if params.get('name') is not None and current.get('name') != params['name']:
        return True
    if params.get('description') is not None and current.get('description') != params['description']:
        return True
    return False


def get_router_key(router):
    """Generate a unique key for a router based on peer/peer_groups."""
    peer = router.get('peer', '')
    peer_groups = tuple(sorted(extract_ids(router.get('peer_groups') or [])))
    return (peer, peer_groups)


def router_needs_update(current, desired):
    """Check if a router needs to be updated."""
    if current.get('metric') != desired.get('metric', 9999):
        return True
    if current.get('masquerade') != desired.get('masquerade', False):
        return True
    if current.get('enabled') != desired.get('enabled', True):
        return True
    return False


def resource_needs_update(current, desired):
    """Check if a resource needs to be updated."""
    if current.get('name', '') != desired.get('name', ''):
        return True
    if current.get('description', '') != desired.get('description', ''):
        return True
    if current.get('enabled', True) != desired.get('enabled', True):
        return True
    current_groups = set(extract_ids(current.get('groups') or []))
    desired_groups = set(extract_ids(desired.get('groups') or []))
    if current_groups != desired_groups:
        return True
    return False


def sync_routers(api, module, network_id, desired_routers):
    """Synchronize routers for a network. Returns (changed, routers_list)."""
    changed = False
    
    # Get current routers
    current_routers, _ = api.list_network_routers(network_id)
    current_by_key = {get_router_key(r): r for r in current_routers}
    
    # Build desired routers map
    desired_by_key = {}
    for router in desired_routers:
        peer = router.get('peer', '')
        peer_groups = router.get('peer_groups', []) or []
        key = (peer, tuple(sorted(peer_groups)))
        desired_by_key[key] = router
    
    final_routers = []
    
    # Create or update routers
    for key, desired in desired_by_key.items():
        peer, peer_groups_tuple = key
        peer_groups = list(peer_groups_tuple) if peer_groups_tuple else None
        
        if key in current_by_key:
            current = current_by_key[key]
            if router_needs_update(current, desired):
                if not module.check_mode:
                    updated, _ = api.update_network_router(
                        network_id,
                        current['id'],
                        peer_id=peer if peer else None,
                        peer_groups=peer_groups,
                        metric=desired.get('metric', 9999),
                        masquerade=desired.get('masquerade', False),
                        enabled=desired.get('enabled', True)
                    )
                    final_routers.append(updated)
                else:
                    final_routers.append(current)
                changed = True
            else:
                final_routers.append(current)
        else:
            # Create new router
            if not module.check_mode:
                created, _ = api.create_network_router(
                    network_id,
                    peer_id=peer if peer else None,
                    peer_groups=peer_groups,
                    metric=desired.get('metric', 9999),
                    masquerade=desired.get('masquerade', False),
                    enabled=desired.get('enabled', True)
                )
                final_routers.append(created)
            changed = True
    
    # Delete routers not in desired state
    for key, current in current_by_key.items():
        if key not in desired_by_key:
            if not module.check_mode:
                api.delete_network_router(network_id, current['id'])
            changed = True
    
    return changed, final_routers


def sync_resources(api, module, network_id, desired_resources):
    """Synchronize resources for a network. Returns (changed, resources_list)."""
    changed = False
    
    # Get current resources
    current_resources, _ = api.list_network_resources(network_id)
    current_by_address = {r.get('address'): r for r in current_resources}
    
    # Build desired resources map
    desired_by_address = {r['address']: r for r in desired_resources}
    
    final_resources = []
    
    # Create or update resources
    for address, desired in desired_by_address.items():
        if address in current_by_address:
            current = current_by_address[address]
            if resource_needs_update(current, desired):
                if not module.check_mode:
                    updated, _ = api.update_network_resource(
                        network_id,
                        current['id'],
                        address=address,
                        name=desired.get('name', ''),
                        description=desired.get('description', ''),
                        enabled=desired.get('enabled', True),
                        groups=desired.get('groups', [])
                    )
                    final_resources.append(updated)
                else:
                    final_resources.append(current)
                changed = True
            else:
                final_resources.append(current)
        else:
            # Create new resource
            if not module.check_mode:
                created, _ = api.create_network_resource(
                    network_id,
                    address=address,
                    name=desired.get('name', ''),
                    description=desired.get('description', ''),
                    enabled=desired.get('enabled', True),
                    groups=desired.get('groups', [])
                )
                final_resources.append(created)
            changed = True
    
    # Delete resources not in desired state
    for address, current in current_by_address.items():
        if address not in desired_by_address:
            if not module.check_mode:
                api.delete_network_resource(network_id, current['id'])
            changed = True
    
    return changed, final_resources


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        network_id=dict(type='str'),
        name=dict(type='str'),
        description=dict(type='str', default=''),
        routers=dict(
            type='list',
            elements='dict',
            options=dict(
                peer=dict(type='str'),
                peer_groups=dict(type='list', elements='str'),
                metric=dict(type='int', default=9999),
                masquerade=dict(type='bool', default=False),
                enabled=dict(type='bool', default=True)
            ),
            required_one_of=[('peer', 'peer_groups')],
            mutually_exclusive=[('peer', 'peer_groups')]
        ),
        resources=dict(
            type='list',
            elements='dict',
            options=dict(
                address=dict(type='str', required=True),
                name=dict(type='str', default=''),
                description=dict(type='str', default=''),
                enabled=dict(type='bool', default=True),
                groups=dict(type='list', elements='str', default=[])
            )
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[
            ('network_id', 'name'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    network_id = module.params['network_id']
    name = module.params['name']
    description = module.params['description']
    routers = module.params['routers']
    resources = module.params['resources']

    result = dict(
        changed=False,
        network={},
        routers_changed=False,
        resources_changed=False
    )

    try:
        # Find existing network
        existing_network = None
        if network_id:
            try:
                existing_network, _ = api.get_network(network_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_network = find_network_by_name(api, name)

        if state == 'absent':
            if existing_network:
                if not module.check_mode:
                    api.delete_network(existing_network['id'])
                result['changed'] = True
                result['msg'] = 'Network deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        network_changed = False
        
        if existing_network:
            current_network_id = existing_network['id']
            
            # Check if network metadata needs update
            update_params = {
                'name': name,
                'description': description
            }
            
            if network_needs_update(existing_network, update_params):
                if not module.check_mode:
                    network, _ = api.update_network(
                        current_network_id,
                        name=name,
                        description=description
                    )
                    result['network'] = network
                else:
                    result['network'] = existing_network
                network_changed = True
            else:
                result['network'] = existing_network
        else:
            # Create new network
            if not name:
                module.fail_json(msg="name is required when creating a new network")
            
            if not module.check_mode:
                network, _ = api.create_network(
                    name=name,
                    description=description
                )
                result['network'] = network
                current_network_id = network['id']
            else:
                # In check mode, we can't sync routers/resources for a new network
                result['network'] = {'name': name, 'description': description}
                result['changed'] = True
                module.exit_json(**result)
            network_changed = True

        # Sync routers if specified
        if routers is not None:
            routers_changed, final_routers = sync_routers(api, module, current_network_id, routers)
            result['routers_changed'] = routers_changed
            result['network']['routers'] = final_routers
            if routers_changed:
                result['changed'] = True

        # Sync resources if specified
        if resources is not None:
            resources_changed, final_resources = sync_resources(api, module, current_network_id, resources)
            result['resources_changed'] = resources_changed
            result['network']['resources'] = final_resources
            if resources_changed:
                result['changed'] = True

        if network_changed:
            result['changed'] = True

        # Refresh network data to get updated counts
        if not module.check_mode and (routers is not None or resources is not None):
            refreshed_network, _ = api.get_network(current_network_id)
            # Preserve the routers/resources lists we built
            saved_routers = result['network'].get('routers')
            saved_resources = result['network'].get('resources')
            result['network'] = refreshed_network
            if saved_routers is not None:
                result['network']['routers'] = saved_routers
            if saved_resources is not None:
                result['network']['resources'] = saved_resources

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()

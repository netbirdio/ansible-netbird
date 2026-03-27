#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird routes."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_route
short_description: Manage NetBird routes (deprecated API)
description:
  - Create, update, and delete routes in NetBird.
  - Note: This uses the deprecated routes API. Consider using networks for new implementations.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the route.
    type: str
    choices: ['present', 'absent']
    default: present
  route_id:
    description:
      - The unique identifier of the route.
      - Required when state is absent or when updating by ID.
    type: str
  network_id:
    description:
      - Network identifier for the route.
    type: str
  network:
    description:
      - Network CIDR (e.g., "10.0.0.0/24").
    type: str
  description:
    description:
      - Description of the route.
    type: str
    default: ''
  peer_id:
    description:
      - Peer ID to use as the routing peer.
      - Either peer_id or peer_groups must be specified.
    type: str
  peer_groups:
    description:
      - List of peer group IDs to use as routing peers.
      - Either peer_id or peer_groups must be specified.
    type: list
    elements: str
  metric:
    description:
      - Route metric/priority (lower is higher priority).
    type: int
    default: 9999
  masquerade:
    description:
      - Whether to masquerade (NAT) traffic through the route.
    type: bool
    default: true
  enabled:
    description:
      - Whether the route is enabled.
    type: bool
    default: true
  groups:
    description:
      - List of group IDs that can access this route.
    type: list
    elements: str
    default: []
  keep_route:
    description:
      - Whether to keep the route when the peer is offline.
    type: bool
    default: false
  domains:
    description:
      - List of domains for DNS routing.
    type: list
    elements: str
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a route to internal network
  community.ansible_netbird.netbird_route:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    network_id: "internal-route"
    network: "172.16.0.0/16"
    description: "Route to internal network"
    peer_id: "gateway-peer-id"
    metric: 100
    masquerade: true
    enabled: true
    groups:
      - "all-peers-group-id"
    state: present

- name: Create a route with peer groups
  community.ansible_netbird.netbird_route:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    network_id: "ha-route"
    network: "192.168.0.0/16"
    description: "High availability route"
    peer_groups:
      - "gateway-group-id"
    metric: 100
    masquerade: true
    enabled: true
    groups:
      - "developers-group-id"
    state: present

- name: Disable a route
  community.ansible_netbird.netbird_route:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    route_id: "route-id-123"
    enabled: false
    state: present

- name: Delete a route
  community.ansible_netbird.netbird_route:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    route_id: "route-id-123"
    state: absent
'''

RETURN = r'''
route:
  description: The route object.
  returned: success
  type: dict
  contains:
    id:
      description: Route ID.
      type: str
    network_id:
      description: Network identifier.
      type: str
    network:
      description: Network CIDR.
      type: str
    description:
      description: Route description.
      type: str
    peer:
      description: Routing peer ID.
      type: str
    peer_groups:
      description: List of routing peer group IDs.
      type: list
    metric:
      description: Route metric.
      type: int
    masquerade:
      description: Whether masquerading is enabled.
      type: bool
    enabled:
      description: Whether route is enabled.
      type: bool
    groups:
      description: List of access group IDs.
      type: list
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    netbird_argument_spec
)


def find_route_by_network_id(api, network_id):
    """Find a route by network ID."""
    routes, _ = api.list_routes()
    for route in routes:
        if route.get('network_id') == network_id:
            return route
    return None


def route_needs_update(current, params):
    """Check if route needs to be updated."""
    check_fields = ['network', 'description', 'metric', 'masquerade', 'enabled', 'keep_route']
    for field in check_fields:
        if params.get(field) is not None and current.get(field) != params[field]:
            return True
    
    # Check peer
    if params.get('peer_id') is not None and current.get('peer') != params['peer_id']:
        return True
    
    # Check peer_groups
    if params.get('peer_groups') is not None:
        current_groups = set(extract_ids(current.get('peer_groups') or []))
        desired_groups = set(extract_ids(params['peer_groups'] or []))
        if current_groups != desired_groups:
            return True

    # Check groups
    if params.get('groups') is not None:
        current_groups = set(extract_ids(current.get('groups') or []))
        desired_groups = set(extract_ids(params['groups'] or []))
        if current_groups != desired_groups:
            return True
    
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        route_id=dict(type='str'),
        network_id=dict(type='str'),
        network=dict(type='str'),
        description=dict(type='str', default=''),
        peer_id=dict(type='str'),
        peer_groups=dict(type='list', elements='str'),
        metric=dict(type='int', default=9999),
        masquerade=dict(type='bool', default=True),
        enabled=dict(type='bool', default=True),
        groups=dict(type='list', elements='str', default=[]),
        keep_route=dict(type='bool', default=False),
        domains=dict(type='list', elements='str')
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[
            ('route_id', 'network_id'),
        ],
        mutually_exclusive=[
            ('peer_id', 'peer_groups'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    route_id = module.params['route_id']
    network_id = module.params['network_id']

    result = dict(
        changed=False,
        route={}
    )

    try:
        # Find existing route
        existing_route = None
        if route_id:
            try:
                existing_route, _ = api.get_route(route_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif network_id:
            existing_route = find_route_by_network_id(api, network_id)

        if state == 'absent':
            if existing_route:
                if not module.check_mode:
                    api.delete_route(existing_route['id'])
                result['changed'] = True
                result['msg'] = 'Route deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_route:
            # Check if update is needed
            update_params = {
                'network': module.params['network'],
                'description': module.params['description'],
                'peer_id': module.params['peer_id'],
                'peer_groups': module.params['peer_groups'],
                'metric': module.params['metric'],
                'masquerade': module.params['masquerade'],
                'enabled': module.params['enabled'],
                'groups': module.params['groups'],
                'keep_route': module.params['keep_route']
            }
            
            if route_needs_update(existing_route, update_params):
                if not module.check_mode:
                    route, _ = api.update_route(
                        existing_route['id'],
                        network_id=network_id,
                        network=module.params['network'],
                        description=module.params['description'],
                        peer_id=module.params['peer_id'],
                        peer_groups=module.params['peer_groups'],
                        metric=module.params['metric'],
                        masquerade=module.params['masquerade'],
                        enabled=module.params['enabled'],
                        groups=module.params['groups'],
                        keep_route=module.params['keep_route'],
                        domains=module.params['domains']
                    )
                    result['route'] = route
                else:
                    result['route'] = existing_route
                result['changed'] = True
            else:
                result['route'] = existing_route
        else:
            # Create new route
            if not network_id:
                module.fail_json(msg="network_id is required when creating a new route")
            if not module.params['network']:
                module.fail_json(msg="network is required when creating a new route")
            if not module.params['peer_id'] and not module.params['peer_groups']:
                module.fail_json(msg="Either peer_id or peer_groups is required when creating a new route")
            
            if not module.check_mode:
                route, _ = api.create_route(
                    network_id=network_id,
                    network=module.params['network'],
                    description=module.params['description'],
                    peer_id=module.params['peer_id'],
                    peer_groups=module.params['peer_groups'],
                    metric=module.params['metric'],
                    masquerade=module.params['masquerade'],
                    enabled=module.params['enabled'],
                    groups=module.params['groups'],
                    keep_route=module.params['keep_route'],
                    domains=module.params['domains']
                )
                result['route'] = route
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



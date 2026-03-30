#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird groups."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_group
short_description: Manage NetBird groups
description:
  - Create, update, and delete groups in NetBird.
  - Groups are used to organize peers and define access policies.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the group.
    type: str
    choices: ['present', 'absent']
    default: present
  group_id:
    description:
      - The unique identifier of the group.
      - Required when state is absent or when updating by ID.
    type: str
  name:
    description:
      - Name of the group.
      - Required when creating a new group.
    type: str
  peers:
    description:
      - List of peer IDs to include in the group.
      - When updating an existing group and this is not specified, the current peers are preserved.
    type: list
    elements: str
  resources:
    description:
      - List of resource objects for the group.
    type: list
    elements: dict
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a group
  community.ansible_netbird.netbird_group:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "developers"
    state: present

- name: Create a group with peers
  community.ansible_netbird.netbird_group:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "production-servers"
    peers:
      - "peer-id-1"
      - "peer-id-2"
    state: present

- name: Update group peers
  community.ansible_netbird.netbird_group:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    group_id: "group-id-123"
    peers:
      - "peer-id-1"
      - "peer-id-2"
      - "peer-id-3"
    state: present

- name: Delete a group
  community.ansible_netbird.netbird_group:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    group_id: "group-id-123"
    state: absent
'''

RETURN = r'''
group:
  description: The group object.
  returned: success
  type: dict
  contains:
    id:
      description: Group ID.
      type: str
    name:
      description: Group name.
      type: str
    peers_count:
      description: Number of peers in the group.
      type: int
    peers:
      description: List of peer IDs.
      type: list
    resources:
      description: List of resources.
      type: list
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    netbird_argument_spec
)


def find_group_by_name(api, name):
    """Find a group by name."""
    groups, _ = api.list_groups()
    for group in (groups or []):
        if group.get('name') == name:
            return group
    return None


def group_needs_update(current, desired):
    """Check if group needs to be updated."""
    if 'name' in desired and desired['name'] is not None:
        if current.get('name') != desired['name']:
            return True

    if 'peers' in desired and desired['peers'] is not None:
        current_peers = set(extract_ids(current.get('peers') or []))
        desired_peers = set(extract_ids(desired['peers'] or []))
        if current_peers != desired_peers:
            return True

    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        group_id=dict(type='str'),
        name=dict(type='str'),
        peers=dict(type='list', elements='str'),
        resources=dict(type='list', elements='dict')
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[
            ('group_id', 'name'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    group_id = module.params['group_id']
    name = module.params['name']
    peers = module.params['peers']
    resources = module.params['resources']

    result = dict(
        changed=False,
        group={}
    )

    try:
        # Find existing group
        existing_group = None
        if group_id:
            try:
                existing_group, _ = api.get_group(group_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_group = find_group_by_name(api, name)

        if state == 'absent':
            if existing_group:
                if not module.check_mode:
                    api.delete_group(existing_group['id'])
                result['changed'] = True
                result['msg'] = 'Group deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_group:
            # Use existing values as fallback for fields the user didn't specify
            effective_peers = peers if peers is not None else existing_group.get('peers', [])
            # Normalize peers to list of IDs (API may return dicts with 'id' key)
            effective_peer_ids = [
                p['id'] if isinstance(p, dict) else p for p in (effective_peers or [])
            ]

            # Check if update is needed
            desired = {
                'name': name,
                'peers': effective_peer_ids
            }

            if group_needs_update(existing_group, desired):
                if not module.check_mode:
                    group, _ = api.update_group(
                        existing_group['id'],
                        name=name,
                        peers=effective_peer_ids,
                        resources=resources
                    )
                    result['group'] = group
                else:
                    result['group'] = existing_group
                result['changed'] = True
            else:
                result['group'] = existing_group
        else:
            # Create new group
            if not name:
                module.fail_json(msg="name is required when creating a new group")

            if not module.check_mode:
                group, _ = api.create_group(
                    name=name,
                    peers=peers or [],
                    resources=resources
                )
                result['group'] = group
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



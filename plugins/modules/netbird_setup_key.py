#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird setup keys."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_setup_key
short_description: Manage NetBird setup keys
description:
  - Create, update, and delete setup keys in NetBird.
  - Setup keys are used to register new peers to the network.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the setup key.
    type: str
    choices: ['present', 'absent']
    default: present
  key_id:
    description:
      - The unique identifier of the setup key.
      - Required when state is absent or when updating by ID.
    type: str
  name:
    description:
      - Name of the setup key.
      - Required when creating a new setup key.
    type: str
  key_type:
    description:
      - Type of the setup key.
      - 'one-off' keys can only be used once.
      - 'reusable' keys can be used multiple times.
    type: str
    choices: ['one-off', 'reusable']
    default: one-off
  expires_in:
    description:
      - Expiration time in seconds.
      - Default is 86400 (24 hours).
    type: int
    default: 86400
  revoked:
    description:
      - Whether the key is revoked.
    type: bool
    default: false
  auto_groups:
    description:
      - List of group IDs to auto-assign to peers registered with this key.
    type: list
    elements: str
    default: []
  usage_limit:
    description:
      - Maximum number of times the key can be used.
      - 0 means unlimited (for reusable keys).
    type: int
    default: 0
  ephemeral:
    description:
      - Whether peers registered with this key are ephemeral.
      - Ephemeral peers are automatically removed when disconnected.
    type: bool
    default: false
  allow_extra_dns_labels:
    description:
      - Allow extra DNS labels for peers registered with this key.
    type: bool
    default: false
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a one-off setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "new-server-key"
    key_type: "one-off"
    expires_in: 3600
    state: present
  register: setup_key

- name: Create a reusable setup key with auto groups
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "developer-machines"
    key_type: "reusable"
    expires_in: 604800
    auto_groups:
      - "developers-group-id"
    state: present

- name: Create an ephemeral setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "temporary-access"
    key_type: "reusable"
    ephemeral: true
    state: present

- name: Revoke a setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    key_id: "key-id-123"
    revoked: true
    state: present

- name: Delete a setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    key_id: "key-id-123"
    state: absent
'''

RETURN = r'''
setup_key:
  description: The setup key object.
  returned: success
  type: dict
  contains:
    id:
      description: Setup key ID.
      type: str
    key:
      description: The actual setup key value (only returned on creation).
      type: str
    name:
      description: Setup key name.
      type: str
    type:
      description: Key type (one-off or reusable).
      type: str
    expires:
      description: Expiration timestamp.
      type: str
    revoked:
      description: Whether the key is revoked.
      type: bool
    auto_groups:
      description: Auto-assigned group IDs.
      type: list
    usage_limit:
      description: Usage limit.
      type: int
    used_times:
      description: Number of times the key has been used.
      type: int
    last_used:
      description: Last used timestamp.
      type: str
    ephemeral:
      description: Whether key creates ephemeral peers.
      type: bool
    valid:
      description: Whether the key is still valid.
      type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    netbird_argument_spec
)


def find_setup_key_by_name(api, name):
    """Find a setup key by name."""
    keys, _ = api.list_setup_keys()
    for key in keys:
        if key.get('name') == name:
            return key
    return None


def setup_key_needs_update(current, params):
    """Check if setup key needs to be updated."""
    if params.get('name') is not None and current.get('name') != params['name']:
        return True
    if params.get('revoked') is not None and current.get('revoked') != params['revoked']:
        return True
    if params.get('auto_groups') is not None:
        current_groups = set(current.get('auto_groups', []))
        desired_groups = set(params['auto_groups'])
        if current_groups != desired_groups:
            return True
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        key_id=dict(type='str'),
        name=dict(type='str'),
        key_type=dict(type='str', choices=['one-off', 'reusable'], default='one-off'),
        expires_in=dict(type='int', default=86400),
        revoked=dict(type='bool', default=False),
        auto_groups=dict(type='list', elements='str', default=[]),
        usage_limit=dict(type='int', default=0),
        ephemeral=dict(type='bool', default=False),
        allow_extra_dns_labels=dict(type='bool', default=False)
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[
            ('key_id', 'name'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    key_id = module.params['key_id']
    name = module.params['name']

    result = dict(
        changed=False,
        setup_key={}
    )

    try:
        # Find existing setup key
        existing_key = None
        if key_id:
            try:
                existing_key, _ = api.get_setup_key(key_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_key = find_setup_key_by_name(api, name)

        if state == 'absent':
            if existing_key:
                if not module.check_mode:
                    api.delete_setup_key(existing_key['id'])
                result['changed'] = True
                result['msg'] = 'Setup key deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_key:
            # Check if update is needed
            update_params = {
                'name': name,
                'revoked': module.params['revoked'],
                'auto_groups': module.params['auto_groups']
            }
            
            if setup_key_needs_update(existing_key, update_params):
                if not module.check_mode:
                    key, _ = api.update_setup_key(
                        existing_key['id'],
                        revoked=module.params['revoked'],
                        auto_groups=module.params['auto_groups']
                    )
                    result['setup_key'] = key
                else:
                    result['setup_key'] = existing_key
                result['changed'] = True
            else:
                result['setup_key'] = existing_key
        else:
            # Create new setup key
            if not name:
                module.fail_json(msg="name is required when creating a new setup key")
            
            if not module.check_mode:
                key, _ = api.create_setup_key(
                    name=name,
                    key_type=module.params['key_type'],
                    expires_in=module.params['expires_in'],
                    revoked=module.params['revoked'],
                    auto_groups=module.params['auto_groups'],
                    usage_limit=module.params['usage_limit'],
                    ephemeral=module.params['ephemeral'],
                    allow_extra_dns_labels=module.params['allow_extra_dns_labels']
                )
                result['setup_key'] = key
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



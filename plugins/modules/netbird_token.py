#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird personal access tokens."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_token
short_description: Manage NetBird personal access tokens
description:
  - Create and delete personal access tokens in NetBird.
  - Tokens are used for API authentication.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the token.
    type: str
    choices: ['present', 'absent']
    default: present
  user_id:
    description:
      - The unique identifier of the user to manage tokens for.
    type: str
    required: true
  token_id:
    description:
      - The unique identifier of the token.
      - Required when state is absent.
    type: str
  name:
    description:
      - Name of the token.
      - Required when creating a new token.
    type: str
  expires_in:
    description:
      - Token expiration time in days.
      - If not specified, uses the default expiration.
    type: int
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a personal access token
  community.ansible_netbird.netbird_token:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    user_id: "user-id-123"
    name: "automation-token"
    expires_in: 365
    state: present
  register: new_token

- name: Display the token value (only available on creation)
  ansible.builtin.debug:
    msg: "Token: {{ new_token.token.plain_token }}"

- name: Delete a token
  community.ansible_netbird.netbird_token:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    user_id: "user-id-123"
    token_id: "token-id-456"
    state: absent
'''

RETURN = r'''
token:
  description: The token object.
  returned: success
  type: dict
  contains:
    id:
      description: Token ID.
      type: str
    name:
      description: Token name.
      type: str
    expiration_date:
      description: Token expiration date.
      type: str
    created_by:
      description: User ID who created the token.
      type: str
    created_at:
      description: Token creation timestamp.
      type: str
    last_used:
      description: Last used timestamp.
      type: str
    plain_token:
      description: The actual token value (only returned on creation).
      type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    netbird_argument_spec
)


def find_token_by_name(api, user_id, name):
    """Find a token by name for a specific user."""
    tokens, _ = api.list_tokens(user_id)
    for token in (tokens or []):
        if token.get('name') == name:
            return token
    return None


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        user_id=dict(type='str', required=True),
        token_id=dict(type='str'),
        name=dict(type='str'),
        expires_in=dict(type='int')
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'absent', ['token_id'], True),
            ('state', 'present', ['name'], True),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    user_id = module.params['user_id']
    token_id = module.params['token_id']
    name = module.params['name']
    expires_in = module.params['expires_in']

    result = dict(
        changed=False,
        token={}
    )

    try:
        if state == 'absent':
            if token_id:
                if not module.check_mode:
                    api.delete_token(user_id, token_id)
                result['changed'] = True
                result['msg'] = 'Token deleted successfully'
            elif name:
                # Find token by name to delete
                existing_token = find_token_by_name(api, user_id, name)
                if existing_token:
                    if not module.check_mode:
                        api.delete_token(user_id, existing_token['id'])
                    result['changed'] = True
                    result['msg'] = 'Token deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        # Check if token with this name already exists
        existing_token = find_token_by_name(api, user_id, name)
        
        if existing_token:
            # Token exists, return it (we can't update tokens)
            result['token'] = existing_token
            result['msg'] = 'Token already exists'
        else:
            # Create new token
            if not module.check_mode:
                token, _ = api.create_token(
                    user_id,
                    name=name,
                    expires_in=expires_in
                )
                result['token'] = token
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



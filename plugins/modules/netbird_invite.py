#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird user invites."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_invite
short_description: Manage NetBird user invites
description:
  - Create, delete, and regenerate user invites in NetBird.
  - Invites are used to onboard new users to a NetBird account.
  - Invites cannot be updated, only created, deleted, or regenerated.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the user invite.
    type: str
    choices: ['present', 'absent']
    default: present
  invite_id:
    description:
      - The unique identifier of the user invite.
      - Can be used to delete a specific invite when state is absent.
    type: str
  email:
    description:
      - Email address for the invite.
      - Required when state is present.
    type: str
  name:
    description:
      - Name of the invited user.
    type: str
  role:
    description:
      - Role to assign to the invited user.
    type: str
    choices: ['admin', 'user']
    default: user
  auto_groups:
    description:
      - List of group IDs to auto-assign to the invited user.
    type: list
    elements: str
    default: []
  expires_in:
    description:
      - Expiration time for the invite in seconds.
    type: int
  regenerate:
    description:
      - If true and an invite already exists for the email, regenerate the invite token.
    type: bool
    default: false
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a user invite
  community.ansible_netbird.netbird_invite:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    email: "newuser@example.com"
    name: "New User"
    role: "user"
    auto_groups:
      - "group-id-1"
    expires_in: 604800
    state: present

- name: Create an admin invite
  community.ansible_netbird.netbird_invite:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    email: "admin@example.com"
    name: "Admin User"
    role: "admin"
    state: present

- name: Regenerate an existing invite
  community.ansible_netbird.netbird_invite:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    email: "newuser@example.com"
    regenerate: true
    state: present

- name: Delete an invite by email
  community.ansible_netbird.netbird_invite:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    email: "newuser@example.com"
    state: absent

- name: Delete an invite by ID
  community.ansible_netbird.netbird_invite:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    invite_id: "invite-id-123"
    state: absent
'''

RETURN = r'''
invite:
  description: The user invite object.
  returned: success
  type: dict
  contains:
    id:
      description: Invite ID.
      type: str
    email:
      description: Invited user email.
      type: str
    name:
      description: Invited user name.
      type: str
    role:
      description: Assigned role.
      type: str
    auto_groups:
      description: Auto-assigned group IDs.
      type: list
    expires_at:
      description: Invite expiration timestamp.
      type: str
    created_at:
      description: Invite creation timestamp.
      type: str
    expired:
      description: Whether the invite has expired.
      type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    netbird_argument_spec
)


def find_invite_by_email(api, email):
    """Find a user invite by email address."""
    invites, _ = api.list_user_invites()
    for invite in invites:
        if invite.get('email') == email:
            return invite
    return None


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        invite_id=dict(type='str'),
        email=dict(type='str'),
        name=dict(type='str'),
        role=dict(type='str', choices=['admin', 'user'], default='user'),
        auto_groups=dict(type='list', elements='str', default=[]),
        expires_in=dict(type='int'),
        regenerate=dict(type='bool', default=False)
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'present', ['email']),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    invite_id = module.params['invite_id']
    email = module.params['email']
    name = module.params['name']
    role = module.params['role']
    auto_groups = module.params['auto_groups']
    expires_in = module.params['expires_in']
    regenerate = module.params['regenerate']

    result = dict(
        changed=False,
        invite={}
    )

    try:
        if state == 'absent':
            if invite_id:
                if not module.check_mode:
                    api.delete_user_invite(invite_id)
                result['changed'] = True
                result['msg'] = 'User invite deleted successfully'
            elif email:
                existing_invite = find_invite_by_email(api, email)
                if existing_invite:
                    if not module.check_mode:
                        api.delete_user_invite(existing_invite['id'])
                    result['changed'] = True
                    result['msg'] = 'User invite deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        existing_invite = find_invite_by_email(api, email)

        if existing_invite:
            if regenerate:
                # Regenerate the invite token
                if not module.check_mode:
                    invite, _ = api.regenerate_user_invite(
                        existing_invite['id'],
                        expires_in=expires_in
                    )
                    result['invite'] = invite
                else:
                    result['invite'] = existing_invite
                result['changed'] = True
            else:
                # Invite already exists, return it
                result['invite'] = existing_invite
                result['msg'] = 'User invite already exists'
        else:
            # Create new invite
            if not module.check_mode:
                invite, _ = api.create_user_invite(
                    email=email,
                    name=name,
                    role=role,
                    auto_groups=auto_groups,
                    expires_in=expires_in
                )
                result['invite'] = invite
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()

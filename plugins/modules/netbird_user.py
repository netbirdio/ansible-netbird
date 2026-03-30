#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird users."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_user
short_description: Manage NetBird users
description:
  - Create, update, delete, and manage users in NetBird.
  - Supports both regular users and service users.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the user.
    type: str
    choices: ['present', 'absent']
  user_id:
    description:
      - The unique identifier of the user.
      - Required when state is absent or when updating an existing user.
    type: str
  email:
    description:
      - User's email address.
      - Required when creating a regular user (not a service user).
    type: str
  name:
    description:
      - User's full name.
    type: str
  role:
    description:
      - User's NetBird account role.
    type: str
    choices: ['admin', 'user', 'owner', 'network_admin', 'auditor']
    default: user
  auto_groups:
    description:
      - List of group IDs to auto-assign to peers registered by this user.
    type: list
    elements: str
    default: []
  is_service_user:
    description:
      - Set to true if this user is a service user.
    type: bool
    default: false
  is_blocked:
    description:
      - If set to true, the user is blocked and cannot use the system.
    type: bool
  action:
    description:
      - Action to perform on the user.
      - Use 'approve' to approve a user with pending approval status.
      - Use 'reject' to reject a user with pending approval status.
      - Mutually exclusive with state.
    type: str
    choices: ['approve', 'reject']
  resend_invitation:
    description:
      - Resend user invitation email.
    type: bool
    default: false
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a regular user
  community.ansible_netbird.netbird_user:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    email: "user@example.com"
    name: "John Doe"
    role: "user"
    auto_groups:
      - "group-id-1"
    state: present

- name: Create a service user
  community.ansible_netbird.netbird_user:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "automation-service"
    role: "admin"
    is_service_user: true
    state: present

- name: Block a user
  community.ansible_netbird.netbird_user:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    user_id: "user-id-123"
    is_blocked: true
    state: present

- name: Delete a user
  community.ansible_netbird.netbird_user:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    user_id: "user-id-123"
    state: absent

- name: Resend user invitation
  community.ansible_netbird.netbird_user:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    user_id: "user-id-123"
    resend_invitation: true
'''

RETURN = r'''
user:
  description: The user object.
  returned: success
  type: dict
  contains:
    id:
      description: User ID.
      type: str
    email:
      description: User email.
      type: str
    name:
      description: User name.
      type: str
    role:
      description: User role.
      type: str
    status:
      description: User status.
      type: str
    auto_groups:
      description: Auto-assigned groups.
      type: list
    is_service_user:
      description: Whether user is a service user.
      type: bool
    is_blocked:
      description: Whether user is blocked.
      type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    netbird_argument_spec
)


def find_user_by_email(api, email):
    """Find a user by email address."""
    users, _ = api.list_users()
    for user in (users or []):
        if user.get('email') == email:
            return user
    return None


def find_user_by_name(api, name, is_service_user=False):
    """Find a service user by name."""
    users, _ = api.list_users(service_user=is_service_user)
    for user in (users or []):
        if user.get('name') == name:
            return user
    return None


def user_needs_update(current, desired):
    """Check if user needs to be updated."""
    for key in ['role', 'is_blocked']:
        if key in desired and desired[key] is not None:
            if current.get(key) != desired[key]:
                return True
    
    if 'auto_groups' in desired and desired['auto_groups'] is not None:
        current_groups = set(extract_ids(current.get('auto_groups') or []))
        desired_groups = set(extract_ids(desired['auto_groups'] or []))
        if current_groups != desired_groups:
            return True
    
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent']),
        user_id=dict(type='str'),
        email=dict(type='str'),
        name=dict(type='str'),
        role=dict(type='str', choices=['admin', 'user', 'owner', 'network_admin', 'auditor'], default='user'),
        auto_groups=dict(type='list', elements='str', default=[]),
        is_service_user=dict(type='bool', default=False),
        is_blocked=dict(type='bool'),
        resend_invitation=dict(type='bool', default=False),
        action=dict(type='str', choices=['approve', 'reject']),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'absent', ['user_id']),
        ],
        mutually_exclusive=[['state', 'action']],
        required_one_of=[['state', 'action']]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    user_id = module.params['user_id']
    email = module.params['email']
    name = module.params['name']
    role = module.params['role']
    auto_groups = module.params['auto_groups']
    is_service_user = module.params['is_service_user']
    is_blocked = module.params['is_blocked']
    resend_invitation = module.params['resend_invitation']

    result = dict(
        changed=False,
        user={}
    )

    try:
        # Handle action parameter (approve/reject)
        action = module.params.get('action')
        if action:
            user_id = module.params['user_id']
            if not user_id:
                module.fail_json(msg="user_id is required when using action parameter")
            if not module.check_mode:
                if action == 'approve':
                    api.approve_user(user_id)
                elif action == 'reject':
                    api.reject_user(user_id)
            result['changed'] = True
            result['msg'] = f'User {action}d successfully'
            module.exit_json(**result)

        # Handle resend invitation
        if resend_invitation and user_id:
            if not module.check_mode:
                api.resend_user_invitation(user_id)
            result['changed'] = True
            result['msg'] = 'Invitation resent successfully'
            module.exit_json(**result)

        # Find existing user
        existing_user = None
        if user_id:
            existing_user, _ = api.get_user(user_id)
        elif email:
            existing_user = find_user_by_email(api, email)
        elif name and is_service_user:
            existing_user = find_user_by_name(api, name, is_service_user=True)

        if state == 'absent':
            if existing_user:
                if not module.check_mode:
                    api.delete_user(existing_user['id'])
                result['changed'] = True
                result['msg'] = 'User deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_user:
            # Check if update is needed
            desired = {
                'role': role,
                'auto_groups': auto_groups,
                'is_blocked': is_blocked
            }
            
            if user_needs_update(existing_user, desired):
                if not module.check_mode:
                    user, _ = api.update_user(
                        existing_user['id'],
                        role=role,
                        auto_groups=auto_groups,
                        is_blocked=is_blocked
                    )
                    result['user'] = user
                else:
                    result['user'] = existing_user
                result['changed'] = True
            else:
                result['user'] = existing_user
        else:
            # Create new user
            if not is_service_user and not email:
                module.fail_json(msg="email is required when creating a regular user")
            
            if not module.check_mode:
                user, _ = api.create_user(
                    email=email,
                    name=name,
                    role=role,
                    auto_groups=auto_groups,
                    is_service_user=is_service_user
                )
                result['user'] = user
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



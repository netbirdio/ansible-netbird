#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird posture checks."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_posture_check
short_description: Manage NetBird posture checks
description:
  - Create, update, and delete posture checks in NetBird.
  - Posture checks define security requirements for peers.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the posture check.
    type: str
    choices: ['present', 'absent']
    default: present
  check_id:
    description:
      - The unique identifier of the posture check.
      - Required when state is absent or when updating by ID.
    type: str
  name:
    description:
      - Name of the posture check.
      - Required when creating a new posture check.
    type: str
  description:
    description:
      - Description of the posture check.
    type: str
    default: ''
  checks:
    description:
      - Dictionary of check configurations.
      - Supports various check types like nb_version_check, os_version_check, etc.
    type: dict
    suboptions:
      nb_version_check:
        description:
          - NetBird version check configuration.
        type: dict
        suboptions:
          min_version:
            description:
              - Minimum required NetBird version.
            type: str
      os_version_check:
        description:
          - Operating system version check configuration.
        type: dict
        suboptions:
          android:
            description:
              - Android version configuration.
            type: dict
          darwin:
            description:
              - macOS version configuration.
            type: dict
          ios:
            description:
              - iOS version configuration.
            type: dict
          linux:
            description:
              - Linux version configuration.
            type: dict
          windows:
            description:
              - Windows version configuration.
            type: dict
      geo_location_check:
        description:
          - Geo-location check configuration.
        type: dict
        suboptions:
          locations:
            description:
              - List of allowed locations.
            type: list
            elements: dict
          action:
            description:
              - Action to take (allow or deny).
            type: str
      peer_network_range_check:
        description:
          - Peer network range check configuration.
        type: dict
        suboptions:
          ranges:
            description:
              - List of allowed IP ranges.
            type: list
            elements: str
          action:
            description:
              - Action to take (allow or deny).
            type: str
      process_check:
        description:
          - Process check configuration.
        type: dict
        suboptions:
          processes:
            description:
              - List of processes to check.
            type: list
            elements: dict
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a NetBird version check
  community.ansible_netbird.netbird_posture_check:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "minimum-version"
    description: "Require minimum NetBird version"
    checks:
      nb_version_check:
        min_version: "0.25.0"
    state: present

- name: Create a geo-location check
  community.ansible_netbird.netbird_posture_check:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "allowed-countries"
    description: "Only allow connections from specific countries"
    checks:
      geo_location_check:
        locations:
          - country_code: "US"
          - country_code: "DE"
          - country_code: "GB"
        action: "allow"
    state: present

- name: Create a network range check
  community.ansible_netbird.netbird_posture_check:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "office-networks"
    description: "Only allow connections from office networks"
    checks:
      peer_network_range_check:
        ranges:
          - "172.16.0.0/16"
          - "192.168.0.0/16"
        action: "allow"
    state: present

- name: Create an OS version check
  community.ansible_netbird.netbird_posture_check:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "os-requirements"
    description: "Minimum OS version requirements"
    checks:
      os_version_check:
        darwin:
          min_version: "13.0"
        windows:
          min_kernel_version: "10.0"
    state: present

- name: Delete a posture check
  community.ansible_netbird.netbird_posture_check:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    check_id: "check-id-123"
    state: absent
'''

RETURN = r'''
posture_check:
  description: The posture check object.
  returned: success
  type: dict
  contains:
    id:
      description: Posture check ID.
      type: str
    name:
      description: Posture check name.
      type: str
    description:
      description: Posture check description.
      type: str
    checks:
      description: Check configurations.
      type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    netbird_argument_spec
)


def find_posture_check_by_name(api, name):
    """Find a posture check by name."""
    checks, _ = api.list_posture_checks()
    for check in (checks or []):
        if check.get('name') == name:
            return check
    return None


def normalize_checks(checks):
    """Normalize checks dict for comparison, removing None/null entries."""
    if not checks:
        return {}
    return {k: v for k, v in checks.items() if v is not None}


def posture_check_needs_update(current, params):
    """Check if posture check needs to be updated."""
    if params.get('name') is not None and current.get('name') != params['name']:
        return True
    if params.get('description') is not None:
        if (current.get('description') or '') != (params['description'] or ''):
            return True
    if params.get('checks') is not None:
        if normalize_checks(current.get('checks')) != normalize_checks(params['checks']):
            return True
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        check_id=dict(type='str'),
        name=dict(type='str'),
        description=dict(type='str', default=''),
        checks=dict(type='dict')
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[
            ('check_id', 'name'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    check_id = module.params['check_id']
    name = module.params['name']
    description = module.params['description']
    checks = module.params['checks']

    result = dict(
        changed=False,
        posture_check={}
    )

    try:
        # Find existing posture check
        existing_check = None
        if check_id:
            try:
                existing_check, _ = api.get_posture_check(check_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_check = find_posture_check_by_name(api, name)

        if state == 'absent':
            if existing_check:
                if not module.check_mode:
                    api.delete_posture_check(existing_check['id'])
                result['changed'] = True
                result['msg'] = 'Posture check deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_check:
            # Check if update is needed
            update_params = {
                'name': name,
                'description': description,
                'checks': checks
            }
            
            if posture_check_needs_update(existing_check, update_params):
                if not module.check_mode:
                    posture_check, _ = api.update_posture_check(
                        existing_check['id'],
                        name=name,
                        description=description,
                        checks=checks
                    )
                    result['posture_check'] = posture_check
                else:
                    result['posture_check'] = existing_check
                result['changed'] = True
            else:
                result['posture_check'] = existing_check
        else:
            # Create new posture check
            if not name:
                module.fail_json(msg="name is required when creating a new posture check")
            
            if not module.check_mode:
                posture_check, _ = api.create_posture_check(
                    name=name,
                    description=description,
                    checks=checks or {}
                )
                result['posture_check'] = posture_check
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



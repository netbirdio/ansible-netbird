#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for gathering NetBird information."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_info
short_description: Gather information about NetBird resources
description:
  - Gather information about various NetBird resources.
  - Useful for dynamic inventory or gathering facts.
version_added: "1.0.0"
author:
  - Community
options:
  resource:
    description:
      - Type of resource to gather information about.
    type: str
    choices: ['accounts', 'users', 'peers', 'groups', 'setup_keys', 'policies',
              'networks', 'routes', 'dns_nameservers', 'dns_settings',
              'posture_checks', 'events', 'countries', 'current_user',
              'identity_providers', 'invites']
    required: true
  service_user:
    description:
      - Filter users by service user type.
      - Only applicable when resource is 'users'.
    type: bool
  country_code:
    description:
      - Country code for listing cities.
      - Only applicable when resource is 'cities'.
    type: str
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Get all peers
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: peers
  register: peers_info

- name: Get all groups
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: groups
  register: groups_info

- name: Get all service users
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: users
    service_user: true
  register: service_users_info

- name: Get current user info
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: current_user
  register: current_user_info

- name: Get all policies
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: policies
  register: policies_info

- name: Get DNS settings
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: dns_settings
  register: dns_settings

- name: Get all events
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: events
  register: events_info

- name: Get available countries for geo-location
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: countries
  register: countries_info
'''

RETURN = r'''
data:
  description: The requested information.
  returned: success
  type: raw
  sample: 
    - id: "peer-123"
      name: "my-server"
      ip: "100.64.0.1"
count:
  description: Number of items returned (for list resources).
  returned: success
  type: int
  sample: 5
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    netbird_argument_spec
)


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        resource=dict(
            type='str',
            required=True,
            choices=['accounts', 'users', 'peers', 'groups', 'setup_keys',
                     'policies', 'networks', 'routes', 'dns_nameservers',
                     'dns_settings', 'posture_checks', 'events', 'countries',
                     'current_user', 'identity_providers', 'invites']
        ),
        service_user=dict(type='bool'),
        country_code=dict(type='str')
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    resource = module.params['resource']

    result = dict(
        changed=False,
        data=None
    )

    try:
        # Map resource types to API methods
        if resource == 'accounts':
            data, _ = api.list_accounts()
        elif resource == 'users':
            service_user = module.params.get('service_user')
            data, _ = api.list_users(service_user=service_user)
        elif resource == 'current_user':
            data, _ = api.get_current_user()
        elif resource == 'peers':
            data, _ = api.list_peers()
        elif resource == 'groups':
            data, _ = api.list_groups()
        elif resource == 'setup_keys':
            data, _ = api.list_setup_keys()
        elif resource == 'policies':
            data, _ = api.list_policies()
        elif resource == 'networks':
            data, _ = api.list_networks()
        elif resource == 'routes':
            data, _ = api.list_routes()
        elif resource == 'dns_nameservers':
            data, _ = api.list_nameserver_groups()
        elif resource == 'dns_settings':
            data, _ = api.get_dns_settings()
        elif resource == 'posture_checks':
            data, _ = api.list_posture_checks()
        elif resource == 'events':
            data, _ = api.list_events()
        elif resource == 'countries':
            data, _ = api.list_countries()
        elif resource == 'identity_providers':
            data, _ = api.list_identity_providers()
        elif resource == 'invites':
            data, _ = api.list_user_invites()
        else:
            module.fail_json(msg=f"Unknown resource type: {resource}")

        result['data'] = data
        
        # Add count for list resources
        if isinstance(data, list):
            result['count'] = len(data)

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



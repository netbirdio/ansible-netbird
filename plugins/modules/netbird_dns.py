#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird DNS settings and nameserver groups."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_dns
short_description: Manage NetBird DNS settings and nameserver groups
description:
  - Manage DNS settings and nameserver groups in NetBird.
  - Can update global DNS settings or manage nameserver groups.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the DNS resource.
    type: str
    choices: ['present', 'absent']
    default: present
  resource_type:
    description:
      - Type of DNS resource to manage.
    type: str
    choices: ['settings', 'nameserver_group']
    default: nameserver_group
  nsgroup_id:
    description:
      - The unique identifier of the nameserver group.
      - Required when resource_type is nameserver_group and state is absent.
    type: str
  name:
    description:
      - Name of the nameserver group.
      - Required when creating a new nameserver group.
    type: str
  description:
    description:
      - Description of the nameserver group.
    type: str
    default: ''
  nameservers:
    description:
      - List of nameserver objects.
      - Each nameserver should have 'ip', 'ns_type' (udp/tcp), and 'port'.
    type: list
    elements: dict
    suboptions:
      ip:
        description:
          - IP address of the nameserver.
        type: str
        required: true
      ns_type:
        description:
          - Protocol type (udp or tcp).
        type: str
        default: udp
      port:
        description:
          - Port number.
        type: int
        default: 53
  groups:
    description:
      - List of group IDs that should use this nameserver group.
    type: list
    elements: str
    default: []
  domains:
    description:
      - List of domains for the nameserver group.
    type: list
    elements: str
    default: []
  enabled:
    description:
      - Whether the nameserver group is enabled.
    type: bool
    default: true
  primary:
    description:
      - Whether this is a primary nameserver group.
    type: bool
    default: false
  search_domains_enabled:
    description:
      - Whether search domains are enabled.
    type: bool
    default: true
  disabled_management_groups:
    description:
      - List of group IDs to disable DNS management for.
      - Only used when resource_type is settings.
    type: list
    elements: str
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a nameserver group
  community.ansible_netbird.netbird_dns:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource_type: nameserver_group
    name: "corporate-dns"
    description: "Corporate DNS servers"
    nameservers:
      - ip: "10.0.0.53"
        ns_type: "udp"
        port: 53
      - ip: "10.0.0.54"
        ns_type: "udp"
        port: 53
    groups:
      - "all-peers-group-id"
    domains:
      - "corp.example.com"
    enabled: true
    primary: false
    state: present

- name: Create a primary DNS nameserver group
  community.ansible_netbird.netbird_dns:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource_type: nameserver_group
    name: "primary-dns"
    nameservers:
      - ip: "8.8.8.8"
        ns_type: "udp"
        port: 53
      - ip: "8.8.4.4"
        ns_type: "udp"
        port: 53
    groups:
      - "all-peers-group-id"
    primary: true
    state: present

- name: Update DNS settings
  community.ansible_netbird.netbird_dns:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource_type: settings
    disabled_management_groups:
      - "special-group-id"
    state: present

- name: Delete a nameserver group
  community.ansible_netbird.netbird_dns:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource_type: nameserver_group
    nsgroup_id: "nsgroup-id-123"
    state: absent
'''

RETURN = r'''
dns_settings:
  description: The DNS settings object (when resource_type is settings).
  returned: success and resource_type is settings
  type: dict
  contains:
    disabled_management_groups:
      description: List of group IDs with disabled DNS management.
      type: list
nameserver_group:
  description: The nameserver group object (when resource_type is nameserver_group).
  returned: success and resource_type is nameserver_group
  type: dict
  contains:
    id:
      description: Nameserver group ID.
      type: str
    name:
      description: Nameserver group name.
      type: str
    description:
      description: Nameserver group description.
      type: str
    nameservers:
      description: List of nameservers.
      type: list
    groups:
      description: List of group IDs.
      type: list
    domains:
      description: List of domains.
      type: list
    enabled:
      description: Whether the group is enabled.
      type: bool
    primary:
      description: Whether this is a primary group.
      type: bool
    search_domains_enabled:
      description: Whether search domains are enabled.
      type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    netbird_argument_spec
)


def find_nsgroup_by_name(api, name):
    """Find a nameserver group by name."""
    groups, _ = api.list_nameserver_groups()
    for group in groups:
        if group.get('name') == name:
            return group
    return None


def nsgroup_needs_update(current, params):
    """Check if nameserver group needs to be updated."""
    check_fields = ['name', 'description', 'enabled', 'primary', 'search_domains_enabled']
    for field in check_fields:
        if params.get(field) is not None and current.get(field) != params[field]:
            return True
    
    # Check nameservers
    if params.get('nameservers') is not None:
        return True  # Always update if nameservers provided
    
    # Check groups
    if params.get('groups') is not None:
        current_groups = set(extract_ids(current.get('groups') or []))
        desired_groups = set(extract_ids(params['groups'] or []))
        if current_groups != desired_groups:
            return True
    
    # Check domains
    if params.get('domains') is not None:
        current_domains = set(current.get('domains', []))
        desired_domains = set(params['domains'])
        if current_domains != desired_domains:
            return True
    
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        resource_type=dict(type='str', choices=['settings', 'nameserver_group'], default='nameserver_group'),
        nsgroup_id=dict(type='str'),
        name=dict(type='str'),
        description=dict(type='str', default=''),
        nameservers=dict(type='list', elements='dict'),
        groups=dict(type='list', elements='str', default=[]),
        domains=dict(type='list', elements='str', default=[]),
        enabled=dict(type='bool', default=True),
        primary=dict(type='bool', default=False),
        search_domains_enabled=dict(type='bool', default=True),
        disabled_management_groups=dict(type='list', elements='str')
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

    state = module.params['state']
    resource_type = module.params['resource_type']

    result = dict(
        changed=False
    )

    try:
        if resource_type == 'settings':
            # Handle DNS settings
            current_settings, _ = api.get_dns_settings()
            
            if state == 'present':
                disabled_groups = module.params['disabled_management_groups']
                if disabled_groups is not None:
                    current_disabled = set(extract_ids(current_settings.get('disabled_management_groups') or []))
                    desired_disabled = set(extract_ids(disabled_groups or []))
                    
                    if current_disabled != desired_disabled:
                        if not module.check_mode:
                            settings, _ = api.update_dns_settings(
                                disabled_management_groups=disabled_groups
                            )
                            result['dns_settings'] = settings
                        else:
                            result['dns_settings'] = current_settings
                        result['changed'] = True
                    else:
                        result['dns_settings'] = current_settings
                else:
                    result['dns_settings'] = current_settings
            
            module.exit_json(**result)

        # Handle nameserver groups
        nsgroup_id = module.params['nsgroup_id']
        name = module.params['name']

        # Find existing nameserver group
        existing_group = None
        if nsgroup_id:
            try:
                existing_group, _ = api.get_nameserver_group(nsgroup_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_group = find_nsgroup_by_name(api, name)

        if state == 'absent':
            if existing_group:
                if not module.check_mode:
                    api.delete_nameserver_group(existing_group['id'])
                result['changed'] = True
                result['msg'] = 'Nameserver group deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_group:
            # Check if update is needed
            update_params = {
                'name': name,
                'description': module.params['description'],
                'nameservers': module.params['nameservers'],
                'groups': module.params['groups'],
                'domains': module.params['domains'],
                'enabled': module.params['enabled'],
                'primary': module.params['primary'],
                'search_domains_enabled': module.params['search_domains_enabled']
            }
            
            if nsgroup_needs_update(existing_group, update_params):
                if not module.check_mode:
                    group, _ = api.update_nameserver_group(
                        existing_group['id'],
                        name=name,
                        nameservers=module.params['nameservers'],
                        description=module.params['description'],
                        groups=module.params['groups'],
                        domains=module.params['domains'],
                        enabled=module.params['enabled'],
                        primary=module.params['primary'],
                        search_domains_enabled=module.params['search_domains_enabled']
                    )
                    result['nameserver_group'] = group
                else:
                    result['nameserver_group'] = existing_group
                result['changed'] = True
            else:
                result['nameserver_group'] = existing_group
        else:
            # Create new nameserver group
            if not name:
                module.fail_json(msg="name is required when creating a new nameserver group")
            if not module.params['nameservers']:
                module.fail_json(msg="nameservers is required when creating a new nameserver group")
            
            if not module.check_mode:
                group, _ = api.create_nameserver_group(
                    name=name,
                    nameservers=module.params['nameservers'],
                    description=module.params['description'],
                    groups=module.params['groups'],
                    domains=module.params['domains'],
                    enabled=module.params['enabled'],
                    primary=module.params['primary'],
                    search_domains_enabled=module.params['search_domains_enabled']
                )
                result['nameserver_group'] = group
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



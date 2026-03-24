#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird accounts."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_account
short_description: Manage NetBird account settings
description:
  - Update account settings in NetBird.
  - Configure peer login expiration, JWT settings, and other account-wide settings.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the account.
    type: str
    choices: ['present', 'absent']
    default: present
  account_id:
    description:
      - The unique identifier of the account.
      - If not provided, the first account will be used.
    type: str
  peer_login_expiration_enabled:
    description:
      - Enable or disable peer login expiration globally.
    type: bool
  peer_login_expiration:
    description:
      - Period of time after which peer login expires (seconds).
    type: int
  peer_inactivity_expiration_enabled:
    description:
      - Enable or disable peer inactivity expiration globally.
    type: bool
  peer_inactivity_expiration:
    description:
      - Period of time of inactivity after which peer session expires (seconds).
    type: int
  regular_users_view_blocked:
    description:
      - Block regular users from viewing parts of the system.
    type: bool
  groups_propagation_enabled:
    description:
      - Allow propagation of new user auto groups to peers that belong to the user.
    type: bool
  jwt_groups_enabled:
    description:
      - Allow extracting groups from JWT claims.
    type: bool
  jwt_groups_claim_name:
    description:
      - Name of the claim from which to extract group names.
    type: str
  jwt_allow_groups:
    description:
      - List of groups to which users are allowed access.
    type: list
    elements: str
  routing_peer_dns_resolution_enabled:
    description:
      - Enable or disable DNS resolution on the routing peer.
    type: bool
  dns_domain:
    description:
      - Custom DNS domain for the account.
    type: str
  network_range:
    description:
      - Custom network range for the account in CIDR format.
    type: str
  lazy_connection_enabled:
    description:
      - Enable or disable experimental lazy connection.
    type: bool
  extra_peer_approval_enabled:
    description:
      - Enable or disable peer approval globally.
      - When enabled, all peers added will be in pending state until approved by an admin.
    type: bool
  extra_user_approval_required:
    description:
      - Enable manual approval for new users joining via domain matching.
      - When enabled, users are blocked with pending approval status until approved by an admin.
    type: bool
  extra_network_traffic_logs_enabled:
    description:
      - Enable or disable network traffic logging.
      - When enabled, all network traffic events from peers will be stored.
    type: bool
  extra_network_traffic_logs_groups:
    description:
      - Limits traffic logging to these groups.
      - If empty, all peers are enabled.
    type: list
    elements: str
  extra_network_traffic_packet_counter_enabled:
    description:
      - Enable or disable network traffic packet counter.
      - When enabled, network packets and their size will be counted and reported.
    type: bool
  auto_update_always:
    description:
      - When true, updates are installed automatically in the background.
      - When false, updates require user interaction from the UI.
    type: bool
  auto_update_version:
    description:
      - Set clients auto-update version.
      - Use "latest", "disabled", or a specific version (e.g., "0.50.1").
    type: str
  peer_expose_enabled:
    description:
      - Enable or disable peer expose.
      - When enabled, peers can expose local services through the reverse proxy using the CLI.
    type: bool
  peer_expose_groups:
    description:
      - Limits which peer groups are allowed to expose services.
      - If empty, all peers are allowed when peer expose is enabled.
    type: list
    elements: str
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Enable peer login expiration
  community.ansible_netbird.netbird_account:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    peer_login_expiration_enabled: true
    peer_login_expiration: 86400
    state: present

- name: Configure JWT groups
  community.ansible_netbird.netbird_account:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    jwt_groups_enabled: true
    jwt_groups_claim_name: "groups"
    jwt_allow_groups:
      - "developers"
      - "administrators"
    state: present

- name: Configure custom DNS domain
  community.ansible_netbird.netbird_account:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    dns_domain: "netbird.example.com"
    state: present

- name: Configure peer expiration settings
  community.ansible_netbird.netbird_account:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    peer_login_expiration_enabled: true
    peer_login_expiration: 604800
    peer_inactivity_expiration_enabled: true
    peer_inactivity_expiration: 2592000
    state: present

- name: Delete an account (use with caution)
  community.ansible_netbird.netbird_account:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    account_id: "account-id-123"
    state: absent
'''

RETURN = r'''
account:
  description: The account object.
  returned: success
  type: dict
  contains:
    id:
      description: Account ID.
      type: str
    settings:
      description: Account settings.
      type: dict
      contains:
        peer_login_expiration_enabled:
          description: Whether peer login expiration is enabled.
          type: bool
        peer_login_expiration:
          description: Peer login expiration time in seconds.
          type: int
        peer_inactivity_expiration_enabled:
          description: Whether peer inactivity expiration is enabled.
          type: bool
        peer_inactivity_expiration:
          description: Peer inactivity expiration time in seconds.
          type: int
        regular_users_view_blocked:
          description: Whether regular users view is blocked.
          type: bool
        groups_propagation_enabled:
          description: Whether groups propagation is enabled.
          type: bool
        jwt_groups_enabled:
          description: Whether JWT groups are enabled.
          type: bool
        jwt_groups_claim_name:
          description: JWT groups claim name.
          type: str
        jwt_allow_groups:
          description: JWT allowed groups.
          type: list
        routing_peer_dns_resolution_enabled:
          description: Whether routing peer DNS resolution is enabled.
          type: bool
        dns_domain:
          description: Custom DNS domain.
          type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    netbird_argument_spec
)


def build_settings_update(module):
    """Build the settings update object from module parameters."""
    settings = {}
    
    # Map module parameters to API settings fields
    param_mapping = {
        'peer_login_expiration_enabled': 'peer_login_expiration_enabled',
        'peer_login_expiration': 'peer_login_expiration',
        'peer_inactivity_expiration_enabled': 'peer_inactivity_expiration_enabled',
        'peer_inactivity_expiration': 'peer_inactivity_expiration',
        'regular_users_view_blocked': 'regular_users_view_blocked',
        'groups_propagation_enabled': 'groups_propagation_enabled',
        'jwt_groups_enabled': 'jwt_groups_enabled',
        'jwt_groups_claim_name': 'jwt_groups_claim_name',
        'jwt_allow_groups': 'jwt_allow_groups',
        'routing_peer_dns_resolution_enabled': 'routing_peer_dns_resolution_enabled',
        'dns_domain': 'dns_domain',
        'network_range': 'network_range',
        'lazy_connection_enabled': 'lazy_connection_enabled'
    }
    
    for param, api_field in param_mapping.items():
        value = module.params.get(param)
        if value is not None:
            settings[api_field] = value

    # Build nested extra settings
    extra = {}
    if module.params.get('extra_peer_approval_enabled') is not None:
        extra['peer_approval_enabled'] = module.params['extra_peer_approval_enabled']
    if module.params.get('extra_user_approval_required') is not None:
        extra['user_approval_required'] = module.params['extra_user_approval_required']
    if module.params.get('extra_network_traffic_logs_enabled') is not None:
        extra['network_traffic_logs_enabled'] = module.params['extra_network_traffic_logs_enabled']
    if module.params.get('extra_network_traffic_logs_groups') is not None:
        extra['network_traffic_logs_groups'] = module.params['extra_network_traffic_logs_groups']
    if module.params.get('extra_network_traffic_packet_counter_enabled') is not None:
        extra['network_traffic_packet_counter_enabled'] = module.params['extra_network_traffic_packet_counter_enabled']
    if extra:
        settings['extra'] = extra

    if module.params.get('auto_update_always') is not None:
        settings['auto_update_always'] = module.params['auto_update_always']
    if module.params.get('auto_update_version') is not None:
        settings['auto_update_version'] = module.params['auto_update_version']
    if module.params.get('peer_expose_enabled') is not None:
        settings['peer_expose_enabled'] = module.params['peer_expose_enabled']
    if module.params.get('peer_expose_groups') is not None:
        settings['peer_expose_groups'] = module.params['peer_expose_groups']

    return settings


def settings_need_update(current_settings, desired_settings):
    """Check if account settings need to be updated."""
    for key, value in desired_settings.items():
        if key == 'extra':
            # Compare nested extra settings
            current_extra = current_settings.get('extra', {})
            for extra_key, extra_value in value.items():
                if current_extra.get(extra_key) != extra_value:
                    return True
        elif current_settings.get(key) != value:
            return True
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        account_id=dict(type='str'),
        peer_login_expiration_enabled=dict(type='bool'),
        peer_login_expiration=dict(type='int'),
        peer_inactivity_expiration_enabled=dict(type='bool'),
        peer_inactivity_expiration=dict(type='int'),
        regular_users_view_blocked=dict(type='bool'),
        groups_propagation_enabled=dict(type='bool'),
        jwt_groups_enabled=dict(type='bool'),
        jwt_groups_claim_name=dict(type='str'),
        jwt_allow_groups=dict(type='list', elements='str'),
        routing_peer_dns_resolution_enabled=dict(type='bool'),
        dns_domain=dict(type='str'),
        network_range=dict(type='str'),
        lazy_connection_enabled=dict(type='bool'),
        extra_peer_approval_enabled=dict(type='bool'),
        extra_user_approval_required=dict(type='bool'),
        extra_network_traffic_logs_enabled=dict(type='bool'),
        extra_network_traffic_logs_groups=dict(type='list', elements='str'),
        extra_network_traffic_packet_counter_enabled=dict(type='bool'),
        auto_update_always=dict(type='bool'),
        auto_update_version=dict(type='str'),
        peer_expose_enabled=dict(type='bool'),
        peer_expose_groups=dict(type='list', elements='str')
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
    account_id = module.params['account_id']

    result = dict(
        changed=False,
        account={}
    )

    try:
        # Get accounts
        accounts, _ = api.list_accounts()
        
        if not accounts:
            module.fail_json(msg="No accounts found")
        
        # Use specified account or first one
        if account_id:
            account = None
            for acc in accounts:
                if acc.get('id') == account_id:
                    account = acc
                    break
            if not account:
                module.fail_json(msg=f"Account {account_id} not found")
        else:
            account = accounts[0]
            account_id = account['id']

        if state == 'absent':
            if not module.check_mode:
                api.delete_account(account_id)
            result['changed'] = True
            result['msg'] = 'Account deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        desired_settings = build_settings_update(module)
        
        if desired_settings:
            current_settings = account.get('settings', {})
            
            if settings_need_update(current_settings, desired_settings):
                if not module.check_mode:
                    # Build full settings update
                    update_data = {
                        'settings': {**current_settings, **desired_settings}
                    }
                    updated_account, _ = api.update_account(account_id, update_data)
                    result['account'] = updated_account
                else:
                    result['account'] = account
                result['changed'] = True
            else:
                result['account'] = account
        else:
            result['account'] = account

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



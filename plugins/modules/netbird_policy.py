#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird policies."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_policy
short_description: Manage NetBird policies
description:
  - Create, update, and delete policies in NetBird.
  - Policies define network access rules between groups.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the policy.
    type: str
    choices: ['present', 'absent']
    default: present
  policy_id:
    description:
      - The unique identifier of the policy.
      - Required when state is absent or when updating by ID.
    type: str
  name:
    description:
      - Name of the policy.
      - Required when creating a new policy.
    type: str
  description:
    description:
      - Description of the policy.
    type: str
    default: ''
  enabled:
    description:
      - Whether the policy is enabled.
    type: bool
    default: true
  source_posture_checks:
    description:
      - List of posture check IDs applied to policy source groups.
    type: list
    elements: str
  rules:
    description:
      - List of policy rules.
      - Each rule defines traffic flow between source and destination groups.
    type: list
    elements: dict
    suboptions:
      name:
        description:
          - Name of the rule.
        type: str
      description:
        description:
          - Description of the rule.
        type: str
      enabled:
        description:
          - Whether the rule is enabled.
        type: bool
        default: true
      sources:
        description:
          - List of source group IDs.
        type: list
        elements: str
      destinations:
        description:
          - List of destination group IDs.
        type: list
        elements: str
      bidirectional:
        description:
          - Whether traffic flows both ways.
        type: bool
        default: true
      protocol:
        description:
          - Network protocol (all, tcp, udp, icmp, netbird-ssh).
        type: str
        default: all
      ports:
        description:
          - List of destination ports (e.g., ["80", "443", "8000-9000"]).
        type: list
        elements: str
      port_ranges:
        description:
          - List of port ranges.
          - Each range has start and end port numbers.
        type: list
        elements: dict
        suboptions:
          start:
            description:
              - Start port number.
            type: int
            required: true
          end:
            description:
              - End port number.
            type: int
            required: true
      destination_resource:
        description:
          - Destination network resource for the rule.
        type: dict
        suboptions:
          id:
            description:
              - Resource ID.
            type: str
            required: true
          type:
            description:
              - Resource type.
            type: str
            required: true
      source_resource:
        description:
          - Source network resource for the rule.
        type: dict
        suboptions:
          id:
            description:
              - Resource ID.
            type: str
            required: true
          type:
            description:
              - Resource type.
            type: str
            required: true
      action:
        description:
          - Action to take (accept, drop).
        type: str
        default: accept
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a policy allowing all traffic between groups
  community.ansible_netbird.netbird_policy:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "Allow developers to production"
    description: "Developers can access production servers"
    enabled: true
    rules:
      - name: "developers-to-production"
        sources:
          - "developers-group-id"
        destinations:
          - "production-group-id"
        bidirectional: false
        protocol: "all"
        action: "accept"
    state: present

- name: Create a policy with specific ports
  community.ansible_netbird.netbird_policy:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "Web traffic only"
    rules:
      - name: "http-https"
        sources:
          - "clients-group-id"
        destinations:
          - "webservers-group-id"
        protocol: "tcp"
        ports:
          - "80"
          - "443"
        action: "accept"
    state: present

- name: Disable a policy
  community.ansible_netbird.netbird_policy:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    policy_id: "policy-id-123"
    enabled: false
    state: present

- name: Delete a policy
  community.ansible_netbird.netbird_policy:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    policy_id: "policy-id-123"
    state: absent
'''

RETURN = r'''
policy:
  description: The policy object.
  returned: success
  type: dict
  contains:
    id:
      description: Policy ID.
      type: str
    name:
      description: Policy name.
      type: str
    description:
      description: Policy description.
      type: str
    enabled:
      description: Whether policy is enabled.
      type: bool
    rules:
      description: List of policy rules.
      type: list
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    netbird_argument_spec
)


def find_policy_by_name(api, name):
    """Find a policy by name."""
    policies, _ = api.list_policies()
    for policy in (policies or []):
        if policy.get('name') == name:
            return policy
    return None


def build_rule_data(rule):
    """Build rule payload for the API from Ansible rule config."""
    rule_data = {}
    if rule.get('name') is not None:
        rule_data['name'] = rule['name']
    if rule.get('description') is not None:
        rule_data['description'] = rule['description']
    if rule.get('enabled') is not None:
        rule_data['enabled'] = rule['enabled']
    if rule.get('sources') is not None:
        rule_data['sources'] = rule['sources']
    if rule.get('destinations') is not None:
        rule_data['destinations'] = rule['destinations']
    if rule.get('bidirectional') is not None:
        rule_data['bidirectional'] = rule['bidirectional']
    if rule.get('protocol') is not None:
        rule_data['protocol'] = rule['protocol']
    if rule.get('ports') is not None:
        rule_data['ports'] = rule['ports']
    if rule.get('port_ranges') is not None:
        rule_data['port_ranges'] = rule['port_ranges']
    if rule.get('destination_resource') is not None:
        rule_data['destinationResource'] = rule['destination_resource']
    if rule.get('source_resource') is not None:
        rule_data['sourceResource'] = rule['source_resource']
    if rule.get('action') is not None:
        rule_data['action'] = rule['action']
    return rule_data


def build_rules_data(rules):
    """Build list of rule payloads for the API."""
    if rules is None:
        return None
    return [build_rule_data(rule) for rule in rules]


def normalize_rule(rule):
    """Normalize a rule for comparison, extracting IDs from any dict references."""
    return {
        'name': rule.get('name', ''),
        'description': rule.get('description', ''),
        'enabled': rule.get('enabled', True),
        'sources': sorted(extract_ids(rule.get('sources') or [])),
        'destinations': sorted(extract_ids(rule.get('destinations') or [])),
        'bidirectional': rule.get('bidirectional', True),
        'protocol': rule.get('protocol', 'all'),
        'ports': sorted(rule.get('ports') or []),
        'action': rule.get('action', 'accept'),
    }


def rules_need_update(current_rules, desired_rules):
    """Check if rules need to be updated by comparing normalized representations."""
    current_rules = current_rules or []
    desired_rules = desired_rules or []
    if len(current_rules) != len(desired_rules):
        return True
    for current, desired in zip(
        sorted(current_rules, key=lambda r: r.get('name', '')),
        sorted(desired_rules, key=lambda r: r.get('name', ''))
    ):
        if normalize_rule(current) != normalize_rule(desired):
            return True
    return False


def policy_needs_update(current, params):
    """Check if policy needs to be updated."""
    if params.get('name') is not None and current.get('name') != params['name']:
        return True
    if params.get('description') is not None:
        if (current.get('description') or '') != (params['description'] or ''):
            return True
    if params.get('enabled') is not None and current.get('enabled') != params['enabled']:
        return True
    if params.get('source_posture_checks') is not None:
        current_checks = set(extract_ids(current.get('source_posture_checks') or []))
        desired_checks = set(extract_ids(params['source_posture_checks'] or []))
        if current_checks != desired_checks:
            return True
    if params.get('rules') is not None:
        if rules_need_update(current.get('rules'), params['rules']):
            return True
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        policy_id=dict(type='str'),
        name=dict(type='str'),
        description=dict(type='str', default=''),
        enabled=dict(type='bool', default=True),
        source_posture_checks=dict(type='list', elements='str'),
        rules=dict(type='list', elements='dict', options=dict(
            name=dict(type='str'),
            description=dict(type='str'),
            enabled=dict(type='bool', default=True),
            sources=dict(type='list', elements='str'),
            destinations=dict(type='list', elements='str'),
            bidirectional=dict(type='bool', default=True),
            protocol=dict(type='str', default='all'),
            ports=dict(type='list', elements='str'),
            port_ranges=dict(type='list', elements='dict', options=dict(
                start=dict(type='int', required=True),
                end=dict(type='int', required=True)
            )),
            destination_resource=dict(type='dict', options=dict(
                id=dict(type='str', required=True),
                type=dict(type='str', required=True)
            )),
            source_resource=dict(type='dict', options=dict(
                id=dict(type='str', required=True),
                type=dict(type='str', required=True)
            )),
            action=dict(type='str', default='accept')
        ))
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[
            ('policy_id', 'name'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    policy_id = module.params['policy_id']
    name = module.params['name']
    description = module.params['description']
    enabled = module.params['enabled']
    source_posture_checks = module.params['source_posture_checks']
    rules = build_rules_data(module.params['rules'])

    result = dict(
        changed=False,
        policy={}
    )

    try:
        # Find existing policy
        existing_policy = None
        if policy_id:
            try:
                existing_policy, _ = api.get_policy(policy_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_policy = find_policy_by_name(api, name)

        if state == 'absent':
            if existing_policy:
                if not module.check_mode:
                    api.delete_policy(existing_policy['id'])
                result['changed'] = True
                result['msg'] = 'Policy deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_policy:
            # Check if update is needed
            update_params = {
                'name': name,
                'description': description,
                'enabled': enabled,
                'source_posture_checks': source_posture_checks,
                'rules': rules
            }
            
            if policy_needs_update(existing_policy, update_params):
                if not module.check_mode:
                    policy, _ = api.update_policy(
                        existing_policy['id'],
                        name=name,
                        enabled=enabled,
                        description=description,
                        rules=rules,
                        source_posture_checks=source_posture_checks
                    )
                    result['policy'] = policy
                else:
                    result['policy'] = existing_policy
                result['changed'] = True
            else:
                result['policy'] = existing_policy
        else:
            # Create new policy
            if not name:
                module.fail_json(msg="name is required when creating a new policy")
            
            if not module.check_mode:
                policy, _ = api.create_policy(
                    name=name,
                    enabled=enabled,
                    description=description,
                    rules=rules or [],
                    source_posture_checks=source_posture_checks
                )
                result['policy'] = policy
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



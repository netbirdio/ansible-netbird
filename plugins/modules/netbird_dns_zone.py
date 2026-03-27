#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird DNS zones."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_dns_zone
short_description: Manage NetBird DNS zones with records
description:
  - Create, update, and delete DNS zones in NetBird.
  - Manage DNS records within zones (A, AAAA, CNAME).
  - Zones are matched by name. Records within a zone are matched by name + type.
version_added: "1.1.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the DNS zone.
    type: str
    choices: ['present', 'absent']
    default: present
  zone_id:
    description:
      - The unique identifier of the DNS zone.
      - Required when state is absent or when updating by ID.
    type: str
  name:
    description:
      - The DNS zone name (descriptive label, e.g., "Office Zone").
      - Used to identify the zone. Required when creating a new zone.
    type: str
  domain:
    description:
      - The DNS zone domain (FQDN, e.g., "example.com").
      - Required when creating a new zone.
    type: str
  enabled:
    description:
      - Whether the DNS zone is active.
    type: bool
    default: true
  enable_search_domain:
    description:
      - Whether to use this zone as a search domain.
    type: bool
    default: false
  distribution_groups:
    description:
      - List of distribution group IDs that receive this zone's DNS records.
    type: list
    elements: str
    default: []
  records:
    description:
      - List of DNS records for this zone.
      - Records are matched by name + type combination.
      - Records not in this list will be removed from the zone.
      - Set to empty list to remove all records.
      - Omit to leave existing records unchanged.
    type: list
    elements: dict
    suboptions:
      name:
        description:
          - Record FQDN. Must be a subdomain within or match the zone domain.
        type: str
        required: true
      type:
        description:
          - DNS record type.
        type: str
        choices: ['A', 'AAAA', 'CNAME']
        required: true
      content:
        description:
          - DNS record content (IP address for A/AAAA, domain for CNAME).
        type: str
        required: true
      ttl:
        description:
          - Time to live in seconds.
        type: int
        default: 300
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create a DNS zone
  community.ansible_netbird.netbird_dns_zone:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "Office Zone"
    domain: "office.example.com"
    enabled: true
    distribution_groups:
      - "all-users-group-id"
    records:
      - name: "server1.office.example.com"
        type: "A"
        content: "10.0.1.1"
        ttl: 300
      - name: "mail.office.example.com"
        type: "CNAME"
        content: "mailserver.example.com"
    state: present

- name: Disable a DNS zone
  community.ansible_netbird.netbird_dns_zone:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "Office Zone"
    enabled: false
    state: present

- name: Delete a DNS zone
  community.ansible_netbird.netbird_dns_zone:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "Office Zone"
    state: absent
'''

RETURN = r'''
zone:
  description: The DNS zone object.
  returned: success
  type: dict
  contains:
    id:
      description: Zone ID.
      type: str
    name:
      description: Zone name (label).
      type: str
    domain:
      description: Zone domain (FQDN).
      type: str
    enabled:
      description: Whether the zone is active.
      type: bool
    enable_search_domain:
      description: Whether the zone is a search domain.
      type: bool
    distribution_groups:
      description: List of distribution group IDs.
      type: list
    records:
      description: List of DNS records.
      type: list
      elements: dict
records_changed:
  description: Whether any records were modified.
  returned: success
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    netbird_argument_spec
)


def find_zone_by_name(api, name):
    """Find a DNS zone by name."""
    zones, _ = api.list_dns_zones()
    for zone in zones:
        if zone.get('name') == name:
            return zone
    return None


def zone_needs_update(current, params):
    """Check if zone metadata needs to be updated."""
    if params.get('name') is not None and current.get('name') != params['name']:
        return True
    if params.get('domain') is not None and current.get('domain') != params['domain']:
        return True
    if params.get('enabled') is not None and current.get('enabled') != params['enabled']:
        return True
    if params.get('enable_search_domain') is not None and current.get('enable_search_domain') != params['enable_search_domain']:
        return True
    if params.get('distribution_groups') is not None:
        current_groups = set(extract_ids(current.get('distribution_groups') or []))
        desired_groups = set(extract_ids(params['distribution_groups'] or []))
        if current_groups != desired_groups:
            return True
    return False


def get_record_key(record):
    """Generate a unique key for a record based on name + type."""
    return (record.get('name', ''), record.get('type', ''))


def record_needs_update(current, desired):
    """Check if a record needs to be updated."""
    if current.get('content', '') != desired.get('content', ''):
        return True
    if current.get('ttl', 300) != desired.get('ttl', 300):
        return True
    return False


def sync_records(api, module, zone_id, desired_records):
    """Synchronize records for a DNS zone. Returns (changed, records_list)."""
    changed = False

    # Get current records
    current_records, _ = api.list_dns_zone_records(zone_id)
    current_by_key = {get_record_key(r): r for r in current_records}

    # Build desired records map
    desired_by_key = {}
    for record in desired_records:
        key = get_record_key(record)
        desired_by_key[key] = record

    final_records = []

    # Create or update records
    for key, desired in desired_by_key.items():
        name, record_type = key

        if key in current_by_key:
            current = current_by_key[key]
            if record_needs_update(current, desired):
                if not module.check_mode:
                    updated, _ = api.update_dns_zone_record(
                        zone_id,
                        current['id'],
                        name=name,
                        record_type=record_type,
                        content=desired.get('content'),
                        ttl=desired.get('ttl', 300)
                    )
                    final_records.append(updated)
                else:
                    final_records.append(current)
                changed = True
            else:
                final_records.append(current)
        else:
            # Create new record
            if not module.check_mode:
                new_record, _ = api.create_dns_zone_record(
                    zone_id,
                    name=name,
                    record_type=record_type,
                    content=desired.get('content', ''),
                    ttl=desired.get('ttl', 300)
                )
                final_records.append(new_record)
            changed = True

    # Delete records not in desired list
    for key, current in current_by_key.items():
        if key not in desired_by_key:
            if not module.check_mode:
                api.delete_dns_zone_record(zone_id, current['id'])
            changed = True

    return changed, final_records


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        zone_id=dict(type='str'),
        name=dict(type='str'),
        domain=dict(type='str'),
        enabled=dict(type='bool', default=True),
        enable_search_domain=dict(type='bool', default=False),
        distribution_groups=dict(type='list', elements='str', default=[]),
        records=dict(
            type='list',
            elements='dict',
            options=dict(
                name=dict(type='str', required=True),
                type=dict(type='str', required=True,
                          choices=['A', 'AAAA', 'CNAME']),
                content=dict(type='str', required=True),
                ttl=dict(type='int', default=300)
            )
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[
            ('zone_id', 'name'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    zone_id = module.params['zone_id']
    name = module.params['name']
    domain = module.params['domain']
    enabled = module.params['enabled']
    enable_search_domain = module.params['enable_search_domain']
    distribution_groups = module.params['distribution_groups']
    records = module.params['records']

    result = dict(
        changed=False,
        zone={},
        records_changed=False
    )

    try:
        # Find existing zone
        existing_zone = None
        if zone_id:
            try:
                existing_zone, _ = api.get_dns_zone(zone_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_zone = find_zone_by_name(api, name)

        if state == 'absent':
            if existing_zone:
                if not module.check_mode:
                    api.delete_dns_zone(existing_zone['id'])
                result['changed'] = True
                result['msg'] = 'DNS zone deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        zone_changed = False

        if existing_zone:
            current_zone_id = existing_zone['id']

            # Check if zone metadata needs update
            update_params = {
                'name': name,
                'domain': domain,
                'enabled': enabled,
                'enable_search_domain': enable_search_domain,
                'distribution_groups': distribution_groups
            }

            if zone_needs_update(existing_zone, update_params):
                if not module.check_mode:
                    zone, _ = api.update_dns_zone(
                        current_zone_id,
                        name=name,
                        domain=domain,
                        enabled=enabled,
                        distribution_groups=distribution_groups,
                        enable_search_domain=enable_search_domain
                    )
                    result['zone'] = zone
                else:
                    result['zone'] = existing_zone
                zone_changed = True
            else:
                result['zone'] = existing_zone
        else:
            # Create new zone
            if not name:
                module.fail_json(msg="name is required when creating a new DNS zone")
            if not domain:
                module.fail_json(msg="domain is required when creating a new DNS zone")

            if not module.check_mode:
                zone, _ = api.create_dns_zone(
                    name=name,
                    domain=domain,
                    enabled=enabled,
                    distribution_groups=distribution_groups,
                    enable_search_domain=enable_search_domain
                )
                result['zone'] = zone
                current_zone_id = zone['id']
            else:
                result['zone'] = {'name': name, 'domain': domain}
                current_zone_id = None
            zone_changed = True

        # Sync records if provided
        if records is not None and current_zone_id and not module.check_mode:
            records_changed, final_records = sync_records(
                api, module, current_zone_id, records
            )
            result['zone']['records'] = final_records
            result['records_changed'] = records_changed
            if records_changed:
                zone_changed = True
        elif records is not None and module.check_mode:
            result['records_changed'] = True
            zone_changed = True

        result['changed'] = zone_changed
        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(
            msg=f"NetBird API error: {e}",
            status_code=getattr(e, 'status_code', None)
        )


def main():
    run_module()


if __name__ == '__main__':
    main()

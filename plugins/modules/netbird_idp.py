#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird identity providers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_idp
short_description: Manage NetBird identity providers
description:
  - Create, update, and delete identity providers in NetBird.
  - Identity providers are used to authenticate users via OIDC-compatible providers.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the identity provider.
    type: str
    choices: ['present', 'absent']
    default: present
  idp_id:
    description:
      - The unique identifier of the identity provider.
      - Used for update or delete by ID.
    type: str
  name:
    description:
      - Name of the identity provider.
      - Required when state is present.
      - Used for lookup and creation.
    type: str
  type:
    description:
      - The type of identity provider.
      - Required when creating a new identity provider.
    type: str
    choices: ['entra', 'google', 'microsoft', 'oidc', 'okta', 'pocketid', 'zitadel']
  issuer:
    description:
      - The OIDC issuer URL for the identity provider.
      - Required when creating a new identity provider.
    type: str
  client_id:
    description:
      - The OIDC client ID for the identity provider.
      - Required when creating a new identity provider.
    type: str
  client_secret:
    description:
      - The OIDC client secret for the identity provider.
      - Required when creating a new identity provider.
      - This value is write-only and never returned by the API.
    type: str
    no_log: true
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Create an identity provider
  community.ansible_netbird.netbird_idp:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "corporate-okta"
    type: "okta"
    issuer: "https://dev-123456.okta.com"
    client_id: "0oa1b2c3d4e5f6g7h8i9"
    client_secret: "{{ okta_client_secret }}"
    state: present

- name: Update an identity provider by name
  community.ansible_netbird.netbird_idp:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "corporate-okta"
    type: "okta"
    issuer: "https://dev-789012.okta.com"
    client_id: "0oa1b2c3d4e5f6g7h8i9"
    client_secret: "{{ okta_client_secret }}"
    state: present

- name: Delete an identity provider by ID
  community.ansible_netbird.netbird_idp:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    idp_id: "idp-id-123"
    state: absent

- name: Delete an identity provider by name
  community.ansible_netbird.netbird_idp:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "corporate-okta"
    state: absent
'''

RETURN = r'''
identity_provider:
  description: The identity provider object.
  returned: success
  type: dict
  contains:
    id:
      description: Identity provider ID.
      type: str
    name:
      description: Identity provider name.
      type: str
    type:
      description: Identity provider type.
      type: str
    issuer:
      description: OIDC issuer URL.
      type: str
    client_id:
      description: OIDC client ID.
      type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    netbird_argument_spec
)


def find_idp_by_name(api, name):
    """Find an identity provider by name."""
    idps, _ = api.list_identity_providers()
    for idp in (idps or []):
        if idp.get('name') == name:
            return idp
    return None


def idp_needs_update(current, desired):
    """Check if identity provider needs to be updated."""
    if 'name' in desired and desired['name'] is not None:
        if current.get('name') != desired['name']:
            return True

    if 'type' in desired and desired['type'] is not None:
        if current.get('type') != desired['type']:
            return True

    if 'issuer' in desired and desired['issuer'] is not None:
        if current.get('issuer') != desired['issuer']:
            return True

    if 'client_id' in desired and desired['client_id'] is not None:
        if current.get('client_id') != desired['client_id']:
            return True

    # Skip client_secret comparison since it's write-only/never returned by the API

    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        idp_id=dict(type='str'),
        name=dict(type='str'),
        type=dict(type='str', choices=['entra', 'google', 'microsoft', 'oidc', 'okta', 'pocketid', 'zitadel']),
        issuer=dict(type='str'),
        client_id=dict(type='str'),
        client_secret=dict(type='str', no_log=True)
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'present', ['name'], True),
        ],
        required_one_of=[
            ('idp_id', 'name'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    idp_id = module.params['idp_id']
    name = module.params['name']
    idp_type = module.params['type']
    issuer = module.params['issuer']
    client_id = module.params['client_id']
    client_secret = module.params['client_secret']

    result = dict(
        changed=False,
        identity_provider={}
    )

    try:
        # Find existing identity provider
        existing_idp = None
        if idp_id:
            try:
                existing_idp, _ = api.get_identity_provider(idp_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_idp = find_idp_by_name(api, name)

        if state == 'absent':
            if existing_idp:
                if not module.check_mode:
                    api.delete_identity_provider(existing_idp['id'])
                result['changed'] = True
                result['msg'] = 'Identity provider deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_idp:
            # Check if update is needed
            desired = {
                'name': name,
                'type': idp_type,
                'issuer': issuer,
                'client_id': client_id
            }

            if idp_needs_update(existing_idp, desired):
                if not module.check_mode:
                    idp, _ = api.update_identity_provider(
                        existing_idp['id'],
                        name=name,
                        idp_type=idp_type,
                        issuer=issuer,
                        client_id=client_id,
                        client_secret=client_secret
                    )
                    result['identity_provider'] = idp
                else:
                    result['identity_provider'] = existing_idp
                result['changed'] = True
            else:
                result['identity_provider'] = existing_idp
        else:
            # Create new identity provider
            if not name:
                module.fail_json(msg="name is required when creating a new identity provider")

            if not module.check_mode:
                idp, _ = api.create_identity_provider(
                    name=name,
                    idp_type=idp_type,
                    issuer=issuer,
                    client_id=client_id,
                    client_secret=client_secret
                )
                result['identity_provider'] = idp
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()

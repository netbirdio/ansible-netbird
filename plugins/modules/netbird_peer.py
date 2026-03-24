#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird peers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_peer
short_description: Manage NetBird peers
description:
  - Update and delete peers in NetBird.
  - Peers are devices/machines connected to the NetBird network.
  - Note: Peers are registered using setup keys, not created via API.
version_added: "1.0.0"
author:
  - Community
options:
  state:
    description:
      - The desired state of the peer.
    type: str
    choices: ['present', 'absent']
    default: present
  peer_id:
    description:
      - The unique identifier of the peer.
      - Required for all operations.
    type: str
    required: true
  name:
    description:
      - Name of the peer.
    type: str
  ssh_enabled:
    description:
      - Enable or disable SSH access to the peer.
    type: bool
  login_expiration_enabled:
    description:
      - Enable or disable login expiration for the peer.
    type: bool
  inactivity_expiration_enabled:
    description:
      - Enable or disable inactivity expiration for the peer.
    type: bool
  approval_required:
    description:
      - Whether approval is required for the peer.
    type: bool
  ip:
    description:
      - The IP address to assign to the peer within the NetBird network.
      - Allows reassigning a peer's IP.
    type: str
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Update peer name
  community.ansible_netbird.netbird_peer:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    peer_id: "peer-id-123"
    name: "production-server-01"
    state: present

- name: Enable SSH on peer
  community.ansible_netbird.netbird_peer:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    peer_id: "peer-id-123"
    ssh_enabled: true
    state: present

- name: Configure peer expiration settings
  community.ansible_netbird.netbird_peer:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    peer_id: "peer-id-123"
    login_expiration_enabled: true
    inactivity_expiration_enabled: false
    state: present

- name: Delete a peer
  community.ansible_netbird.netbird_peer:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    peer_id: "peer-id-123"
    state: absent
'''

RETURN = r'''
peer:
  description: The peer object.
  returned: success
  type: dict
  contains:
    id:
      description: Peer ID.
      type: str
    name:
      description: Peer name.
      type: str
    ip:
      description: Peer IP address.
      type: str
    connected:
      description: Whether peer is connected.
      type: bool
    last_seen:
      description: Last seen timestamp.
      type: str
    os:
      description: Operating system.
      type: str
    version:
      description: NetBird version.
      type: str
    groups:
      description: Groups the peer belongs to.
      type: list
    ssh_enabled:
      description: Whether SSH is enabled.
      type: bool
    hostname:
      description: Peer hostname.
      type: str
    user_id:
      description: User ID of the peer owner.
      type: str
    ui_version:
      description: UI version.
      type: str
    dns_label:
      description: DNS label.
      type: str
    login_expiration_enabled:
      description: Whether login expiration is enabled.
      type: bool
    login_expired:
      description: Whether login has expired.
      type: bool
    last_login:
      description: Last login timestamp.
      type: str
    inactivity_expiration_enabled:
      description: Whether inactivity expiration is enabled.
      type: bool
    approval_required:
      description: Whether approval is required.
      type: bool
    accessible_peers_count:
      description: Number of accessible peers.
      type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    netbird_argument_spec
)


def peer_needs_update(current, params):
    """Check if peer needs to be updated."""
    for key in ['name', 'ssh_enabled', 'login_expiration_enabled',
                'inactivity_expiration_enabled', 'approval_required', 'ip']:
        if params.get(key) is not None:
            if current.get(key) != params[key]:
                return True
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        peer_id=dict(type='str', required=True),
        name=dict(type='str'),
        ssh_enabled=dict(type='bool'),
        login_expiration_enabled=dict(type='bool'),
        inactivity_expiration_enabled=dict(type='bool'),
        approval_required=dict(type='bool'),
        ip=dict(type='str')
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
    peer_id = module.params['peer_id']

    result = dict(
        changed=False,
        peer={}
    )

    try:
        # Get existing peer
        try:
            existing_peer, _ = api.get_peer(peer_id)
        except NetBirdAPIError as e:
            if e.status_code == 404:
                if state == 'absent':
                    module.exit_json(**result)
                module.fail_json(msg=f"Peer {peer_id} not found")
            raise

        if state == 'absent':
            if not module.check_mode:
                api.delete_peer(peer_id)
            result['changed'] = True
            result['msg'] = 'Peer deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        update_params = {
            'name': module.params['name'],
            'ssh_enabled': module.params['ssh_enabled'],
            'login_expiration_enabled': module.params['login_expiration_enabled'],
            'inactivity_expiration_enabled': module.params['inactivity_expiration_enabled'],
            'approval_required': module.params['approval_required'],
            'ip': module.params['ip']
        }

        if peer_needs_update(existing_peer, update_params):
            if not module.check_mode:
                peer, _ = api.update_peer(
                    peer_id,
                    name=module.params['name'],
                    ssh_enabled=module.params['ssh_enabled'],
                    login_expiration_enabled=module.params['login_expiration_enabled'],
                    inactivity_expiration_enabled=module.params['inactivity_expiration_enabled'],
                    approval_required=module.params['approval_required'],
                    ip=module.params['ip']
                )
                result['peer'] = peer
            else:
                result['peer'] = existing_peer
            result['changed'] = True
        else:
            result['peer'] = existing_peer

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()



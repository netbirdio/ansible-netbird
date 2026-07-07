#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird reverse-proxy services."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_service
short_description: Manage NetBird reverse-proxy services
description:
  - Create, update, and delete reverse-proxy services exposed by a NetBird
    reverse-proxy (Ingress) over the overlay (C(/api/reverse-proxies/services)).
  - A service publishes a domain and forwards to one or more targets that
    reference a network resource (subnet/host) plus a host and port.
  - Services are matched by C(domain), which NetBird treats as unique.
version_added: "1.3.0"
author:
  - dhumpf (@dhumpf)
options:
  state:
    description:
      - The desired state of the service.
    type: str
    choices: ['present', 'absent']
    default: present
  service_id:
    description:
      - The unique identifier of the service.
      - Optional; the module otherwise matches by C(domain).
    type: str
  domain:
    description:
      - Public domain the service is served on (e.g. C(myapp.netbird.example.com)).
      - Required to create a service. When updating an existing service by
        C(service_id), the current domain is reused if this is omitted.
    type: str
  name:
    description:
      - Display name of the service. Defaults to C(domain) when omitted.
    type: str
  mode:
    description:
      - Proxy mode. C(http) is L7; C(tcp)/C(udp)/C(tls) are L4 passthrough.
      - Defaults to C(http) on create; left unchanged if omitted on update.
    type: str
    choices: ['http', 'tcp', 'udp', 'tls']
  private:
    description:
      - Whether the service is NetBird-only (reachable over the overlay only).
      - Private services are http-only and gated by C(access_groups); set false
        for L4 modes (tcp/udp/tls) or to use auth schemes.
      - Defaults to C(true) on create; left unchanged if omitted on update.
    type: bool
  enabled:
    description:
      - Whether the service is enabled.
      - Defaults to C(true) on create; left unchanged if omitted on update.
    type: bool
  listen_port:
    description:
      - Listen port for L4 modes. C(0) lets NetBird auto-assign.
      - Defaults to C(0) on create; left unchanged if omitted on update.
    type: int
  pass_host_header:
    description:
      - Whether to pass the original Host header to the target.
      - Defaults to C(false) on create; left unchanged if omitted on update.
    type: bool
  rewrite_redirects:
    description:
      - Whether to rewrite upstream redirects to the public domain.
      - Defaults to C(false) on create; left unchanged if omitted on update.
    type: bool
  access_groups:
    description:
      - List of group IDs allowed to reach the service.
      - Omit to leave unmanaged; an explicit empty list C([]) clears all groups.
    type: list
    elements: str
  targets:
    description:
      - Backend targets. Matched by C(target_id) plus C(host) and C(port).
      - When set, targets not in the list are removed and an explicit empty
        list C([]) removes all. Omit the option to leave targets unmanaged.
    type: list
    elements: dict
    suboptions:
      host:
        description:
          - Target host (IP or hostname reachable via the referenced resource).
        type: str
        required: true
      port:
        description:
          - Target port.
        type: int
        required: true
      protocol:
        description:
          - Target protocol.
        type: str
        default: http
      target_id:
        description:
          - ID of the NetBird network resource (subnet/host) the target rides.
        type: str
        required: true
      target_type:
        description:
          - Type of the referenced resource.
        type: str
        choices: ['subnet', 'host', 'domain', 'peer']
        default: subnet
      enabled:
        description:
          - Whether the target is enabled.
        type: bool
        default: true
      direct_upstream:
        description:
          - Whether to connect directly to the upstream host.
        type: bool
        default: true
      skip_tls_verify:
        description:
          - Skip verification of the upstream TLS certificate. Use with
            C(protocol=https) when the upstream serves a self-signed cert whose
            SANs do not cover the dialed host.
        type: bool
        default: false
      path:
        description:
          - Match prefix for path-based routing. Multiple targets in one service
            with distinct paths route by longest-prefix match.
        type: str
        default: /
      path_rewrite:
        description:
          - How the matched C(path) maps to the upstream. C(preserve) forwards
            the full request path to the upstream unchanged.
        type: str
        default: preserve
  auth:
    description:
      - Optional authentication in front of the service. Omit to leave the
        existing auth unchanged; set a scheme's C(enabled) to C(false) to disable it.
      - Auth applies to public services only. Private (NetBird-only) services
        are gated by C(access_groups), so auth schemes do not apply to them.
      - The API masks stored secrets, so a change to an already-enabled password
        or PIN value cannot be detected and will not trigger an update.
    type: dict
    suboptions:
      bearer_auth:
        description:
          - Bearer-token (NetBird JWT) authentication.
        type: dict
        suboptions:
          enabled:
            description: Whether bearer auth is enabled.
            type: bool
            default: false
          distribution_groups:
            description: Group IDs the bearer policy applies to.
            type: list
            elements: str
      password_auth:
        description:
          - Shared-password authentication.
        type: dict
        suboptions:
          enabled:
            description: Whether password auth is enabled.
            type: bool
            default: false
          password:
            description: Shared password.
            type: str
            default: ""
      pin_auth:
        description:
          - Shared-PIN authentication.
        type: dict
        suboptions:
          enabled:
            description: Whether PIN auth is enabled.
            type: bool
            default: false
          pin:
            description: Shared PIN.
            type: str
            default: ""
extends_documentation_fragment:
  - community.ansible_netbird.netbird
requirements:
  - python >= 3.6
'''

EXAMPLES = r'''
- name: Expose an internal app over the overlay
  community.ansible_netbird.netbird_service:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    domain: "myapp.netbird.example.com"
    private: true
    access_groups:
      - "all-users-group-id"
    targets:
      - host: "10.0.0.30"
        port: 8080
        protocol: http
        target_id: "subnet-resource-id"
        target_type: subnet
    state: present

- name: Delete a service
  community.ansible_netbird.netbird_service:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    domain: "myapp.netbird.example.com"
    state: absent
'''

RETURN = r'''
service:
  description: The reverse-proxy service object.
  returned: success
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    netbird_argument_spec
)


def find_service_by_domain(api, domain):
    """Find a reverse-proxy service by domain."""
    services, _ = api.list_services()
    for service in (services or []):
        if service.get('domain') == domain:
            return service
    return None


def build_target(target):
    """Build the API payload for a single target."""
    return {
        'target_id': target['target_id'],
        'target_type': target.get('target_type', 'subnet'),
        'host': target['host'],
        'port': target['port'],
        'path': target.get('path', '/'),
        'protocol': target.get('protocol', 'http'),
        'enabled': target.get('enabled', True),
        'options': {
            'direct_upstream': target.get('direct_upstream', True),
            'skip_tls_verify': target.get('skip_tls_verify', False),
            'path_rewrite': target.get('path_rewrite', 'preserve'),
        },
    }


def build_auth(auth, current_auth=None):
    """Build the API auth payload; omitted schemes keep their current value."""
    auth = auth or {}
    current_auth = current_auth or {}

    def _scheme(name, builder, default):
        if auth.get(name) is not None:
            return builder(auth[name])
        if current_auth.get(name) is not None:
            return current_auth[name]
        return default

    return {
        'bearer_auth': _scheme(
            'bearer_auth',
            lambda b: {
                'enabled': b.get('enabled', False),
                'distribution_groups': b.get('distribution_groups') or [],
            },
            {'enabled': False, 'distribution_groups': []},
        ),
        'password_auth': _scheme(
            'password_auth',
            lambda p: {
                'enabled': p.get('enabled', False),
                'password': p.get('password', ''),
            },
            {'enabled': False, 'password': ''},
        ),
        'pin_auth': _scheme(
            'pin_auth',
            lambda n: {
                'enabled': n.get('enabled', False),
                'pin': n.get('pin', ''),
            },
            {'enabled': False, 'pin': ''},
        ),
    }


def build_body(params, domain, current=None):
    """Build the full service payload from module params.

    The API does a full replace on PUT, so any field the caller omits carries
    the current service's value forward instead of being cleared or reset to a
    default. Scalars default only on create; the argspec defaults are dropped so
    an omitted field reads as None here rather than as its default.

    domain is passed in so an update found by service_id can reuse the existing
    domain. current is the existing service, or None on create.
    """
    current = current or {}

    def scalar(field, default):
        val = params.get(field)
        if val is not None:
            return val
        return current.get(field, default)

    body = {
        'domain': domain,
        'name': params.get('name') or current.get('name') or domain,
        'mode': scalar('mode', 'http'),
        'private': scalar('private', True),
        'enabled': scalar('enabled', True),
        'listen_port': scalar('listen_port', 0),
        'pass_host_header': scalar('pass_host_header', False),
        'rewrite_redirects': scalar('rewrite_redirects', False),
    }
    # omitted -> carry current forward; an explicit value (incl. []) wins
    if params.get('access_groups') is not None:
        body['access_groups'] = params['access_groups']
    elif current.get('access_groups') is not None:
        body['access_groups'] = extract_ids(current['access_groups'])
    if params.get('targets') is not None:
        body['targets'] = [build_target(t) for t in params['targets']]
    elif current.get('targets') is not None:
        body['targets'] = current['targets']
    if params.get('auth') is not None:
        body['auth'] = build_auth(params['auth'], current.get('auth'))
    elif current.get('auth') is not None:
        body['auth'] = current['auth']
    return body


def target_key(target):
    """Identity key for matching a target across current/desired.

    host keyed only for subnet; domain/host/peer get it rewritten server-side.
    """
    host = target.get('host') if target.get('target_type') == 'subnet' else None
    return (target.get('target_id'), host, target.get('port'), target.get('path') or '/')


def targets_differ(current, desired):
    """Compare target lists, ignoring server-computed fields."""
    cur = {target_key(t): t for t in (current or [])}
    des = {target_key(t): t for t in (desired or [])}
    if set(cur) != set(des):
        return True
    for key, desired_target in des.items():
        current_target = cur[key]
        if current_target.get('protocol') != desired_target.get('protocol'):
            return True
        if bool(current_target.get('enabled', True)) != bool(desired_target.get('enabled', True)):
            return True
        if (current_target.get('target_id') or '') != (desired_target.get('target_id') or ''):
            return True
        if desired_target.get('target_id') and current_target.get('target_type') != desired_target.get('target_type'):
            return True
        # server omits direct_upstream when false (API default)
        cur_direct = (current_target.get('options') or {}).get('direct_upstream', False)
        des_direct = (desired_target.get('options') or {}).get('direct_upstream', False)
        if bool(cur_direct) != bool(des_direct):
            return True
        cur_skip = (current_target.get('options') or {}).get('skip_tls_verify', False)
        des_skip = (desired_target.get('options') or {}).get('skip_tls_verify', False)
        if bool(cur_skip) != bool(des_skip):
            return True
        cur_rewrite = (current_target.get('options') or {}).get('path_rewrite', 'preserve')
        des_rewrite = (desired_target.get('options') or {}).get('path_rewrite', 'preserve')
        if cur_rewrite != des_rewrite:
            return True
    return False


def auth_differ(current, desired):
    """Compare auth enable-flags only (the API masks secret values)."""
    if not desired:
        return False
    for scheme in ('bearer_auth', 'password_auth', 'pin_auth'):
        cur_enabled = (current.get(scheme) or {}).get('enabled', False)
        des_enabled = (desired.get(scheme) or {}).get('enabled', False)
        if bool(cur_enabled) != bool(des_enabled):
            return True
    cur_groups = set(extract_ids((current.get('bearer_auth') or {}).get('distribution_groups') or []))
    des_groups = set(extract_ids((desired.get('bearer_auth') or {}).get('distribution_groups') or []))
    if cur_groups != des_groups:
        return True
    return False


def service_needs_update(current, desired):
    """Check whether a service needs to be updated, ignoring computed fields."""
    scalar_fields = (
        'domain', 'name', 'mode', 'private', 'enabled',
        'pass_host_header', 'rewrite_redirects',
    )
    for field in scalar_fields:
        if current.get(field) != desired.get(field):
            return True
    # listen_port 0 = "let NetBird auto-assign"; the server returns the assigned
    # port, so only compare when an explicit non-zero port is requested.
    if desired.get('listen_port') and current.get('listen_port') != desired.get('listen_port'):
        return True
    # access_groups / targets are compared only when managed (present in desired).
    if 'access_groups' in desired:
        if set(extract_ids(current.get('access_groups') or [])) != set(desired['access_groups']):
            return True
    if 'targets' in desired:
        if targets_differ(current.get('targets') or [], desired['targets']):
            return True
    if auth_differ(current.get('auth') or {}, desired.get('auth')):
        return True
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        service_id=dict(type='str'),
        domain=dict(type='str'),
        name=dict(type='str'),
        mode=dict(type='str', choices=['http', 'tcp', 'udp', 'tls']),
        private=dict(type='bool'),
        enabled=dict(type='bool'),
        listen_port=dict(type='int'),
        pass_host_header=dict(type='bool', no_log=False),
        rewrite_redirects=dict(type='bool'),
        access_groups=dict(type='list', elements='str'),
        targets=dict(
            type='list',
            elements='dict',
            options=dict(
                host=dict(type='str', required=True),
                port=dict(type='int', required=True),
                protocol=dict(type='str', default='http'),
                target_id=dict(type='str', required=True),
                target_type=dict(type='str', choices=['subnet', 'host', 'domain', 'peer'], default='subnet'),
                enabled=dict(type='bool', default=True),
                direct_upstream=dict(type='bool', default=True),
                skip_tls_verify=dict(type='bool', default=False),
                path=dict(type='str', default='/'),
                path_rewrite=dict(type='str', default='preserve'),
            ),
        ),
        auth=dict(
            type='dict',
            options=dict(
                bearer_auth=dict(
                    type='dict',
                    options=dict(
                        enabled=dict(type='bool', default=False),
                        distribution_groups=dict(type='list', elements='str'),
                    ),
                ),
                password_auth=dict(
                    type='dict',
                    no_log=False,
                    options=dict(
                        enabled=dict(type='bool', default=False),
                        password=dict(type='str', no_log=True, default=''),
                    ),
                ),
                pin_auth=dict(
                    type='dict',
                    options=dict(
                        enabled=dict(type='bool', default=False),
                        pin=dict(type='str', no_log=True, default=''),
                    ),
                ),
            ),
        ),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[('service_id', 'domain')],
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs']
    )

    state = module.params['state']
    service_id = module.params['service_id']
    domain = module.params['domain']

    result = dict(changed=False, service={})

    try:
        existing = None
        if service_id:
            try:
                existing, _ = api.get_service(service_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif domain:
            existing = find_service_by_domain(api, domain)

        if state == 'absent':
            if existing:
                if not module.check_mode:
                    api.delete_service(existing['id'])
                result['changed'] = True
                result['msg'] = 'Service deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if not existing and not domain:
            module.fail_json(msg='domain is required to create a service')
        desired = build_body(module.params, domain or (existing or {}).get('domain'), current=existing)

        if existing:
            if service_needs_update(existing, desired):
                if not module.check_mode:
                    updated, _ = api.update_service(existing['id'], desired)
                    result['service'] = updated
                else:
                    result['service'] = existing
                result['changed'] = True
            else:
                result['service'] = existing
        else:
            if not module.check_mode:
                created, _ = api.create_service(desired)
                result['service'] = created
            else:
                result['service'] = desired
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()

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
          - Backend IP or hostname for this target, reachable via the
            referenced resource.
          - Optional. A O(targets[].target_type=peer) target is addressed by
            O(targets[].target_id) and has no backend address of its own, so
            leave this unset unless O(targets[].direct_upstream=true) and you
            mean to override the address the lookup would fill in.
          - A O(targets[].target_type=cluster) target in an HTTP service does
            require a host - the API rejects a cluster target with an empty
            one, and also requires O(targets[].direct_upstream=true). In a
            TCP, UDP or TLS service the cluster address comes from
            O(targets[].target_id) and the host may be left unset.
        type: str
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
          - What the target points at, which depends on
            O(targets[].target_type).
          - For V(subnet), V(host) and V(domain), the ID of the NetBird network
            resource the target rides. For V(peer), the peer's ID. For
            V(cluster), the cluster address, which the proxy resolves to an
            upstream at request time rather than an ID.
        type: str
        required: true
      target_type:
        description:
          - Type of the referenced resource.
        type: str
        choices: ['subnet', 'host', 'domain', 'peer', 'cluster']
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
      proxy_protocol:
        description:
          - Send a PROXY Protocol v2 header to this backend, so it can see the
            original client address rather than the proxy's.
          - TCP and TLS targets only. The backend must be configured to expect
            it, or it will treat the header as request data.
        type: bool
        default: false
        version_added: "1.3.0"
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
          - HTTP services only, and defaults to C(preserve) there. The API
            rejects any value on a TCP, UDP or TLS service, so it is omitted
            from the request for those unless you set it explicitly.
        type: str
      access_action:
        description:
          - Authentication applied to requests routed to this target by its
            O(targets[].path).
          - V(inherit) uses the service's authentication. V(bypass) skips the
            service's SSO, password, PIN and header authentication for this
            path, making it public; service-level access restrictions still
            apply. V(block) answers C(403) without contacting the backend.
          - When omitted, the target keeps the action it already has on the
            service (matched by target, then by path), and a new path gets
            V(inherit). A playbook that does not mention the option therefore
            leaves actions set in the dashboard in place. Where the server would
            carry them forward itself, the actions are left out of the request,
            so one changed in the dashboard while the task runs is not undone.
            An action belongs to its path, so moving a target to a new path or
            removing it drops the action with it.
          - Set it, V(inherit) included, to have the playbook enforce the
            action. The export role writes it for every target the server
            reports it on, so applying such an export reverts actions changed
            in the dashboard since. An export taken from a server without the
            feature contains no actions and enforces none.
          - HTTP services only. V(bypass) is not allowed on private services.
            Once any target uses V(bypass) or V(block), enabled targets must
            have distinct paths. A path with a non-inherit action must start
            with C(/), contain no percent sign, backslash, question mark, hash
            or semicolon, and have no C(.) or C(..) segments.
          - Requires NetBird management v0.81.0 or later. A server without it
            ignores the action, so requesting V(bypass) or V(block) from one
            fails instead. For an existing service this is detected before
            anything is written. A new service is created with every target
            disabled, so it serves no route, and its targets are enabled only
            once the server reports the requested actions; otherwise it is
            removed. If enabling fails, the service is read back and its state
            reported; after a transient failure, rerunning the task completes
            it. Check mode cannot detect an unsupported server for a new
            service.
          - The actions are enforced by the reverse proxy. Upgrade every proxy
            in the service's cluster before relying on V(bypass) or V(block),
            since older proxies ignore them and apply the service's authentication.
        type: str
        choices: ['inherit', 'bypass', 'block']
        version_added: "1.5.0"
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
attributes:
  check_mode:
    description: Can run in C(check_mode) and predict changes without modifying the target.
    support: full
  diff_mode:
    description: This module does not report a diff of the changes it makes.
    support: none
requirements:
  - python >= 3.9
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

- name: Public app with a public landing page and a blocked admin path
  community.ansible_netbird.netbird_service:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    domain: "myapp.netbird.example.com"
    private: false
    auth:
      bearer_auth:
        enabled: true
        distribution_groups:
          - "all-users-group-id"
    targets:
      - target_id: "host-resource-id"
        target_type: host
        port: 8080
        direct_upstream: false
        path: /
        access_action: inherit
      - target_id: "host-resource-id"
        target_type: host
        port: 8080
        direct_upstream: false
        path: /public/
        access_action: bypass
      - target_id: "host-resource-id"
        target_type: host
        port: 8080
        direct_upstream: false
        path: /admin
        access_action: block
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
    services, _unused = api.list_services()
    for service in (services or []):
        if service.get('domain') == domain:
            return service
    return None


L4_MODES = ('tcp', 'udp', 'tls')


def build_target(target, mode='http'):
    """Build the API payload for a single target.

    ``mode`` is the service's mode, because two target options are only legal
    for some of them and the API rejects the request outright rather than
    ignoring the field.
    """
    payload = {
        'target_id': target['target_id'],
        'target_type': target.get('target_type', 'subnet'),
        'port': target['port'],
        'path': target.get('path', '/'),
        'protocol': target.get('protocol', 'http'),
        'enabled': target.get('enabled', True),
        'options': {
            'direct_upstream': target.get('direct_upstream', True),
            'skip_tls_verify': target.get('skip_tls_verify', False),
            'proxy_protocol': target.get('proxy_protocol', False),
        },
    }
    # The API refuses a non-empty path_rewrite on a TCP/UDP/TLS service
    # ("path_rewrite is not supported for L4 services"), so an unconditional
    # default made every L4 service a 400 regardless of what was asked for.
    # It stays defaulted for HTTP, where it is meaningful and where changing
    # it would alter how existing services forward paths. An explicit value
    # is always sent, so an L4 service that sets one still gets the API's
    # error rather than having the request quietly rewritten.
    path_rewrite = target.get('path_rewrite')
    if path_rewrite is None and mode not in L4_MODES:
        path_rewrite = 'preserve'
    if path_rewrite is not None:
        payload['options']['path_rewrite'] = path_rewrite
    # `host` is optional in the API (ServiceTarget.Host is *string,
    # json:"host,omitempty"). A peer target is addressed by target_id and has
    # no backend address of its own, so sending an empty host would be wrong
    # rather than merely redundant.
    if target.get('host'):
        payload['host'] = target['host']
    if target.get('access_action'):
        payload['access_action'] = target['access_action']
    return payload


def target_path(target):
    """The path a target is selected by; the API treats unset as ``/``."""
    return target.get('path') or '/'


def resolve_access_actions(payloads, requested, current_targets):
    """Decide the ``access_action`` each target payload is sent with, if any.

    When no target in a request names an action, the server carries existing
    actions forward by path inside its own update transaction -- so an action
    changed in the dashboard between this module's read and its write is not
    lost -- but it refuses to drop or re-path a target whose action is
    ``bypass`` or ``block``, and it hands a path's action to whatever target
    takes that path. So the actions are worked out here, then left out of the
    request whenever the server's merge would give the same result, and sent
    explicitly on every target only when it would not (or when the playbook
    sets one).

    An unset action keeps the current one, so a ``block`` set in the dashboard
    is not reset to ``inherit`` by a playbook that never mentions it. A path
    can hold an enabled target and disabled standbys, each with its own action:

    - an enabled target takes the action of the enabled target currently
      serving its path -- the action in force there -- so enabling a standby or
      swapping the backend keeps it; failing that its own action (a standby
      being enabled), and never the action of a different, disabled target,
      which is not in force -- such a path gets ``inherit``;
    - a disabled target keeps its own action, matched by target, protocol
      and state, then the one action on its path if there is only one;
    - a new path gets ``inherit``.

    Where the targets an omitted action would come from disagree, the task
    fails and asks for the action to be set, rather than pick one.

    Nothing is added when the caller set no action and the server does not
    report the field, so requests to servers without the feature are unchanged.
    """
    current_targets = current_targets or []
    explicit = any(t.get('access_action') for t in requested)
    reported = any('access_action' in t for t in current_targets)
    if not (explicit or reported):
        return
    exact = {}
    own = {}
    by_key = {}
    active = {}
    by_path = {}
    for target in current_targets:
        action = target.get('access_action')
        if not action:
            continue
        key, path, enabled = action_key(target), target_path(target), target_enabled(target)
        protocol = target.get('protocol')
        exact.setdefault((key, protocol, enabled), set()).add(action)
        own.setdefault((key, protocol), set()).add(action)
        by_key.setdefault(key, set()).add(action)
        by_path.setdefault(path, set()).add(action)
        if enabled:
            active.setdefault(path, set()).add(action)
    for payload, wanted in zip(payloads, requested):
        if wanted.get('access_action'):
            payload['access_action'] = wanted['access_action']
            continue
        key, path, protocol = action_key(payload), target_path(payload), payload.get('protocol')
        if target_enabled(payload):
            candidates = (active.get(path), exact.get((key, protocol, True)), own.get((key, protocol)))
        else:
            candidates = (exact.get((key, protocol, False)), own.get((key, protocol)))
        found = next((c for c in candidates if c), None)
        if found and len(found) > 1:
            raise AmbiguousAccessAction(
                'targets[].access_action: path {0} has several targets matching this one with different '
                'actions ({1}); set access_action on it explicitly'.format(path, ', '.join(sorted(found))))
        # Same key under another protocol: either this target with its
        # protocol changed, or a different one. Its bypass or block is not
        # handed over on a guess.
        if not found and (by_key.get(key, set()) - {'inherit'}):
            raise AmbiguousAccessAction(
                'targets[].access_action: path {0} has a target with the same resource and port but '
                'another protocol, with action {1}; set access_action on this target explicitly'.format(
                    path, ', '.join(sorted(by_key[key]))))
        if not found and not target_enabled(payload):
            found = by_path.get(path)
            if found and len(found) > 1:
                raise AmbiguousAccessAction(
                    'targets[].access_action: path {0} has targets with different actions ({1}) and none '
                    'matches this one; set access_action on it explicitly'.format(path, ', '.join(sorted(found))))
        payload['access_action'] = next(iter(found)) if found else 'inherit'
    if not explicit and predicted_server_merge(payloads, current_targets) == [
            p['access_action'] for p in payloads]:
        for payload in payloads:
            del payload['access_action']


def action_key(target):
    """``target_key`` plus a cluster target's host.

    ``target_key`` leaves the host out for every type but subnet, because the
    API rewrites it on read -- except for cluster targets, whose host is the
    operator's upstream. A different upstream is a different backend, so it
    must not inherit the other's action.
    """
    host = (target.get('host') or '') if target.get('target_type') == 'cluster' else None
    return target_key(target) + (host,)


def predicted_server_merge(payloads, current_targets):
    """The actions the server would give the targets if the request named none.

    Mirrors ``preserveTargetAccessActions``: without a bypass or block on the
    service nothing is carried and every target is ``inherit``; otherwise each
    target takes the action stored for its path (first come, first served),
    and the update is refused -- None here -- if a path holding bypass or
    block is dropped or the service has two targets on one path.
    """
    if not any(t.get('access_action') not in (None, 'inherit') for t in current_targets):
        return ['inherit'] * len(payloads)
    by_path = {}
    for target in current_targets:
        path = target_path(target)
        if path in by_path:
            return None
        by_path[path] = target.get('access_action') or 'inherit'
    actions = [by_path.pop(target_path(p), 'inherit') for p in payloads]
    if any(action != 'inherit' for action in by_path.values()):
        return None
    return actions


class AmbiguousAccessAction(ValueError):
    """An omitted action could be taken from targets that disagree."""


def access_action_input_problem(desired):
    """Server-side rules for access actions that can be checked before writing.

    Checked up front because a staged create would otherwise pass them (its
    targets are disabled) and only fail when they are enabled.
    """
    targets = desired.get('targets') or []
    controlled = [t for t in targets if t.get('access_action') not in (None, 'inherit')]
    if not controlled:
        return None
    if desired.get('mode') in L4_MODES:
        return 'targets[].access_action bypass and block are only supported for HTTP services'
    if desired.get('private') and any(t.get('access_action') == 'bypass' for t in controlled):
        return 'targets[].access_action bypass is not allowed on private services'
    # The server only requires distinct paths once an ENABLED target uses
    # bypass or block.
    if not any(target_enabled(t) for t in controlled):
        return None
    seen = set()
    for target in targets:
        if not target_enabled(target):
            continue
        path = target_path(target)
        if path in seen:
            return ('targets[].access_action: once a target uses bypass or block, enabled targets need '
                    'distinct paths, and {0} is used more than once').format(path)
        seen.add(path)
    return None


def target_enabled(target):
    return bool(target.get('enabled', True))


def access_action_unsupported(service, requested):
    """Whether a non-inherit action was requested from a server without it.

    A server that predates per-target actions ignores the field, so a requested
    ``block`` would silently leave the path open. It is detected by the
    service's targets not reporting ``access_action`` at all.
    """
    targets = (service or {}).get('targets') or []
    return requests_access_control(requested) and bool(targets) and not any('access_action' in t for t in targets)


def requests_access_control(requested):
    """Whether any requested target asks for bypass or block."""
    return any(t.get('access_action') not in (None, 'inherit') for t in (requested or []))


ACCESS_ACTION_UNSUPPORTED = (
    'targets[].access_action requires NetBird management v0.81.0 or later; '
    'this server does not report it, so the requested action would not be applied'
)


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
        targets = [build_target(t, body['mode']) for t in params['targets']]
        resolve_access_actions(targets, params['targets'], current.get('targets'))
        body['targets'] = targets
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


def pair_targets(current, desired):
    """Pair each desired target with a current one; None if they do not pair up.

    Targets are matched by ``target_key``. A path may hold an enabled target
    and a disabled standby that share every key field, so a key can match more
    than one target; those pair one-to-one, same enabled state first, rather
    than collapsing so that one hides a change to the other.
    """
    groups = {}
    for target in current or []:
        groups.setdefault(target_key(target), []).append(target)
    pairs = []
    for wanted in desired or []:
        pool = groups.get(target_key(wanted))
        if not pool:
            return None
        # Same enabled state and protocol first: standbys sharing a key are
        # told apart by what they are, not by their order in the list.
        match = min(pool, key=lambda t: (target_enabled(t) != target_enabled(wanted),
                                         t.get('protocol') != wanted.get('protocol'),
                                         (t.get('access_action') or 'inherit')
                                         != (wanted.get('access_action') or 'inherit')))
        pool.remove(match)
        pairs.append((match, wanted))
    if any(groups.values()):
        return None
    return pairs


def targets_differ(current, desired):
    """Compare target lists, ignoring server-computed fields."""
    pairs = pair_targets(current, desired)
    if pairs is None:
        return True
    for current_target, desired_target in pairs:
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
        # server omits proxy_protocol when false (API default)
        cur_proxy = (current_target.get('options') or {}).get('proxy_protocol', False)
        des_proxy = (desired_target.get('options') or {}).get('proxy_protocol', False)
        if bool(cur_proxy) != bool(des_proxy):
            return True
        # Compared only when both sides carry it: a server without per-target
        # actions never returns the field, and would otherwise never converge.
        if 'access_action' in desired_target and 'access_action' in current_target:
            if (current_target.get('access_action') or 'inherit') != desired_target['access_action']:
                return True
        # `host` is absent from target_key for everything but subnet, because
        # replaceHostByLookup overwrites it on every read path -- peer targets
        # get the peer's IP, host and domain targets the resource's address or
        # domain -- so comparing it there would report drift against a value the
        # operator never set, forever. That rewrite is unconditional; it does not
        # consult direct_upstream, whatever the validator's comment suggests.
        #
        # Cluster is the exception: replaceHostByLookup skips it (the upstream
        # address rides on target_id), so the stored host is returned verbatim
        # and is the operator's to manage. It is also the one type where host is
        # required and meaningful, and which this change is what makes
        # expressible, so an edit to it must be detected rather than ignored.
        if desired_target.get('target_type') == 'cluster':
            if (current_target.get('host') or '') != (desired_target.get('host') or ''):
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


def create_service(module, api, desired, requested_targets):
    """Create a service, without serving a route before its access actions hold.

    An existing service always has targets (the API requires one), so a server
    without per-target actions is caught before an update. A new service has
    nothing to judge the server by until it exists. When bypass or block is
    requested it is therefore created with every target disabled -- a disabled
    target is left out of the proxy mapping, on every server version, so
    nothing is routable -- checked, and only then are its targets enabled.

    Should the enabling update fail, the service is read back and its state
    reported. While its targets are still disabled, rerunning the task finds
    it by domain and enables them through an ordinary update -- unless the
    server rejected the configuration, which has to be corrected first.
    """
    if not requests_access_control(requested_targets):
        created, _unused = api.create_service(desired)
        return created
    staged_body = dict(desired, targets=[dict(t, enabled=False) for t in desired['targets']])
    staged, _unused = api.create_service(staged_body)
    problem = staged_action_problem(staged, staged_body)
    if problem:
        try:
            api.delete_service(staged['id'])
        except Exception as e:  # pylint: disable=broad-except
            # The removal may still have gone through (a response cut short):
            # look before saying what is left.
            module.fail_json(msg='{0}; {1}'.format(problem, staged_removal_state(api, staged['id'], e)),
                             changed=True, service=staged)
        module.fail_json(msg='{0}; the service was created with its targets disabled and has been removed'.format(problem),
                         changed=False, service={})
    if not any(target_enabled(t) for t in desired['targets']):
        return staged
    try:
        created, _unused = api.update_service(staged['id'], desired)
    except Exception as e:  # pylint: disable=broad-except
        # Any failure, including a response cut short after the update was
        # applied: what matters is the state the service is now in.
        rejected = isinstance(e, NetBirdAPIError) and e.status_code in (400, 409, 422)
        if rejected:
            advice = 'The server rejected the request: correct the configuration, then rerun the task.'
        else:
            advice = 'Rerunning the task completes it.'
        try:
            current, _unused = api.get_service(staged['id'])
        except Exception:  # pylint: disable=broad-except
            module.fail_json(
                msg=('Service {0} was created with its targets disabled and enabling them failed ({1}); '
                     'its state could not be read back, so it is unknown. {2}').format(staged['id'], e, advice),
                changed=True)
        if not service_needs_update(current, desired):
            return current
        if any(target_enabled(t) for t in current.get('targets') or []):
            state = 'Read back, it has enabled targets but does not match the requested configuration.'
        else:
            state = 'Read back, every target is still disabled, so it serves no route.'
        module.fail_json(
            msg='Enabling the targets of new service {0} failed ({1}). {2} {3}'.format(staged['id'], e, state, advice),
            changed=True, service=current)
    return created


def staged_removal_state(api, service_id, error):
    """Describe a staged service whose removal failed, from a fresh read."""
    unconfirmed = ('removing staged service {0} failed ({1}) and it could not be read back, so whether it '
                   'remains is unconfirmed: check it and delete it if present').format(service_id, error)
    try:
        api.get_service(service_id)
    except NetBirdAPIError as e:
        if e.status_code == 404:
            return 'removing the staged service reported an error ({0}) but it is gone'.format(error)
        return unconfirmed
    except Exception:  # pylint: disable=broad-except
        return unconfirmed
    return ('removing the service failed ({0}). Service {1} is left with every target disabled, so it '
            'serves no route: delete it.').format(error, service_id)


def staged_action_problem(staged, sent):
    """Why the staged service cannot be enabled, or None.

    Every target must come back with the action that was sent: a server that
    predates the feature returns none, and any other difference means the
    requested protection is not what the server holds.
    """
    if not any('access_action' in t for t in staged.get('targets') or []):
        return ACCESS_ACTION_UNSUPPORTED
    pairs = pair_targets(staged.get('targets'), sent['targets'])
    if pairs is None:
        return 'the created service did not return the targets that were sent'
    for got, wanted in pairs:
        if (got.get('access_action') or 'inherit') != wanted.get('access_action', 'inherit'):
            return 'the server stored access_action {0!r} where {1!r} was requested for path {2}'.format(
                got.get('access_action'), wanted.get('access_action'), target_path(wanted))
    return None


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
                host=dict(type='str'),
                port=dict(type='int', required=True),
                protocol=dict(type='str', default='http'),
                target_id=dict(type='str', required=True),
                target_type=dict(
                    type='str',
                    choices=['subnet', 'host', 'domain', 'peer', 'cluster'],
                    default='subnet',
                ),
                enabled=dict(type='bool', default=True),
                direct_upstream=dict(type='bool', default=True),
                skip_tls_verify=dict(type='bool', default=False),
                path=dict(type='str', default='/'),
                path_rewrite=dict(type='str'),
                proxy_protocol=dict(type='bool', default=False),
                access_action=dict(type='str', choices=['inherit', 'bypass', 'block']),
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
                existing, _unused = api.get_service(service_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
            # A stale service_id must not create a second service for a domain
            # that already has one -- nor silently manage that other service,
            # which nothing ties to this task. Name it and let the operator say.
            if not existing and domain and state == 'present':
                other = find_service_by_domain(api, domain)
                if other:
                    module.fail_json(msg=(
                        'service_id {0} was not found, and domain {1} is served by service {2}; set service_id '
                        'to {2} to manage that service, or omit service_id to manage it by domain').format(
                            service_id, domain, other.get('id')))
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
        try:
            desired = build_body(module.params, domain or (existing or {}).get('domain'), current=existing)
        except AmbiguousAccessAction as e:
            module.fail_json(msg=str(e))
        requested_targets = module.params.get('targets')
        input_problem = access_action_input_problem(desired)
        if input_problem:
            module.fail_json(msg=input_problem)

        if access_action_unsupported(existing, requested_targets):
            module.fail_json(msg=ACCESS_ACTION_UNSUPPORTED)

        if existing:
            if service_needs_update(existing, desired):
                if not module.check_mode:
                    updated, _unused = api.update_service(existing['id'], desired)
                    result['service'] = updated
                else:
                    result['service'] = existing
                result['changed'] = True
            else:
                result['service'] = existing
        else:
            if not module.check_mode:
                result['service'] = create_service(module, api, desired, requested_targets)
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

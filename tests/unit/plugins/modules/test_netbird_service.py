# -*- coding: utf-8 -*-
# Copyright: (c) 2024-2026, NetBird and contributors
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the netbird_service target payload.

Run via:
    ansible-test units --docker default

Two target options are legal for some service modes and rejected outright for
others, and the API answers 400 rather than ignoring the field:

- ``path_rewrite`` is refused on TCP, UDP and TLS ("path_rewrite is not
  supported for L4 services"), so a default that always sends it makes every
  L4 service impossible to create;
- ``proxy_protocol`` is refused on HTTP and on UDP, so it is only usable on
  TCP and TLS.

Between them there is no mode where both defaults can be sent, which is why
``build_target`` takes the service mode.

``build_target`` is pure; no request is made.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible_collections.community.ansible_netbird.plugins.modules.netbird_service import (
    AmbiguousAccessAction,
    pair_targets,
)

from ansible_collections.community.ansible_netbird.plugins.modules import netbird_service
from ansible_collections.community.ansible_netbird.plugins.modules.netbird_service import (
    access_action_unsupported,
    build_body,
    build_target,
    targets_differ,
)


def target(**overrides):
    """A target as the argspec hands it over: every suboption with a default
    is already filled in, and the ones without are present as None."""
    base = {
        'target_id': 'res-1',
        'target_type': 'subnet',
        'host': '10.0.0.1',
        'port': 8080,
        'path': '/',
        'protocol': 'http',
        'enabled': True,
        'direct_upstream': True,
        'skip_tls_verify': False,
        'path_rewrite': None,
        'proxy_protocol': False,
        'access_action': None,
    }
    base.update(overrides)
    return base


class TestPathRewriteByMode:

    @pytest.mark.parametrize('mode', ['tcp', 'udp', 'tls'])
    def test_omitted_for_l4_when_unset(self, mode):
        """The regression: sending it made every L4 service a 400."""
        options = build_target(target(), mode)['options']
        assert 'path_rewrite' not in options

    def test_defaults_to_preserve_for_http(self):
        """Unchanged for HTTP services, where the value is meaningful and
        where dropping it would change how paths reach the upstream."""
        assert build_target(target(), 'http')['options']['path_rewrite'] == 'preserve'

    def test_defaults_to_preserve_when_no_mode_is_given(self):
        assert build_target(target())['options']['path_rewrite'] == 'preserve'

    @pytest.mark.parametrize('mode', ['tcp', 'udp', 'tls', 'http'])
    def test_an_explicit_value_is_always_sent(self, mode):
        """Not silently dropped for L4 — the operator asked for something the
        API refuses, and should see the API say so rather than have the
        request rewritten underneath them."""
        options = build_target(target(path_rewrite='default'), mode)['options']
        assert options['path_rewrite'] == 'default'


class TestHost:

    def test_omitted_when_unset(self):
        """A peer target has no backend address of its own, so an empty host
        would be wrong rather than merely redundant."""
        assert 'host' not in build_target(target(host=None, target_type='peer'))

    def test_omitted_when_empty(self):
        assert 'host' not in build_target(target(host=''))

    def test_sent_when_given(self):
        assert build_target(target(host='10.0.0.9'))['host'] == '10.0.0.9'


class TestProxyProtocol:

    def test_defaults_to_false(self):
        """False is safe to send on every mode: the API only rejects a true
        value on HTTP and UDP."""
        assert build_target(target())['options']['proxy_protocol'] is False

    def test_sent_when_enabled(self):
        assert build_target(target(proxy_protocol=True), 'tcp')['options']['proxy_protocol'] is True


class TestRemainingPayload:

    def test_carries_the_identifying_fields(self):
        payload = build_target(target(target_type='cluster'), 'tcp')
        assert payload['target_id'] == 'res-1'
        assert payload['target_type'] == 'cluster'
        assert payload['port'] == 8080

    def test_defaults_are_applied_for_a_bare_dict(self):
        """Reached when the caller is not the argspec — the comparator builds
        targets from server responses."""
        payload = build_target({'target_id': 'r', 'port': 1}, 'http')
        assert payload['target_type'] == 'subnet'
        assert payload['path'] == '/'
        assert payload['protocol'] == 'http'
        assert payload['enabled'] is True
        assert payload['options']['direct_upstream'] is True
        assert payload['options']['skip_tls_verify'] is False


def sent(**overrides):
    """A target as it went to the API / comes back from it."""
    base = {
        'target_id': 'res-1',
        'target_type': 'cluster',
        'host': '10.0.0.1',
        'port': 8080,
        'path': '/',
        'protocol': 'http',
        'enabled': True,
        'options': {'direct_upstream': True, 'skip_tls_verify': False,
                    'path_rewrite': 'preserve', 'proxy_protocol': False},
    }
    base.update(overrides)
    return base


class TestHostChangeDetection:
    """`host` is left out of the match key for non-subnet targets because
    ``replaceHostByLookup`` overwrites it on every read path. That rewrite is
    unconditional -- it does not consult ``direct_upstream`` -- so for peer,
    host and domain targets the returned host is never the operator's value and
    comparing it would never converge.

    Cluster is the exception the lookup skips, which is also the one type where
    host is required and operator-meaningful.
    """

    def test_an_edited_cluster_host_is_detected(self):
        """The regression: silently ignored, so the playbook and the server
        disagreed permanently."""
        assert targets_differ([sent()], [sent(host='10.0.0.2')]) is True

    def test_an_unchanged_cluster_host_is_not_a_change(self):
        assert targets_differ([sent()], [sent()]) is False

    @pytest.mark.parametrize('target_type', ['peer', 'host', 'domain'])
    def test_a_rewritten_host_never_reads_as_drift(self, target_type):
        """replaceHostByLookup replaces the host with the peer IP or the
        resource's address on every read, whatever was sent and whatever
        direct_upstream says. Comparing it would mean changed=true on every run,
        forever, with the PUT unable to make it converge."""
        current = sent(target_type=target_type, host='100.64.0.7')
        desired = sent(target_type=target_type, host='10.0.0.9')
        assert targets_differ([current], [desired]) is False

    @pytest.mark.parametrize('direct', [True, False])
    def test_the_peer_case_holds_either_way_on_direct_upstream(self, direct):
        """The validator's comment says an operator host is honoured when
        direct_upstream is set. The read path does not implement that, so the
        flag must not gate the comparison."""
        opts = {'direct_upstream': direct, 'skip_tls_verify': False,
                'path_rewrite': 'preserve', 'proxy_protocol': False}
        current = sent(target_type='peer', host='100.64.0.7', options=opts)
        desired = sent(target_type='peer', host='10.0.0.9', options=dict(opts))
        assert targets_differ([current], [desired]) is False

    def test_a_subnet_host_change_is_still_a_key_change(self):
        """Subnet keeps host in the match key, so this reads as a different
        target rather than an edited one -- either way, a change."""
        assert targets_differ([sent(target_type='subnet')],
                              [sent(target_type='subnet', host='10.0.0.2')]) is True

    def test_clearing_a_cluster_host_is_detected(self):
        assert targets_differ([sent()], [sent(host=None)]) is True

    def test_other_option_changes_are_unaffected(self):
        assert targets_differ([sent()], [sent(protocol='https')]) is True
        assert targets_differ([sent()], [sent(enabled=False)]) is True


def params(targets, **overrides):
    """Module params as the argspec hands them over."""
    base = {
        'name': None, 'mode': None, 'private': None, 'enabled': None,
        'listen_port': None, 'pass_host_header': None, 'rewrite_redirects': None,
        'access_groups': None, 'auth': None, 'targets': targets,
    }
    base.update(overrides)
    return base


def existing(*targets):
    """A stored public HTTP service as the API returns it."""
    return {'id': 'svc-1', 'domain': 'app.example.com', 'name': 'app.example.com',
            'mode': 'http', 'private': False, 'enabled': True, 'targets': list(targets)}


def stored(path, action='inherit', **overrides):
    t = sent(target_type='host', path=path, access_action=action)
    t.update(overrides)
    return t


def sent_actions(body):
    return {t['path']: t.get('access_action') for t in body['targets']}


def effective_actions(body, current):
    """What each target ends up with: the action sent, or -- when the request
    names none -- what the server's own merge gives it."""
    if any('access_action' in t for t in body['targets']):
        return sent_actions(body)
    merged = netbird_service.predicted_server_merge(body['targets'], current['targets'])
    return {t['path']: a for t, a in zip(body['targets'], merged)}


class TestAccessActionPayload:

    def test_omitted_when_unset(self):
        assert 'access_action' not in build_target(target())

    @pytest.mark.parametrize('action', ['inherit', 'bypass', 'block'])
    def test_sent_when_given(self, action):
        assert build_target(target(access_action=action))['access_action'] == action


class TestAccessActionResolution:
    """The server only carries existing actions forward when no target in the
    request names one, and then refuses to drop or re-path a bypass/block
    target. Sending an explicit action on every target opts out of that."""

    def test_removing_a_blocked_target_sends_explicit_actions(self):
        """The regression: the request carried no action, so the server's merge
        ran and answered 422 'include access_action when removing or changing
        controlled target location'."""
        current = existing(stored('/'), stored('/admin', 'block'))
        body = build_body(params([target(target_type='host', path='/')]),
                          'app.example.com', current)
        assert sent_actions(body) == {'/': 'inherit'}

    def test_an_unset_action_keeps_the_current_one(self):
        """A dashboard Block must not be loosened by a playbook that predates
        the option -- and since the server's own merge keeps it, the request
        leaves the actions out, so one changed in the dashboard while the task
        runs is not overwritten with this module's earlier read."""
        current = existing(stored('/'), stored('/admin', 'block'))
        body = build_body(params([target(target_type='host', path='/'),
                                  target(target_type='host', path='/admin')]),
                          'app.example.com', current)
        assert sent_actions(body) == {'/': None, '/admin': None}
        assert effective_actions(body, current) == {'/': 'inherit', '/admin': 'block'}

    def test_an_unset_action_follows_the_path_when_the_target_changes(self):
        """Same location, new backend port: the server preserves by location,
        so the module does too."""
        current = existing(stored('/admin', 'block'))
        body = build_body(params([target(target_type='host', path='/admin', port=9090)]),
                          'app.example.com', current)
        assert effective_actions(body, current) == {'/admin': 'block'}

    def test_a_disabled_twin_does_not_hand_over_its_action(self):
        """The server allows a disabled target to share a path with an enabled
        one. The enabled one's action is the one in force on that path."""
        current = existing(stored('/admin', 'block', enabled=False), stored('/admin', 'inherit'))
        body = build_body(params([target(target_type='host', path='/admin')]),
                          'app.example.com', current)
        assert sent_actions(body) == {'/admin': 'inherit'}

    def test_a_kept_standby_keeps_its_own_action(self):
        """An enabled target and a disabled standby on one path, identical
        otherwise, each keep their own action when both stay."""
        current = existing(stored('/admin', 'inherit'), stored('/admin', 'block', enabled=False))
        body = build_body(params([target(target_type='host', path='/admin'),
                                  target(target_type='host', path='/admin', enabled=False)]),
                          'app.example.com', current)
        assert [(t['enabled'], t['access_action']) for t in body['targets']] == [(True, 'inherit'), (False, 'block')]

    def test_enabling_a_standby_keeps_the_path_action(self):
        """Swapping the active backend for a standby must not adopt the
        standby's own action: the path stays blocked."""
        current = existing(stored('/admin', 'block'), stored('/admin', 'inherit', enabled=False, port=9090))
        body = build_body(params([target(target_type='host', path='/admin', port=9090)]),
                          'app.example.com', current)
        assert sent_actions(body) == {'/admin': 'block'}

    def test_an_enabled_replacement_ignores_a_disabled_targets_action(self):
        """Only a disabled target with bypass sits on the path, so bypass is not
        in force there; a different, enabled target must not pick it up."""
        current = existing(stored('/admin', 'bypass', enabled=False))
        body = build_body(params([target(target_type='host', path='/admin', port=9090)]),
                          'app.example.com', current)
        assert sent_actions(body) == {'/admin': 'inherit'}

    def test_enabling_a_standby_keeps_its_own_action(self):
        current = existing(stored('/admin', 'block', enabled=False))
        body = build_body(params([target(target_type='host', path='/admin')]),
                          'app.example.com', current)
        assert effective_actions(body, current) == {'/admin': 'block'}

    def test_enabling_a_standby_keeps_its_own_action_by_protocol(self):
        """Disabled HTTP and HTTPS standbys share a key; enabling the HTTPS one
        keeps its own block, not the HTTP one's bypass."""
        current = existing(stored('/admin', 'bypass', enabled=False, protocol='http'),
                           stored('/admin', 'block', enabled=False, protocol='https'))
        body = build_body(params([target(target_type='host', path='/admin', protocol='https')]),
                          'app.example.com', current)
        assert sent_actions(body) == {'/admin': 'block'}

    def test_an_ambiguous_omitted_action_is_refused(self):
        """Identical standbys with different actions: no guessing."""
        current = existing(stored('/admin', 'bypass', enabled=False), stored('/admin', 'block', enabled=False))
        with pytest.raises(AmbiguousAccessAction):
            build_body(params([target(target_type='host', path='/admin', enabled=False)]),
                       'app.example.com', current)

    def test_another_protocols_action_is_not_handed_over(self):
        """The only target on /admin is a disabled HTTP one with bypass. A new
        enabled HTTPS target on the same resource and port could be that
        target re-protocolled or a different one; bypass is not guessed."""
        current = existing(stored('/admin', 'bypass', enabled=False, protocol='http'))
        with pytest.raises(AmbiguousAccessAction):
            build_body(params([target(target_type='host', path='/admin', protocol='https')]),
                       'app.example.com', current)

    def test_another_protocols_inherit_needs_no_explicit_action(self):
        current = existing(stored('/admin', 'inherit', enabled=False, protocol='http'))
        body = build_body(params([target(target_type='host', path='/admin', protocol='https')]),
                          'app.example.com', current)
        assert effective_actions(body, current) == {'/admin': 'inherit'}

    def test_a_different_cluster_upstream_does_not_inherit(self):
        """A cluster target's host is its upstream: another host is another
        backend, even with the same cluster, port and path."""
        current = existing(stored('/admin', 'bypass', enabled=False, target_type='cluster', host='10.0.0.1'))
        body = build_body(params([target(target_type='cluster', path='/admin', host='10.0.0.2')]),
                          'app.example.com', current)
        assert sent_actions(body) == {'/admin': 'inherit'}

    def test_conflicting_actions_on_a_path_are_not_guessed_for_a_standby(self):
        current = existing(stored('/admin', 'bypass', enabled=False, port=8081),
                           stored('/admin', 'block', enabled=False, port=8082))
        with pytest.raises(AmbiguousAccessAction):
            build_body(params([target(target_type='host', path='/admin', port=8083, enabled=False)]),
                       'app.example.com', current)

    def test_the_server_merge_is_used_only_where_it_agrees(self):
        """Without an action in the request the server would hand the disabled
        standby's bypass to the new enabled target; that is why the action is
        sent explicitly there."""
        current = existing(stored('/admin', 'bypass', enabled=False))
        body = build_body(params([target(target_type='host', path='/admin', port=9090)]),
                          'app.example.com', current)
        assert netbird_service.predicted_server_merge(body['targets'], current['targets']) == ['bypass']
        assert sent_actions(body) == {'/admin': 'inherit'}

    def test_an_explicit_action_wins(self):
        current = existing(stored('/admin', 'block'))
        body = build_body(params([target(target_type='host', path='/admin', access_action='inherit')]),
                          'app.example.com', current)
        assert sent_actions(body) == {'/admin': 'inherit'}

    def test_a_new_path_gets_inherit_once_any_action_is_sent(self):
        body = build_body(params([target(path='/'), target(path='/admin', access_action='block')]),
                          'app.example.com')
        assert sent_actions(body) == {'/': 'inherit', '/admin': 'block'}

    def test_nothing_is_added_for_a_server_without_the_field(self):
        """Requests to servers that predate the feature stay unchanged."""
        legacy = sent(target_type='host')
        current = existing(legacy)
        body = build_body(params([target(target_type='host')]), 'app.example.com', current)
        assert 'access_action' not in body['targets'][0]

    def test_nothing_is_added_on_create_when_unset(self):
        body = build_body(params([target()]), 'app.example.com')
        assert 'access_action' not in body['targets'][0]


class TestAccessActionChangeDetection:

    def test_a_changed_action_is_detected(self):
        assert targets_differ([stored('/admin', 'block')], [stored('/admin', 'bypass')]) is True

    def test_an_unchanged_action_is_not_a_change(self):
        assert targets_differ([stored('/admin', 'block')], [stored('/admin', 'block')]) is False

    def test_a_change_to_one_of_two_same_key_targets_is_detected(self):
        """An enabled target and a disabled standby share every key field; a
        change to only one of them must not be hidden by the other."""
        current = [stored('/admin', 'inherit'), stored('/admin', 'inherit', enabled=False)]
        desired = [stored('/admin', 'block'), stored('/admin', 'inherit', enabled=False)]
        assert targets_differ(current, desired) is True
        assert targets_differ(current, [stored('/admin', 'inherit'),
                                        stored('/admin', 'inherit', enabled=False)]) is False

    def test_standbys_sharing_a_key_pair_by_protocol_not_order(self):
        current = [stored('/admin', 'inherit', enabled=False, protocol='http'),
                   stored('/admin', 'block', enabled=False, protocol='https')]
        desired = [stored('/admin', 'block', enabled=False, protocol='https'),
                   stored('/admin', 'inherit', enabled=False, protocol='http')]
        assert targets_differ(current, desired) is False

    def test_standbys_that_differ_only_by_action_pair_by_action(self):
        current = [stored('/admin', 'bypass', enabled=False), stored('/admin', 'block', enabled=False)]
        desired = [stored('/admin', 'block', enabled=False), stored('/admin', 'bypass', enabled=False)]
        assert targets_differ(current, desired) is False
        assert [(c['access_action'], d['access_action']) for c, d in pair_targets(current, desired)] == \
            [('block', 'block'), ('bypass', 'bypass')]

    def test_a_server_that_does_not_report_it_does_not_drift(self):
        """Otherwise changed=true on every run against such a server."""
        legacy = sent(target_type='host', path='/admin')
        assert targets_differ([legacy], [stored('/admin', 'inherit')]) is False

    def test_preserved_actions_round_trip_without_a_change(self):
        current = existing(stored('/'), stored('/admin', 'block'))
        body = build_body(params([target(target_type='host', path='/'),
                                  target(target_type='host', path='/admin')]),
                          'app.example.com', current)
        assert targets_differ(current['targets'], body['targets']) is False


class TestAccessActionSupport:

    def test_a_requested_block_on_a_server_without_the_field_is_refused(self):
        """It would be ignored, leaving the path open while the task reports
        success."""
        service = existing(sent(target_type='host'))
        assert access_action_unsupported(service, [target(access_action='block')]) is True

    def test_inherit_is_never_refused(self):
        service = existing(sent(target_type='host'))
        assert access_action_unsupported(service, [target(access_action='inherit')]) is False

    def test_a_server_that_reports_it_is_fine(self):
        service = existing(stored('/'))
        assert access_action_unsupported(service, [target(access_action='block')]) is False

    def test_no_targets_to_judge_by_is_not_refused(self):
        assert access_action_unsupported(existing(), [target(access_action='block')]) is False
        assert access_action_unsupported(None, [target(access_action='block')]) is False


class Exit(Exception):
    pass


class Fail(Exception):
    pass


class FakeModule:
    """Stands in for AnsibleModule; params are passed as the argspec would."""

    params = None
    check = False

    def __init__(self, *args, **kwargs):
        self.check_mode = FakeModule.check

    def exit_json(self, **kwargs):
        raise Exit(kwargs)

    def fail_json(self, **kwargs):
        raise Fail(kwargs)


class FakeAPI:
    """A NetBird server that keeps its services between calls.
    ``supported=False`` predates per-target actions: it accepts the field and
    never returns it. ``stored`` overrides the action the server keeps."""

    def __init__(self, services, supported, stored=None):
        self.services = [dict(svc) for svc in services]
        self.supported = supported
        self.stored = stored
        self.calls = []

    def _keep(self, body, service_id):
        targets = []
        for t in body.get('targets') or []:
            if not self.supported:
                t = strip(t)
            elif self.stored and 'access_action' in t:
                t = dict(t, access_action=self.stored)
            targets.append(t)
        svc = dict(body, id=service_id, targets=targets)
        self.services = [x for x in self.services if x['id'] != service_id] + [svc]
        return svc

    def list_services(self):
        return [dict(x) for x in self.services], None

    def get_service(self, service_id):
        self.calls.append(('get', service_id))
        for x in self.services:
            if x['id'] == service_id:
                return dict(x), None
        raise netbird_service.NetBirdAPIError('not found', status_code=404)

    def create_service(self, body):
        self.calls.append(('create', body))
        return self._keep(body, 'svc-new'), None

    def update_service(self, service_id, body):
        self.calls.append(('update', service_id, body))
        return self._keep(body, service_id), None

    def delete_service(self, service_id):
        self.calls.append(('delete', service_id))
        self.services = [x for x in self.services if x['id'] != service_id]


def strip(t):
    return {k: v for k, v in t.items() if k != 'access_action'}


def run(monkeypatch, api, targets, check_mode=False, service_id=None, **overrides):
    FakeModule.params = dict(
        api_url='https://netbird.example.com', api_token='t', validate_certs=True,
        state='present', service_id=service_id, domain='app.example.com',
        **params(targets, **overrides))
    FakeModule.check = check_mode
    monkeypatch.setattr(netbird_service, 'AnsibleModule', FakeModule)
    monkeypatch.setattr(netbird_service, 'NetBirdAPI', lambda *a, **k: api)
    with pytest.raises((Exit, Fail)) as raised:
        netbird_service.run_module()
    return raised.type, raised.value.args[0]


BLOCK = [target(path='/'), target(path='/admin', access_action='block')]


def writes(api):
    return [c[0] for c in api.calls if c[0] != 'get']


def broken(*_args, **_kwargs):
    raise netbird_service.NetBirdAPIError('boom', status_code=502)


class TestCreateWithAccessControl:
    """A new service has nothing to judge the server by until it exists, so
    with bypass or block requested it is created with every target disabled --
    a disabled target is left out of the proxy mapping, so nothing is routable
    -- checked, and only then are its targets enabled."""

    def test_targets_enabled_only_after_the_actions_are_confirmed(self, monkeypatch):
        api = FakeAPI([], supported=True)
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Exit and result['changed'] is True
        assert writes(api) == ['create', 'update']
        assert [t['enabled'] for t in api.calls[0][1]['targets']] == [False, False]
        assert api.calls[0][1]['enabled'] is True
        assert [t['enabled'] for t in result['service']['targets']] == [True, True]

    def test_targets_requested_disabled_need_no_second_write(self, monkeypatch):
        api = FakeAPI([], supported=True)
        targets = [target(path='/', enabled=False), target(path='/admin', access_action='block', enabled=False)]
        kind, _result = run(monkeypatch, api, targets)
        assert kind is Exit and writes(api) == ['create']

    def test_ignored_actions_remove_the_never_routable_service(self, monkeypatch):
        api = FakeAPI([], supported=False)
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail and result['changed'] is False
        assert writes(api) == ['create', 'delete']
        assert 'removed' in result['msg'] and api.services == []

    def test_a_different_stored_action_is_refused(self, monkeypatch):
        """The field is reported, but not with the requested value."""
        api = FakeAPI([], supported=True, stored='inherit')
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail
        assert writes(api) == ['create', 'delete']
        assert "'block' was requested" in result['msg']

    def test_a_failed_removal_says_what_is_left(self, monkeypatch):
        api = FakeAPI([], supported=False)
        api.delete_service = broken
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail and result['changed'] is True
        assert 'serves no route' in result['msg'] and 'svc-new' in result['msg']

    def test_an_enable_that_committed_despite_an_error_is_success(self, monkeypatch):
        api = FakeAPI([], supported=True)
        real_update = api.update_service

        def commit_then_fail(service_id, body):
            real_update(service_id, body)
            raise netbird_service.NetBirdAPIError('bad gateway', status_code=502)
        api.update_service = commit_then_fail
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Exit
        assert [t['enabled'] for t in result['service']['targets']] == [True, True]

    def test_a_failed_enable_is_completed_by_a_rerun(self, monkeypatch):
        """Same server, same input: the staged service is found by domain and
        its targets are enabled by an ordinary update."""
        api = FakeAPI([], supported=True)
        real_update = api.update_service
        api.update_service = broken
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail and result['changed'] is True
        assert 'serves no route' in result['msg'] and 'Rerunning' in result['msg']
        assert [t['enabled'] for t in api.services[0]['targets']] == [False, False]

        api.update_service = real_update
        api.calls = []
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Exit and result['changed'] is True
        assert writes(api) == ['update']
        assert [t['enabled'] for t in api.services[0]['targets']] == [True, True]
        assert api.services[0]['targets'][1]['access_action'] == 'block'

    def test_an_unreadable_state_after_a_failed_enable_is_unknown(self, monkeypatch):
        api = FakeAPI([], supported=True)
        api.update_service = broken
        api.get_service = broken
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail and 'unknown' in result['msg']

    def test_a_rejected_enable_asks_for_a_configuration_fix(self, monkeypatch):
        api = FakeAPI([], supported=True)

        def rejected(service_id, body):
            raise netbird_service.NetBirdAPIError('invalid', status_code=422)
        api.update_service = rejected
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail
        assert 'correct the configuration' in result['msg'] and 'Rerunning the task completes' not in result['msg']
        assert 'every target is still disabled' in result['msg']

    def test_a_rejected_enable_with_an_unreadable_state_still_asks_for_a_fix(self, monkeypatch):
        api = FakeAPI([], supported=True)

        def rejected(service_id, body):
            raise netbird_service.NetBirdAPIError('invalid', status_code=422)
        api.update_service = rejected
        api.get_service = broken
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail
        assert 'unknown' in result['msg'] and 'correct the configuration' in result['msg']
        assert 'Rerunning the task completes' not in result['msg']

    def test_the_read_back_state_is_reported_as_observed(self, monkeypatch):
        """Enabled, but renamed by someone else before the read-back: say what
        is there, not that no route is served."""
        api = FakeAPI([], supported=True)
        real_update = api.update_service

        def commit_then_fail(service_id, body):
            real_update(service_id, body)
            api.services[0]['name'] = 'renamed elsewhere'
            raise netbird_service.NetBirdAPIError('bad gateway', status_code=502)
        api.update_service = commit_then_fail
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail
        assert 'has enabled targets' in result['msg'] and 'serves no route' not in result['msg']

    def test_a_truncated_response_after_a_committed_enable_is_success(self, monkeypatch):
        """Not every failure is a NetBirdAPIError: a response cut short raises
        from the HTTP layer. The read-back still decides."""
        api = FakeAPI([], supported=True)
        real_update = api.update_service

        def commit_then_truncate(service_id, body):
            real_update(service_id, body)
            raise IOError('IncompleteRead(0 bytes read)')
        api.update_service = commit_then_truncate
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Exit
        assert [t['enabled'] for t in result['service']['targets']] == [True, True]

    def test_a_stale_service_id_does_not_take_over_the_domains_service(self, monkeypatch):
        """Nothing ties the service on the domain to this task: name it rather
        than create a second one or manage it uninvited."""
        other = dict(existing(stored('/')), id='svc-other')
        api = FakeAPI([other], supported=True)
        kind, result = run(monkeypatch, api, BLOCK, service_id='stale-id')
        assert kind is Fail and writes(api) == []
        assert 'svc-other' in result['msg']

    def test_a_failed_removal_that_went_through_is_reported_as_gone(self, monkeypatch):
        api = FakeAPI([], supported=False)
        real_delete = api.delete_service

        def delete_then_truncate(service_id):
            real_delete(service_id)
            raise IOError('IncompleteRead(0 bytes read)')
        api.delete_service = delete_then_truncate
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail and 'it is gone' in result['msg']

    def test_an_unreadable_removal_is_reported_as_unconfirmed(self, monkeypatch):
        api = FakeAPI([], supported=False)
        api.delete_service = broken
        api.get_service = broken
        kind, result = run(monkeypatch, api, BLOCK)
        assert kind is Fail and 'unconfirmed' in result['msg'] and 'svc-new' in result['msg']

    def test_inherit_only_is_a_plain_create(self, monkeypatch):
        api = FakeAPI([], supported=False)
        kind, _result = run(monkeypatch, api, [target(path='/admin', access_action='inherit')])
        assert kind is Exit
        assert writes(api) == ['create']
        assert api.calls[0][1]['targets'][0]['enabled'] is True

    def test_check_mode_writes_nothing(self, monkeypatch):
        api = FakeAPI([], supported=False)
        kind, result = run(monkeypatch, api, BLOCK, check_mode=True)
        assert kind is Exit and result['changed'] is True
        assert api.calls == []


class TestRejectedBeforeAnyWrite:
    """Rules a staged create would only hit once its targets are enabled."""

    @pytest.mark.parametrize('mode', ['tcp', 'udp', 'tls'])
    def test_block_on_an_l4_service(self, monkeypatch, mode):
        """An L4 target cannot be staged disabled: the server forces it on."""
        api = FakeAPI([], supported=False)
        kind, result = run(monkeypatch, api, [target(protocol='tcp', access_action='block')], mode=mode)
        assert kind is Fail and api.calls == []
        assert 'only supported for HTTP' in result['msg']

    def test_bypass_on_a_private_service(self, monkeypatch):
        api = FakeAPI([], supported=True)
        kind, result = run(monkeypatch, api, [target(path='/public/', access_action='bypass')], private=True)
        assert kind is Fail and api.calls == []
        assert 'private services' in result['msg']

    def test_block_on_a_private_service_is_fine(self, monkeypatch):
        api = FakeAPI([], supported=True)
        kind, _result = run(monkeypatch, api, [target(path='/admin', access_action='block')], private=True)
        assert kind is Exit

    def test_a_disabled_controlled_target_does_not_force_distinct_paths(self, monkeypatch):
        """The server only requires distinct paths once an ENABLED target
        uses bypass or block."""
        api = FakeAPI([], supported=True)
        targets = [target(path='/'), target(path='/', port=9090),
                   target(path='/admin', access_action='block', enabled=False)]
        kind, _result = run(monkeypatch, api, targets)
        assert kind is Exit

    def test_two_enabled_targets_on_a_controlled_path(self, monkeypatch):
        api = FakeAPI([], supported=True)
        targets = [target(path='/admin', access_action='block'), target(path='/admin', port=9090)]
        kind, result = run(monkeypatch, api, targets)
        assert kind is Fail and api.calls == []
        assert 'distinct paths' in result['msg']


class TestUpdateOnAServerWithoutTheField:
    """An existing service always has targets (the API refuses one without), so
    a server that does not report the field is recognised before writing."""

    @pytest.mark.parametrize('check_mode', [False, True])
    def test_refused_before_any_write(self, monkeypatch, check_mode):
        api = FakeAPI([existing(sent(target_type='host'))], supported=False)
        kind, result = run(monkeypatch, api, BLOCK, check_mode=check_mode)
        assert kind is Fail
        assert api.calls == []
        assert 'v0.81.0' in result['msg']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# -*- coding: utf-8 -*-
# Copyright: (c) 2024-2026, NetBird and contributors
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for service preview diff accuracy.

Run via:
    ansible-test units --docker default

Three shape mismatches between the exported YAML and what _compare_service
reads from the API made the preview flag every service as CHANGED on a
freshly exported config:

1. access_groups / distribution_groups: names vs IDs — the export writes
   group names, but the API returns IDs. Without resolution, every service
   with groups shows drift.
2. targets: the export flattens options.direct_upstream etc. to top-level
   target keys, while the API returns them in a nested options dict.
3. auth: the declared-keys filter is top-level only, so an exported
   bearer-only auth reports password_auth and pin_auth as removed.

_compare_service is pure; no request is made.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible_collections.community.ansible_netbird.plugins.filter.netbird_diff import (
    netbird_diff,
    _compare_service,
)

GROUP_IDS = {
    'ci-test-group': 'grp-abc-123',
    'developers': 'grp-dev-001',
}


def api_service(**overrides):
    """A service as the API returns it."""
    base = {
        'id': 'svc-1',
        'domain': 'app.example.com',
        'name': 'app.example.com',
        'mode': 'http',
        'private': False,
        'enabled': True,
        'listen_port': 0,
        'pass_host_header': False,
        'rewrite_redirects': False,
        'access_groups': [{'id': 'grp-abc-123'}],
        'targets': [{
            'target_id': 'res-1',
            'target_type': 'subnet',
            'host': '10.0.0.1',
            'port': 8080,
            'path': '/',
            'protocol': 'http',
            'enabled': True,
            'options': {
                'direct_upstream': True,
                'skip_tls_verify': False,
                'path_rewrite': 'preserve',
                'proxy_protocol': False,
            },
        }],
        'auth': {
            'bearer_auth': {'enabled': False, 'distribution_groups': []},
            'password_auth': {'enabled': False, 'password': ''},
            'pin_auth': {'enabled': False, 'pin': ''},
        },
        'meta': {},
        'proxy_cluster': 'cluster-1',
    }
    base.update(overrides)
    return base


def exported_service(**overrides):
    """A service as the export template writes it (module input shape)."""
    base = {
        'domain': 'app.example.com',
        'private': False,
        'enabled': True,
        'access_groups': ['ci-test-group'],
        'targets': [{
            'host': '10.0.0.1',
            'port': 8080,
            'protocol': 'http',
            'target_id': 'res-1',
            'target_type': 'subnet',
            'enabled': True,
            'direct_upstream': True,
            'skip_tls_verify': False,
        }],
        'state': 'present',
    }
    base.update(overrides)
    return base


class TestAccessGroupResolution:

    def test_exported_names_match_api_ids(self):
        """The core fix: name→ID resolution prevents false positives."""
        diffs = _compare_service(
            api_service(), exported_service(), group_ids=GROUP_IDS)
        assert not any('access_groups' in d for d in diffs)

    def test_without_group_ids_names_differ(self):
        diffs = _compare_service(api_service(), exported_service())
        assert any('access_groups' in d for d in diffs)

    def test_raw_ids_in_config_still_work(self):
        svc = exported_service(access_groups=['grp-abc-123'])
        diffs = _compare_service(api_service(), svc, group_ids=GROUP_IDS)
        assert not any('access_groups' in d for d in diffs)


class TestTargetNormalization:

    def test_flat_vs_nested_options_are_equal(self):
        """Export writes flat keys; API returns nested options dict."""
        diffs = _compare_service(
            api_service(), exported_service(), group_ids=GROUP_IDS)
        assert not any('targets' in d for d in diffs)

    def test_a_real_target_change_is_detected(self):
        changed = exported_service(targets=[{
            'host': '10.0.0.2',
            'port': 9090,
            'protocol': 'http',
            'target_id': 'res-1',
            'target_type': 'subnet',
            'enabled': True,
        }])
        diffs = _compare_service(api_service(), changed, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_skip_tls_change_detected(self):
        changed = exported_service(targets=[{
            'host': '10.0.0.1',
            'port': 8080,
            'protocol': 'http',
            'target_id': 'res-1',
            'target_type': 'subnet',
            'enabled': True,
            'direct_upstream': True,
            'skip_tls_verify': True,
        }])
        diffs = _compare_service(api_service(), changed, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)


class TestAuthDeclaredKeys:

    def test_bearer_only_does_not_report_other_schemes_removed(self):
        """Export omits password_auth and pin_auth when only bearer is
        enabled. The diff must not flag those as removed."""
        current = api_service(auth={
            'bearer_auth': {
                'enabled': True,
                'distribution_groups': ['grp-abc-123'],
            },
            'password_auth': {'enabled': False, 'password': ''},
            'pin_auth': {'enabled': False, 'pin': ''},
        })
        desired = exported_service(auth={
            'bearer_auth': {
                'enabled': True,
                'distribution_groups': ['ci-test-group'],
            },
        })
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert not any('password_auth' in d for d in diffs)
        assert not any('pin_auth' in d for d in diffs)

    def test_bearer_distribution_groups_resolved(self):
        current = api_service(auth={
            'bearer_auth': {
                'enabled': True,
                'distribution_groups': ['grp-abc-123'],
            },
            'password_auth': {'enabled': False, 'password': ''},
            'pin_auth': {'enabled': False, 'pin': ''},
        })
        desired = exported_service(auth={
            'bearer_auth': {
                'enabled': True,
                'distribution_groups': ['ci-test-group'],
            },
        })
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert not any('distribution_groups' in d for d in diffs)

    def test_no_auth_in_desired_skips_auth_comparison(self):
        diffs = _compare_service(api_service(), exported_service(),
                                 group_ids=GROUP_IDS)
        assert not any('auth' in d for d in diffs)

    def test_real_auth_change_is_detected(self):
        desired = exported_service(auth={
            'bearer_auth': {'enabled': True, 'distribution_groups': []},
        })
        current = api_service(auth={
            'bearer_auth': {'enabled': False, 'distribution_groups': []},
            'password_auth': {'enabled': False, 'password': ''},
            'pin_auth': {'enabled': False, 'pin': ''},
        })
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('enabled' in d for d in diffs)


class TestPerTargetKeyFiltering:
    """Optional keys must be filtered per matched target, not globally.

    When two targets exist and only one declares an optional key like
    skip_tls_verify, the API's default value on the other target must not
    leak into the comparison and produce a false positive.
    """

    def test_mixed_optional_keys_no_false_positive(self):
        current = api_service(targets=[
            {'target_id': 'res-1', 'host': '10.0.0.1', 'port': 8080,
             'protocol': 'http', 'target_type': 'subnet', 'enabled': True,
             'path': '/',
             'options': {'direct_upstream': True, 'skip_tls_verify': True,
                         'path_rewrite': 'preserve', 'proxy_protocol': False}},
            {'target_id': 'res-2', 'host': '10.0.0.2', 'port': 9090,
             'protocol': 'http', 'target_type': 'subnet', 'enabled': True,
             'path': '/',
             'options': {'direct_upstream': True, 'skip_tls_verify': False,
                         'path_rewrite': 'preserve', 'proxy_protocol': False}},
        ])
        desired = exported_service(targets=[
            {'target_id': 'res-1', 'host': '10.0.0.1', 'port': 8080,
             'protocol': 'http', 'target_type': 'subnet', 'enabled': True,
             'direct_upstream': True, 'skip_tls_verify': True},
            {'target_id': 'res-2', 'host': '10.0.0.2', 'port': 9090,
             'protocol': 'http', 'target_type': 'subnet', 'enabled': True,
             'direct_upstream': True},
        ])
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert not any('targets' in d for d in diffs)

    def test_real_change_on_declared_key_still_detected(self):
        current = api_service(targets=[
            {'target_id': 'res-1', 'host': '10.0.0.1', 'port': 8080,
             'protocol': 'http', 'target_type': 'subnet', 'enabled': True,
             'path': '/',
             'options': {'direct_upstream': True, 'skip_tls_verify': False,
                         'path_rewrite': 'preserve', 'proxy_protocol': False}},
            {'target_id': 'res-2', 'host': '10.0.0.2', 'port': 9090,
             'protocol': 'http', 'target_type': 'subnet', 'enabled': True,
             'path': '/',
             'options': {'direct_upstream': True, 'skip_tls_verify': False,
                         'path_rewrite': 'preserve', 'proxy_protocol': False}},
        ])
        desired = exported_service(targets=[
            {'target_id': 'res-1', 'host': '10.0.0.1', 'port': 8080,
             'protocol': 'http', 'target_type': 'subnet', 'enabled': True,
             'direct_upstream': True, 'skip_tls_verify': True},
            {'target_id': 'res-2', 'host': '10.0.0.2', 'port': 9090,
             'protocol': 'http', 'target_type': 'subnet', 'enabled': True,
             'direct_upstream': True},
        ])
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)


class TestFullRoundTrip:
    """End-to-end through netbird_diff with service resource_type."""

    def test_freshly_exported_config_reports_no_changes(self):
        current_map = {'app.example.com': api_service()}
        desired_list = [exported_service()]
        result = netbird_diff(desired_list, current_map, 'service',
                              key_field='domain', group_ids=GROUP_IDS)
        assert result['changed'] == {}
        assert result['unchanged'] == ['app.example.com']

    def test_a_real_change_is_still_detected(self):
        current_map = {'app.example.com': api_service()}
        desired_list = [exported_service(private=True)]
        result = netbird_diff(desired_list, current_map, 'service',
                              key_field='domain', group_ids=GROUP_IDS)
        assert 'app.example.com' in result['changed']


def api_path_target(path, access_action='inherit'):
    """A path-routed target as the API returns it: one resource and port,
    many paths, which is how per-target access actions are set up."""
    return {
        'target_id': 'res-1',
        'target_type': 'host',
        'host': '10.0.0.1',
        'port': 8080,
        'path': path,
        'access_action': access_action,
        'protocol': 'http',
        'enabled': True,
        'options': {'direct_upstream': True, 'skip_tls_verify': False,
                    'path_rewrite': 'preserve', 'proxy_protocol': False},
    }


def exported_path_target(path, access_action=None):
    """The same target in config form: path omitted for ``/``, and
    access_action only when given (the export states it for every target;
    a hand-written config may leave it out)."""
    target = {
        'host': '10.0.0.1',
        'port': 8080,
        'protocol': 'http',
        'target_id': 'res-1',
        'target_type': 'host',
        'enabled': True,
        'direct_upstream': True,
    }
    if path != '/':
        target['path'] = path
    if access_action:
        target['access_action'] = access_action
    return target


class TestPathRoutedTargets:
    """Targets that share a resource and port were matched to a single
    desired target, so the keys one declared (path, access_action) were
    compared on the others and an unedited export read as changed."""

    def _current(self):
        return api_service(targets=[
            api_path_target('/'),
            api_path_target('/public/', 'bypass'),
            api_path_target('/admin', 'block'),
        ])

    def _exported(self, admin_action='block'):
        return exported_service(targets=[
            exported_path_target('/'),
            exported_path_target('/public/', 'bypass'),
            exported_path_target('/admin', admin_action),
        ])

    def test_freshly_exported_multi_path_service_reports_no_changes(self):
        """The regression."""
        assert _compare_service(self._current(), self._exported(),
                                group_ids=GROUP_IDS) == []

    def test_an_export_that_states_inherit_previews_clean(self):
        """The export writes the action for every target, inherit included."""
        desired = exported_service(targets=[
            exported_path_target('/', 'inherit'),
            exported_path_target('/public/', 'bypass'),
            exported_path_target('/admin', 'block'),
        ])
        assert _compare_service(self._current(), desired, group_ids=GROUP_IDS) == []

    def test_an_inherit_drift_is_detected(self):
        """A path made public in the dashboard after the export shows up."""
        current = self._current()
        desired = exported_service(targets=[
            exported_path_target('/', 'inherit'),
            exported_path_target('/public/', 'bypass'),
            exported_path_target('/admin', 'block'),
        ])
        current['targets'][0]['access_action'] = 'bypass'
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_inherit_against_a_server_without_the_field_is_not_a_change(self):
        """Such a server applies the service's authentication everywhere,
        which is what inherit means."""
        target = api_path_target('/admin')
        del target['access_action']
        current = api_service(targets=[target])
        desired = exported_service(targets=[exported_path_target('/admin', 'inherit')])
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_subnet_targets_on_one_resource_pair_by_host(self):
        def subnet(host, action):
            t = api_path_target('/', action)
            t.update(target_type='subnet', host=host)
            return t

        def exported(host, action):
            t = exported_path_target('/', action)
            t.update(target_type='subnet', host=host)
            return t
        # One target states its action, the other (hand-written) does not;
        # paired with the wrong one, the stated action leaks onto it.
        current = api_service(targets=[subnet('10.0.0.1', 'block'), subnet('10.0.0.2', 'inherit')])
        desired = exported_service(targets=[exported('10.0.0.2', None), exported('10.0.0.1', 'block')])
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_an_enabled_target_and_its_standby_pair_one_to_one(self):
        """They share every key field; a change to only the enabled one must
        not be hidden by the standby, nor an unchanged pair reported."""
        def api(action, enabled):
            return dict(api_path_target('/admin', action), enabled=enabled)

        def cfg(action, enabled):
            return dict(exported_path_target('/admin', action), enabled=enabled)
        current = api_service(targets=[api('block', True), api('inherit', False)])
        same = exported_service(targets=[cfg(None, False), cfg('block', True)])
        assert _compare_service(current, same, group_ids=GROUP_IDS) == []
        edited = exported_service(targets=[cfg('inherit', False), cfg('bypass', True)])
        diffs = _compare_service(current, edited, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_standbys_sharing_a_key_pair_by_protocol_not_order(self):
        def api(protocol, action):
            return dict(api_path_target('/admin', action), enabled=False, protocol=protocol)

        def cfg(protocol, action):
            return dict(exported_path_target('/admin', action), enabled=False, protocol=protocol)
        current = api_service(targets=[api('http', 'inherit'), api('https', 'block')])
        desired = exported_service(targets=[cfg('https', 'block'), cfg('http', None)])
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_a_config_target_without_protocol_ranks_as_http(self):
        def api(protocol, action):
            return dict(api_path_target('/admin', action), enabled=False, protocol=protocol)
        http = dict(exported_path_target('/admin', None), enabled=False)
        del http['protocol']
        https = dict(exported_path_target('/admin', 'block'), enabled=False, protocol='https')
        current = api_service(targets=[api('http', 'inherit'), api('https', 'block')])
        desired = exported_service(targets=[https, http])
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_a_null_action_is_unset(self):
        """The module keeps the current action for a null one."""
        current = api_service(targets=[api_path_target('/admin', 'block')])
        desired = exported_service(targets=[dict(exported_path_target('/admin'), access_action=None)])
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_standbys_differing_in_a_declared_option_pair_by_it(self):
        def api(skip):
            t = dict(api_path_target('/admin', 'block'), enabled=False, protocol='https')
            t['options'] = dict(t['options'], skip_tls_verify=skip)
            return t

        def cfg(skip):
            t = dict(exported_path_target('/admin', 'block'), enabled=False, protocol='https')
            if skip:
                t['skip_tls_verify'] = True
            return t
        current = api_service(targets=[api(False), api(True)])
        assert _compare_service(current, exported_service(targets=[cfg(True), cfg(False)]),
                                group_ids=GROUP_IDS) == []
        assert _compare_service(current, exported_service(targets=[cfg(False), cfg(True)]),
                                group_ids=GROUP_IDS) == []
        edited = exported_service(targets=[cfg(True), cfg(True)])
        assert any('targets' in d for d in _compare_service(current, edited, group_ids=GROUP_IDS))

    def test_a_root_path_the_api_leaves_out_matches_path_slash(self):
        target = api_path_target('/')
        del target['path']
        current = api_service(targets=[target])
        desired = exported_service(targets=[dict(exported_path_target('/'), path='/')])
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_an_omitted_path_is_previewed_as_moving_the_target_to_root(self):
        """The module applies a target without ``path`` at ``/``, so against a
        target at ``/api`` that is a change, even with every other field the
        same."""
        current = api_service(targets=[api_path_target('/api')])
        desired = exported_service(targets=[exported_path_target('/')])
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_an_edited_access_action_is_detected(self):
        diffs = _compare_service(self._current(), self._exported('bypass'),
                                 group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_an_undeclared_access_action_is_not_reported(self):
        """Omitting it keeps the current action on apply, so preview must not
        claim it will be reset."""
        assert _compare_service(self._current(), self._exported(None),
                                group_ids=GROUP_IDS) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

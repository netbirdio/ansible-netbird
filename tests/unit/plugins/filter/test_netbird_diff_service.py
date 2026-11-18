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


class TestOmittedFalseOptions:
    """The API leaves a boolean option out of ``options`` when it is false.
    The export now states ``direct_upstream`` either way (netbird_service
    defaults it to true, so omitting it flipped targets on apply), and an
    explicit false must read as equal to an omitted one."""

    def _api(self, **options):
        target = api_service()['targets'][0]
        target['options'] = dict(options)
        return api_service(targets=[target])

    def _exported(self, **flags):
        target = dict(exported_service()['targets'][0])
        target.pop('skip_tls_verify', None)
        target.update(flags)
        return exported_service(targets=[target])

    def test_explicit_false_matches_an_omitted_option(self):
        current = self._api(path_rewrite='preserve')
        desired = self._exported(direct_upstream=False)
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_explicit_true_against_an_omitted_option_is_a_change(self):
        current = self._api(path_rewrite='preserve')
        desired = self._exported(direct_upstream=True)
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_exported_proxy_protocol_matches(self):
        current = self._api(direct_upstream=True, proxy_protocol=True)
        desired = self._exported(direct_upstream=True, proxy_protocol=True)
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_an_omitted_direct_upstream_is_previewed_as_the_module_applies_it(self):
        """A config without direct_upstream (an older export, or written by
        hand) is applied with the module default, true. Against a target that
        dials through the tunnel that is a change, and the preview must say so
        rather than skip the key."""
        current = self._api(path_rewrite='preserve')
        desired = exported_service(targets=[{
            k: v for k, v in exported_service()['targets'][0].items()
            if k not in ('direct_upstream', 'skip_tls_verify')}])
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_an_omitted_proxy_protocol_is_previewed_as_turned_off(self):
        """The module sends false for it, which turns off one that is on."""
        current = self._api(direct_upstream=True, proxy_protocol=True)
        desired = self._exported(direct_upstream=True)
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_null_api_options_read_as_all_false(self):
        current = api_service()
        current['targets'][0]['options'] = None
        desired = self._exported(direct_upstream=False)
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_api_target_without_options_reads_as_all_false(self):
        """Older servers leave ``options`` out when no option is set. That is
        still an API target, not a config one with module defaults."""
        current = api_service()
        del current['targets'][0]['options']
        desired = self._exported(direct_upstream=False)
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_a_null_config_option_is_reported(self):
        """Left empty in YAML it is an explicit null, which the module rejects
        rather than defaulting; the preview must not call it unchanged."""
        current = self._api(direct_upstream=True)
        desired = self._exported(direct_upstream=None)
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    @pytest.mark.parametrize('value', ['off', 'no', 'false', 'False', '0', 0, 0.0])
    def test_a_quoted_false_reads_as_false(self, value):
        """The module converts these when parsing its arguments."""
        current = self._api(path_rewrite='preserve')
        desired = self._exported(direct_upstream=value)
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_numeric_true_does_not_reorder_targets(self):
        """1 sorts differently from True; left unconverted, two unchanged
        targets were paired out of order."""
        def api(port):
            t = api_service()['targets'][0]
            t.update(port=port, options={'direct_upstream': True})
            return t

        def cfg(port, **flags):
            t = {k: v for k, v in exported_service()['targets'][0].items() if k != 'direct_upstream'}
            t.update(port=port, **flags)
            return t
        current = api_service(targets=[api(8080), api(8081)])
        desired = exported_service(targets=[cfg(8080), cfg(8081, direct_upstream=1)])
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []

    def test_an_unrecognised_string_is_reported(self):
        current = self._api(path_rewrite='preserve')
        desired = self._exported(direct_upstream='sometimes')
        diffs = _compare_service(current, desired, group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    @pytest.mark.parametrize('nested', [{'direct_upstream': True}, None])
    def test_nested_options_in_a_config_are_reported(self, nested):
        """netbird_service rejects targets[].options, null included. The API
        side matches the module defaults here, so only the unsupported key
        itself can make the difference."""
        current = self._api(direct_upstream=True, path_rewrite='preserve')
        target = {k: v for k, v in exported_service()['targets'][0].items()
                  if k not in ('direct_upstream', 'skip_tls_verify')}
        target['options'] = nested
        diffs = _compare_service(current, exported_service(targets=[target]), group_ids=GROUP_IDS)
        assert any('targets' in d for d in diffs)

    def test_without_nested_options_the_same_target_is_unchanged(self):
        """The control case for the test above."""
        current = self._api(direct_upstream=True, path_rewrite='preserve')
        target = {k: v for k, v in exported_service()['targets'][0].items()
                  if k not in ('direct_upstream', 'skip_tls_verify')}
        assert _compare_service(current, exported_service(targets=[target]), group_ids=GROUP_IDS) == []

    def test_omitted_options_matching_the_module_defaults_are_not_a_change(self):
        current = self._api(direct_upstream=True)
        desired = exported_service(targets=[{
            k: v for k, v in exported_service()['targets'][0].items()
            if k not in ('direct_upstream', 'skip_tls_verify')}])
        assert _compare_service(current, desired, group_ids=GROUP_IDS) == []


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# -*- coding: utf-8 -*-
# Copyright: (c) 2024-2026, NetBird and contributors
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the export role's services template.

Run via:
    ansible-test units --docker default

The API leaves a boolean target option out of ``options`` when it is false,
while ``netbird_service`` defaults ``direct_upstream`` to true and
``proxy_protocol`` to false. Whatever the template leaves out is therefore
applied with the module default, so it has to state ``direct_upstream`` in
every case and ``proxy_protocol`` whenever it is on.

The template is rendered with Ansible's own templar, so the filters are the
ones the export role uses. No request is made.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os

import pytest
import yaml

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

try:
    # ansible-core 2.19+ renders only template strings marked as trusted.
    from ansible.template import trust_as_template
except ImportError:
    def trust_as_template(value):
        return value

TEMPLATE = os.path.join(
    os.path.dirname(__file__), '..', '..', '..',
    'roles', 'export', 'templates', 'export', 'services.yml.j2')


def render(targets, mode='http'):
    service = {
        'id': 'svc-1',
        'domain': 'app.example.com',
        'name': 'app.example.com',
        'mode': mode,
        'private': False,
        'enabled': True,
        'targets': targets,
    }
    variables = {
        'netbird_api_url': 'https://netbird.example.com',
        'ansible_date_time': {'date': '2026-01-01'},
        'services_data': {'data': [service]},
        'service_domains_data': {'data': []},
        'group_id_map': {},
    }
    with open(TEMPLATE, encoding='utf-8') as f:
        source = f.read()
    rendered = Templar(loader=DataLoader(), variables=variables).template(trust_as_template(source))
    return yaml.safe_load(rendered)['netbird_services'][0]['targets']


def api_target(options=None, omit_options=False, **overrides):
    target = {
        'target_id': 'res-1',
        'target_type': 'subnet',
        'host': '10.0.0.1',
        'port': 8080,
        'path': '/',
        'protocol': 'http',
        'enabled': True,
    }
    if not omit_options:
        target['options'] = options
    target.update(overrides)
    return target


class TestDirectUpstream:

    @pytest.mark.parametrize('options', [{}, {'path_rewrite': 'preserve'}, None])
    def test_written_as_false_when_the_api_omits_it(self, options):
        """The regression: left out, it was applied as true."""
        assert render([api_target(options)])[0]['direct_upstream'] is False

    def test_written_as_false_when_options_are_missing(self):
        assert render([api_target(omit_options=True)])[0]['direct_upstream'] is False

    def test_written_as_false_when_null(self):
        assert render([api_target({'direct_upstream': None})])[0]['direct_upstream'] is False

    def test_written_as_false_when_false(self):
        assert render([api_target({'direct_upstream': False})])[0]['direct_upstream'] is False

    def test_written_as_true(self):
        assert render([api_target({'direct_upstream': True})])[0]['direct_upstream'] is True


class TestProxyProtocol:

    def test_written_when_on(self):
        """The regression: never exported, so applied as false."""
        targets = render([api_target({'direct_upstream': True, 'proxy_protocol': True},
                                     protocol='tcp')], mode='tcp')
        assert targets[0]['proxy_protocol'] is True

    @pytest.mark.parametrize('options', [{}, {'proxy_protocol': False}])
    def test_left_out_when_off(self, options):
        """False is the module default, so it is left out like before."""
        assert 'proxy_protocol' not in render([api_target(options)])[0]


class TestOtherOptionsUnchanged:

    def test_skip_tls_verify_and_path_rewrite(self):
        target = render([api_target({'skip_tls_verify': True, 'path_rewrite': 'preserve'})])[0]
        assert target['skip_tls_verify'] is True
        assert 'path_rewrite' not in target


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

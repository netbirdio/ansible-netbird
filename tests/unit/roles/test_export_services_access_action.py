# -*- coding: utf-8 -*-
# Copyright: (c) 2024-2026, NetBird and contributors
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for how the export role's services template writes access_action.

Run via:
    ansible-test units --docker default

The action is written for every target the server reports it on, inherit
included, so applying an export enforces it: an omitted action would keep
whatever the dashboard has since set. A server without per-target actions
does not report the field, and nothing is written.

The template is rendered with Ansible's own templar. No request is made.
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


def render(targets):
    variables = {
        'netbird_api_url': 'https://netbird.example.com',
        'ansible_date_time': {'date': '2026-01-01'},
        'services_data': {'data': [{
            'id': 'svc-1', 'domain': 'app.example.com', 'name': 'app.example.com',
            'mode': 'http', 'private': False, 'enabled': True, 'targets': targets,
        }]},
        'service_domains_data': {'data': []},
        'group_id_map': {},
    }
    with open(TEMPLATE) as f:
        source = f.read()
    rendered = Templar(loader=DataLoader(), variables=variables).template(trust_as_template(source))
    return {t.get('path', '/'): t for t in yaml.safe_load(rendered)['netbird_services'][0]['targets']}


def api_target(path, **extra):
    target = {'target_id': 'res-1', 'target_type': 'host', 'host': '10.0.0.1',
              'port': 8080, 'path': path, 'protocol': 'http', 'enabled': True,
              'options': {}}
    target.update(extra)
    return target


class TestAccessActionExport:

    @pytest.mark.parametrize('action', ['inherit', 'bypass', 'block'])
    def test_written_as_reported(self, action):
        assert render([api_target('/admin', access_action=action)])['/admin']['access_action'] == action

    def test_inherit_is_written_so_an_apply_enforces_it(self):
        """Left out, the apply would keep a Bypass set in the dashboard later."""
        targets = render([api_target('/', access_action='inherit'),
                          api_target('/admin', access_action='block')])
        assert targets['/']['access_action'] == 'inherit'

    def test_left_out_when_the_server_does_not_report_it(self):
        assert 'access_action' not in render([api_target('/')])['/']

    @pytest.mark.parametrize('value', [None, ''])
    def test_left_out_when_empty(self, value):
        assert 'access_action' not in render([api_target('/', access_action=value)])['/']


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

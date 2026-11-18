# -*- coding: utf-8 -*-
# Copyright: (c) 2024-2026, NetBird and contributors
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for value pre-flight checks in netbird_resolve.

Run via:
    ansible-test units --docker default

Setup-key ``expires_in`` must be a non-negative integer: the API accepts
0 as "never expires" and rejects negative values.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible_collections.community.ansible_netbird.plugins.filter.netbird_resolve import (
    netbird_value_problems,
)


def _keys(value):
    return [{'name': 'k', 'expires_in': value}]


@pytest.mark.parametrize('value', [0, '0', 1, 86400])
def test_non_negative_integer_accepted(value):
    assert netbird_value_problems([], setup_keys=_keys(value)) == []


@pytest.mark.parametrize('value', [-1, '-5', 'abc'])
def test_negative_or_non_integer_rejected(value):
    problems = netbird_value_problems([], setup_keys=_keys(value))
    assert len(problems) == 1
    assert "expires_in" in problems[0]

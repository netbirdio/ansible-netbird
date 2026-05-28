# -*- coding: utf-8 -*-
# Copyright: (c) 2024-2026, NetBird and contributors
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the shared module_utils helpers.

Run via:
    ansible-test units --docker default

These tests are deliberately scoped to pure-Python helpers that do not
make API calls. Integration coverage of API-touching code lives in the
external ansible-netbird-testing harness.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPIError,
    extract_ids,
)


class TestExtractIds:
    """`extract_ids` normalises the two shapes the API returns for related
    objects -- dicts with an `id` key, and plain ID strings -- into a flat
    list of strings so callers can safely use `set()` for comparison."""

    def test_empty_input_returns_empty_list(self):
        assert extract_ids([]) == []
        assert extract_ids(None) == []

    def test_dict_items_extract_id_field(self):
        items = [{"id": "abc", "name": "alpha"}, {"id": "def", "name": "beta"}]
        assert extract_ids(items) == ["abc", "def"]

    def test_string_items_pass_through(self):
        assert extract_ids(["abc", "def"]) == ["abc", "def"]

    def test_mixed_items_normalise(self):
        items = [{"id": "abc"}, "def", {"id": "ghi", "name": "x"}]
        assert extract_ids(items) == ["abc", "def", "ghi"]


class TestNetBirdAPIError:
    """The exception type used by the API client to surface HTTP / SSL /
    connectivity failures back to modules."""

    def test_message_is_propagated(self):
        e = NetBirdAPIError("boom")
        assert str(e) == "boom"
        assert e.message == "boom"

    def test_status_code_and_response_are_stored(self):
        e = NetBirdAPIError("nope", status_code=404, response={"error": "Not Found"})
        assert e.status_code == 404
        assert e.response == {"error": "Not Found"}

    def test_defaults_are_none(self):
        e = NetBirdAPIError("just a string")
        assert e.status_code is None
        assert e.response is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

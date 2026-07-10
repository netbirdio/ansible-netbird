# -*- coding: utf-8 -*-
# Copyright: (c) 2024-2026, NetBird and contributors
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the NetBird API client transport hardening.

Covers the security-relevant request behaviour: HTTPS enforcement warning,
refusing to follow redirects (so the auth token is not replayed to another
host), and percent-encoding of resource IDs in request paths. open_url is
mocked, so no network calls are made.

Run via:
    ansible-test units --docker default
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible_collections.community.ansible_netbird.plugins.module_utils import (
    netbird_api,
)
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    _q,
)


class FakeModule:
    """Minimal stand-in for AnsibleModule capturing warnings."""

    def __init__(self):
        self.warnings = []

    def warn(self, msg):
        self.warnings.append(msg)


class FakeResponse:
    def __init__(self, code=200, body=b'{"ok": true}'):
        self._code = code
        self._body = body

    def getcode(self):
        return self._code

    def read(self):
        return self._body


def make_api(url="https://nb.example.com"):
    return FakeModule(), None, url


class TestQuoteHelper:
    def test_encodes_path_separator(self):
        assert _q("a/b") == "a%2Fb"

    def test_encodes_query_and_fragment(self):
        assert _q("a?x=1#f") == "a%3Fx%3D1%23f"

    def test_leaves_safe_chars(self):
        assert _q("Ab-9_x.y~z") == "Ab-9_x.y~z"

    def test_coerces_non_str(self):
        assert _q(123) == "123"


class TestHttpsWarning:
    def test_http_url_warns(self):
        fm = FakeModule()
        NetBirdAPI(fm, "http://nb.example.com", "tok")
        assert any("cleartext" in w for w in fm.warnings)

    def test_https_url_is_quiet(self):
        fm = FakeModule()
        NetBirdAPI(fm, "https://nb.example.com", "tok")
        assert fm.warnings == []


class TestRequestTransport:
    def _api(self, monkeypatch, response):
        captured = {}

        def fake_open_url(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return response

        monkeypatch.setattr(netbird_api, "open_url", fake_open_url)
        return NetBirdAPI(FakeModule(), "https://nb.example.com", "tok"), captured

    def test_does_not_follow_redirects(self, monkeypatch):
        api, captured = self._api(monkeypatch, FakeResponse())
        api.get("/api/groups/abc")
        assert captured["kwargs"].get("follow_redirects") == "none"

    def test_3xx_is_rejected(self, monkeypatch):
        api, _unused = self._api(monkeypatch, FakeResponse(code=302, body=b""))
        with pytest.raises(NetBirdAPIError) as exc:
            api.get("/api/groups/abc")
        assert exc.value.status_code == 302

    def test_resource_id_is_percent_encoded(self, monkeypatch):
        api, captured = self._api(monkeypatch, FakeResponse())
        api.get_group("evil/../admin?x=1#f")
        tail = captured["url"].split("/api/groups/", 1)[1]
        assert tail == "evil%2F..%2Fadmin%3Fx%3D1%23f"
        assert "/" not in tail  # no raw separator survived

    def test_nested_ids_encoded(self, monkeypatch):
        api, captured = self._api(monkeypatch, FakeResponse())
        api.get_dns_zone_record("z/1", "r/2")
        assert "z%2F1" in captured["url"]
        assert "r%2F2" in captured["url"]

    def test_normal_2xx_passes_through(self, monkeypatch):
        api, _unused = self._api(monkeypatch, FakeResponse(code=200))
        data, code = api.get("/api/groups/abc")
        assert code == 200
        assert data == {"ok": True}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

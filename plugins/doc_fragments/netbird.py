# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


class ModuleDocFragment:
    """Documentation fragment for NetBird modules."""

    DOCUMENTATION = r'''
options:
  api_url:
    description:
      - The URL of the NetBird API.
      - Can also be set via the C(NETBIRD_API_URL) environment variable.
    type: str
    required: true
  api_token:
    description:
      - Personal Access Token for NetBird API authentication.
      - Can also be set via the C(NETBIRD_API_TOKEN) environment variable.
    type: str
    required: true
  validate_certs:
    description:
      - Whether to validate SSL certificates.
    type: bool
    default: true
'''

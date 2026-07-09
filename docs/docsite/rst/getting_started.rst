.. _ansible_collections.community.ansible_netbird.docsite.getting_started:

*******************************************
Getting started with the NetBird collection
*******************************************

The ``community.ansible_netbird`` collection manages NetBird resources — users,
groups, peers, setup keys, policies, networks, DNS, posture checks, and identity
providers — declaratively against the `NetBird REST API
<https://docs.netbird.io/api>`__. Use it to keep your tenant configuration in
version control and reapply it from CI.

The collection talks to the API of an existing NetBird instance. It does not
install the NetBird client on machines and does not deploy the self-hosted
server. It works against any NetBird tenant, cloud or self-hosted, that you can
reach with a Personal Access Token.

.. contents::
   :local:
   :depth: 1

Requirements
============

- ansible-core 2.15 or newer.
- Python 3.9 or newer on the control node.
- The Management API URL for your NetBird instance, for example
  ``https://netbird.example.com``.
- A Personal Access Token (PAT) for a NetBird admin or service user.

Install the collection
=======================

The collection is not yet published to Ansible Galaxy. Build and install it from
source:

.. code-block:: bash

    git clone https://github.com/netbirdio/ansible-netbird.git
    cd ansible-netbird
    ansible-galaxy collection build
    ansible-galaxy collection install community-ansible_netbird-*.tar.gz

Authenticate
============

Every module needs the Management API URL and a PAT. The simplest option for
local runs and CI is a pair of environment variables:

.. code-block:: bash

    export NETBIRD_API_URL="https://netbird.example.com"
    export NETBIRD_API_TOKEN="nbp_EXAMPLEtokenvalue000000000000000000"

.. note::

    Set ``api_url`` to the base URL of your instance; do not include ``/api``.
    The collection appends API paths automatically. Store the PAT in Ansible
    Vault or your CI secret store, and never commit it to source control.

When your credentials come from Ansible Vault or group variables, set them once
for every module with ``module_defaults`` and the collection's action group:

.. code-block:: yaml

    module_defaults:
      group/community.ansible_netbird.netbird:
        api_url: "{{ netbird_api_url }}"
        api_token: "{{ netbird_api_token }}"

On ansible-core 2.15, place ``module_defaults`` at the block level rather than
the play level to avoid a variable-resolution timing issue when the values come
from group variables.

First playbook
==============

This playbook creates a group and a reusable setup key bound to that group, then
saves the key's secret, which the API returns only when the key is first
created:

.. code-block:: yaml

    - name: Configure NetBird tenant
      hosts: localhost
      gather_facts: false
      tasks:
        - name: Create a group for servers
          community.ansible_netbird.netbird_group:
            name: servers
            state: present
          register: servers_group

        - name: Create a reusable setup key for servers
          community.ansible_netbird.netbird_setup_key:
            name: server-enrollment
            key_type: reusable
            expires_in: 604800
            auto_groups:
              - "{{ servers_group.group.id }}"
            state: present
          register: setup_key

        - name: Save the setup key (returned only on creation)
          ansible.builtin.copy:
            content: "{{ setup_key.setup_key.key }}"
            dest: ./server-enrollment.key
            mode: "0600"
          no_log: true
          when: setup_key.setup_key.key is defined

``auto_groups`` takes group IDs, not names, so the setup-key task references the
group created in the first task. Never print a setup key with ``debug``: Ansible
cannot mask a single return value, so keep ``no_log: true`` on any task that
handles it. Re-running the playbook is safe, because every module is idempotent.

Manage a whole tenant as code
=============================

To manage an entire tenant declaratively — export the current state to YAML,
review a diff, then apply it — use the ``configure`` role together with the
``export_netbird_config`` and ``configure_netbird`` playbooks. See the
`Configuration as Code guide
<https://github.com/netbirdio/ansible-netbird/blob/main/docs/guide_netbird_config_as_code.md>`__.

Next steps
==========

- The full walkthrough, with more examples and troubleshooting, lives at
  `Configure NetBird with Ansible <https://docs.netbird.io/selfhosted/iac/ansible>`__.
- The `examples/ directory
  <https://github.com/netbirdio/ansible-netbird/tree/main/examples>`__ has
  runnable playbooks, from dynamic policies to a complete tenant setup.
- Every resource type has a module; browse the module reference for options,
  return values, and per-module examples.

# Ansible Collection for NetBird

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![ansible-test](https://github.com/netbirdio/ansible-netbird/actions/workflows/ansible-test.yml/badge.svg)](https://github.com/netbirdio/ansible-netbird/actions/workflows/ansible-test.yml)

An Ansible collection for managing [NetBird](https://netbird.io) self-hosted infrastructure via the [NetBird REST API](https://docs.netbird.io/api).

## Features

This collection provides comprehensive management of NetBird resources:

- **Users** - Create, update, delete regular and service users
- **Groups** - Organize peers into logical groups
- **Peers** - Manage peer settings (SSH, expiration, etc.)
- **Setup Keys** - Create enrollment keys for new peers
- **Policies** - Define network access rules between groups
- **Networks** - Configure network routing with routers and resources
  - IP/CIDR routing (`172.16.0.0/16`, `192.168.1.0/24`)
  - Domain-based routing (`example.com`, `*.corp.example.com`)
  - High availability with multiple routers and metrics
- **Routes** - Manage legacy routes (deprecated, use Networks instead)
- **Services** - Publish internal apps through the NetBird reverse proxy (HTTP, TCP, UDP, TLS)
- **DNS** - Configure nameserver groups and DNS settings
- **DNS Zones** - Manage DNS zones with A, AAAA, and CNAME records
- **Posture Checks** - Define security compliance requirements
- **Accounts** - Manage account-wide settings (including extra settings, auto-update, peer expose)
- **Tokens** - Create and manage personal access tokens
- **Identity Providers** - Configure identity providers (Google, Okta, Entra, OIDC, etc.)
- **Invites** - Manage user invite links with expiration and regeneration
- **Service Domains** - Manage custom domains for reverse-proxy services
- **Agent Network (AI Gateway)** - Manage AI providers, access policies, guardrails, budget rules, and gateway settings
- **Info** - Gather information about any resource (including services, service domains, proxy clusters, and all agent-network resources)

## Requirements

- Ansible >= 2.15
- Python >= 3.9
- A NetBird self-hosted instance with API access
- A NetBird Personal Access Token

## Installation

This collection is not yet published to Ansible Galaxy. Install the tarball
attached to the [latest GitHub Release](https://github.com/netbirdio/ansible-netbird/releases/latest):

```bash
ansible-galaxy collection install \
  https://github.com/netbirdio/ansible-netbird/releases/download/v1.4.1/community-ansible_netbird-1.4.1.tar.gz
```

Or via `requirements.yml`:

```yaml
collections:
  - name: https://github.com/netbirdio/ansible-netbird/releases/download/v1.4.1/community-ansible_netbird-1.4.1.tar.gz
```

Alternatively, build and install from source:

```bash
# Clone the repository
git clone https://github.com/netbirdio/ansible-netbird.git

# Build and install the collection
cd ansible-netbird
ansible-galaxy collection build
ansible-galaxy collection install community-ansible_netbird-*.tar.gz
```

## Authentication

All modules require API authentication. You can provide credentials in three ways:

> **Note:** `api_url` is the base URL of your NetBird instance (e.g., `https://netbird.example.com`). Do not include `/api` — the collection appends API paths automatically. A trailing slash is stripped automatically.

### 1. Module Parameters

```yaml
- name: List peers
  community.ansible_netbird.netbird_info:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    resource: peers
```

### 2. Environment Variables

```bash
export NETBIRD_API_URL="https://netbird.example.com"
export NETBIRD_API_TOKEN="your-personal-access-token"
```

```yaml
- name: List peers (uses environment variables)
  community.ansible_netbird.netbird_info:
    resource: peers
```

### 3. Role Variables

```yaml
- hosts: localhost
  vars:
    netbird_api_url: "https://netbird.example.com"
    netbird_api_token: "{{ vault_netbird_token }}"
  roles:
    - community.ansible_netbird
```

## Modules

### netbird_user

Manage NetBird users (regular and service users). When updating an existing user, omitting `auto_groups` preserves the current group assignments rather than clearing them.

```yaml
# Create a regular user
- name: Create user
  community.ansible_netbird.netbird_user:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    email: "user@example.com"
    name: "John Doe"
    role: "user"
    auto_groups:
      - "developers"
    state: present

# Create a service user
- name: Create service user
  community.ansible_netbird.netbird_user:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "automation-service"
    role: "admin"
    is_service_user: true
    state: present
```

### netbird_group

Manage NetBird groups. When updating an existing group, omitting `peers` preserves the current peer membership rather than clearing it.

```yaml
- name: Create a group
  community.ansible_netbird.netbird_group:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "production-servers"
    peers:
      - "peer-id-1"
      - "peer-id-2"
    state: present

# Update name only -- peers are preserved
- name: Rename group without affecting peers
  community.ansible_netbird.netbird_group:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    group_id: "{{ group.id }}"
    name: "prod-servers"
    state: present
```

### netbird_peer

Manage NetBird peer settings.

```yaml
- name: Configure peer
  community.ansible_netbird.netbird_peer:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    peer_id: "peer-id-123"
    name: "production-server-01"
    ssh_enabled: true
    login_expiration_enabled: true
    state: present
```

### netbird_setup_key

Manage NetBird setup keys for peer enrollment. When updating an existing key, omitting `auto_groups` preserves the current group assignments rather than clearing them.

```yaml
- name: Create reusable setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "server-enrollment"
    key_type: "reusable"
    expires_in: 604800  # 7 days
    auto_groups:
      - "servers-group-id"
    ephemeral: false
    state: present
  register: setup_key

# The key secret is returned only on creation. Never print it with debug;
# capture it once and store it in a secret manager.
- name: Save the setup key (returned only on creation)
  ansible.builtin.copy:
    content: "{{ setup_key.setup_key.key }}"
    dest: ./server-enrollment.key
    mode: "0600"
  no_log: true
  when: setup_key.setup_key.key is defined

# Revoke a key without wiping its auto_groups
- name: Revoke setup key (auto_groups preserved)
  community.ansible_netbird.netbird_setup_key:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    key_id: "{{ setup_key.setup_key.id }}"
    revoked: true
    state: present

# A key matched by name that is revoked, expired, or out of uses only warns
# by default. Opt in to replacing it (a new secret is returned once):
- name: Rotate the key when it can no longer enrol peers
  community.ansible_netbird.netbird_setup_key:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "server-enrollment"
    key_type: "reusable"
    expires_in: 604800
    rotate_when_invalid: true
    state: present
```

### netbird_policy

Manage NetBird access policies.

```yaml
- name: Create access policy
  community.ansible_netbird.netbird_policy:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "developers-to-servers"
    description: "Allow developers SSH access to servers"
    enabled: true
    source_posture_checks:
      - "posture-check-id"
    rules:
      - name: "ssh-access"
        sources:
          - "developers-group-id"
        destinations:
          - "servers-group-id"
        bidirectional: false
        protocol: "tcp"
        ports:
          - "22"
        action: "accept"
      - name: "web-access"
        sources:
          - "developers-group-id"
        destinations:
          - "servers-group-id"
        protocol: "tcp"
        port_ranges:
          - start: 8000
            end: 9000
        action: "accept"
    state: present
```

### netbird_network

Manage NetBird networks with routers and resources. This module provides full routing capabilities, replacing the deprecated routes API.

```yaml
# Simple network (container only)
- name: Create simple network
  community.ansible_netbird.netbird_network:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "office-network"
    description: "Main office network"
    state: present

# Full network with routers and resources
- name: Create network with routing
  community.ansible_netbird.netbird_network:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "internal-network"
    description: "Corporate internal network"
    routers:
      - peer: "gateway-peer-id"
        metric: 100
        masquerade: true
    resources:
      - address: "172.16.0.0/16"
        name: "internal-range"
        description: "All internal IPs"
        groups:
          - "all-users-group-id"
    state: present

# HA network with multiple routers
- name: Create HA network with failover
  community.ansible_netbird.netbird_network:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "ha-network"
    description: "High availability network"
    routers:
      - peer_groups:
          - "primary-gateways"
        metric: 100
        masquerade: true
      - peer_groups:
          - "backup-gateways"
        metric: 200
        masquerade: true
    resources:
      - address: "192.168.0.0/16"
        name: "private-networks"
        groups:
          - "developers-group-id"
    state: present

# Domain-based routing
- name: Create network with domain routing
  community.ansible_netbird.netbird_network:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "internal-services"
    description: "Route traffic to internal domains"
    routers:
      - peer: "dns-gateway-peer-id"
        metric: 100
        masquerade: true
    resources:
      - address: "internal.example.com"
        name: "internal-portal"
        groups:
          - "all-users-group-id"
      - address: "*.corp.example.com"
        name: "corp-subdomains"
        description: "All corporate subdomains"
        groups:
          - "employees-group-id"
    state: present
```

### netbird_route

Manage NetBird routes (deprecated API, prefer `netbird_network` with routers/resources).

```yaml
- name: Create route (legacy)
  community.ansible_netbird.netbird_route:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    network_id: "internal-route"
    network: "172.16.0.0/16"
    description: "Route to internal network"
    peer_id: "gateway-peer-id"
    metric: 100
    masquerade: true
    enabled: true
    groups:
      - "all-group-id"
    state: present
```

### netbird_service

Publish an internal application through the NetBird reverse proxy. Targets
ride a network resource (`subnet`/`host`/`domain`), a `peer`, or a `cluster`;
HTTP-only options such as `path_rewrite` are omitted automatically for
TCP/UDP/TLS services.

```yaml
- name: Expose an internal app over the overlay
  community.ansible_netbird.netbird_service:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    domain: "myapp.netbird.example.com"
    private: true
    access_groups:
      - "all-users-group-id"
    targets:
      - host: "10.0.0.30"
        port: 8080
        protocol: http
        target_id: "subnet-resource-id"
        target_type: subnet
    state: present
```

### netbird_dns

Manage NetBird DNS settings and nameserver groups.

```yaml
# Create nameserver group
- name: Create DNS nameserver group
  community.ansible_netbird.netbird_dns:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    resource_type: nameserver_group
    name: "internal-dns"
    nameservers:
      - ip: "10.0.0.53"
        ns_type: "udp"
        port: 53
    groups: []
    domains:
      - "internal.example.com"
    enabled: true
    state: present

# Update DNS settings
- name: Configure DNS settings
  community.ansible_netbird.netbird_dns:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    resource_type: settings
    disabled_management_groups:
      - "special-group-id"
    state: present
```

### netbird_dns_zone

Manage DNS zones and their records. `name` is optional and defaults to the
zone's `domain`; a zone can also be addressed by `domain` alone.

```yaml
- name: Create a DNS zone with records
  community.ansible_netbird.netbird_dns_zone:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    domain: "office.example.com"   # name defaults to the domain
    enabled: true
    distribution_groups:
      - "all-users-group-id"
    records:
      - name: "server1.office.example.com"
        type: "A"
        content: "10.0.1.1"
        ttl: 300
      - name: "mail.office.example.com"
        type: "CNAME"
        content: "mailserver.example.com"
    state: present
```

### netbird_posture_check

Manage NetBird posture checks for security compliance.

```yaml
- name: Create version check
  community.ansible_netbird.netbird_posture_check:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "minimum-version"
    description: "Require minimum NetBird version"
    checks:
      nb_version_check:
        min_version: "0.25.0"
    state: present

- name: Create geo-location check
  community.ansible_netbird.netbird_posture_check:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "allowed-countries"
    checks:
      geo_location_check:
        locations:
          - country_code: "US"
          - country_code: "DE"
        action: "allow"
    state: present
```

### netbird_account

Manage NetBird account settings.

```yaml
- name: Configure account settings
  community.ansible_netbird.netbird_account:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    peer_login_expiration_enabled: true
    peer_login_expiration: 604800
    peer_inactivity_expiration_enabled: true
    peer_inactivity_expiration: 2592000
    jwt_groups_enabled: true
    jwt_groups_claim_name: "groups"
    dns_domain: "netbird.example.com"
    auto_update_always: true
    auto_update_version: "latest"
    peer_expose_enabled: true
    extra_peer_approval_enabled: false
    extra_network_traffic_logs_enabled: true
    state: present
```

### netbird_token

Manage NetBird personal access tokens.

```yaml
- name: Create access token
  community.ansible_netbird.netbird_token:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    user_id: "user-id-123"
    name: "automation-token"
    expires_in: 365
    state: present
  register: new_token

# The token secret is returned only on creation. Never print it with debug;
# capture it once and store it in a secret manager.
- name: Save the token (returned only on creation)
  ansible.builtin.copy:
    content: "{{ new_token.token.plain_token }}"
    dest: ./automation-token.secret
    mode: "0600"
  no_log: true
  when: new_token.token.plain_token is defined
```

### netbird_idp

Manage NetBird identity providers.

```yaml
# Create an OIDC identity provider
- name: Configure identity provider
  community.ansible_netbird.netbird_idp:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "corporate-sso"
    type: "oidc"
    issuer: "https://auth.example.com"
    client_id: "your-client-id"
    client_secret: "your-client-secret"
    state: present

# Create a Google identity provider
- name: Configure Google IDP
  community.ansible_netbird.netbird_idp:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    name: "google-workspace"
    type: "google"
    issuer: "https://accounts.google.com"
    client_id: "your-google-client-id"
    client_secret: "your-google-client-secret"
    state: present
```

### netbird_invite

Manage NetBird user invites.

```yaml
# Create a user invite
- name: Invite a new user
  community.ansible_netbird.netbird_invite:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    email: "newuser@example.com"
    name: "New User"
    role: "user"
    auto_groups:
      - "developers-group-id"
    expires_in: 604800  # 7 days
    state: present

# Regenerate an expired invite
- name: Regenerate invite link
  community.ansible_netbird.netbird_invite:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    email: "newuser@example.com"
    regenerate: true
    state: present

# Delete an invite
- name: Remove invite
  community.ansible_netbird.netbird_invite:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    invite_id: "invite-id-123"
    state: absent
```

### netbird_service_domain

Manage custom domains for NetBird reverse-proxy services.

```yaml
# Create a custom domain
- name: Add custom domain
  community.ansible_netbird.netbird_service_domain:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    domain: "app.example.com"
    target_cluster: "eu.proxy.netbird.io"
    state: present

# Create and trigger DNS validation
- name: Add and validate custom domain
  community.ansible_netbird.netbird_service_domain:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    domain: "app.example.com"
    target_cluster: "eu.proxy.netbird.io"
    validate: true
    state: present

# Delete a custom domain
- name: Remove custom domain
  community.ansible_netbird.netbird_service_domain:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    domain: "app.example.com"
    state: absent
```

### netbird_proxy_cluster

Remove NetBird self-hosted reverse-proxy clusters.  

> **Note:** Proxy clusters are registered automatically by the proxy software; only deletion is available through the API, so this module only supports C(state=absent).

```yaml
- name: "Delete existent cluster"
  community.ansible_netbird.netbird_proxy_cluster:
    address: "subdomain.proxy.example.com"
    state: absent
```

### netbird_an_settings

Manage account-wide agent-network (AI gateway) settings. An account that
has never been initialised is bootstrapped on first use; bootstrapping
requires `proxy_address` or `endpoint` (both are read-only afterwards).

```yaml
- name: Enable PII redaction and set log retention
  community.ansible_netbird.netbird_an_settings:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    redact_pii: true
    access_log_retention_days: 90
    state: present
```

### netbird_an_provider

Manage AI providers behind the agent network. The `api_key` is write-only:
the API seals it and never returns it, so it cannot participate in change
detection. Providing it on an existing provider therefore always sends an
update (rotating the key) and reports `changed` — omit `api_key` after
creation to keep runs idempotent.

```yaml
- name: Create an OpenAI provider
  community.ansible_netbird.netbird_an_provider:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "OpenAI Production"
    catalog_provider_id: openai_api
    upstream_url: "https://api.openai.com/v1"
    api_key: "{{ openai_api_key }}"
    models:
      - id: gpt-4o
        input_per_1k: 0.0025
        output_per_1k: 0.01
    enabled: true
    state: present
```

### netbird_an_policy

Manage agent-network access policies: which groups may reach which
providers, with optional guardrails and token/budget limits. Options take
API IDs; the `configure` role resolves plain names for you. Omitted
optional fields (including individual `limits` sub-limits) preserve the
current values instead of resetting them.

```yaml
- name: Create an agent-network policy
  community.ansible_netbird.netbird_an_policy:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "Default AI policy"
    description: "Allow developers to access OpenAI"
    enabled: true
    source_groups:
      - "developers-group-id"
    destination_provider_ids:
      - "openai-provider-id"
    guardrail_ids:
      - "pii-guardrail-id"
    limits:
      token_limit:
        enabled: true
        group_cap: 100000
        user_cap: 10000
        window_seconds: 3600
    state: present
```

### netbird_an_guardrail

Manage agent-network guardrails (model allowlists, prompt capture, PII
redaction). Omitted checks are preserved on update.

```yaml
- name: Create a guardrail with model allowlist and prompt capture
  community.ansible_netbird.netbird_an_guardrail:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "production-guardrail"
    checks:
      model_allowlist:
        enabled: true
        models:
          - "gpt-4"
          - "claude-3-opus"
      prompt_capture:
        enabled: true
        redact_pii: true
    state: present
```

### netbird_an_budget_rule

Manage agent-network budget rules targeting groups or users. Omitting a
sub-limit (or `target_groups`/`target_users`/`enabled`) on update preserves
the existing value.

```yaml
- name: Create a budget rule with token limits
  community.ansible_netbird.netbird_an_budget_rule:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "developer-budget"
    target_groups:
      - "developers-group-id"
    limits:
      token_limit:
        enabled: true
        group_cap: 100000
        user_cap: 10000
        window_seconds: 3600
    enabled: true
    state: present
```

### netbird_info

Gather information about NetBird resources.

```yaml
- name: Get all peers
  community.ansible_netbird.netbird_info:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    resource: peers
  register: peers

- name: Get all groups
  community.ansible_netbird.netbird_info:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    resource: groups
  register: groups

- name: Get current user
  community.ansible_netbird.netbird_info:
    api_url: "{{ netbird_api_url }}"
    api_token: "{{ netbird_api_token }}"
    resource: current_user
  register: me
```

Available resources: `accounts`, `users`, `peers`, `groups`, `setup_keys`, `policies`, `networks`, `routes`, `dns_nameservers`, `dns_zones`, `dns_settings`, `posture_checks`, `events`, `countries`, `current_user`, `identity_providers`, `invites`, `services`, `service_domains`, `proxy_clusters`, `an_settings`, `an_providers`, `an_catalog_providers`, `an_policies`, `an_guardrails`, `an_budget_rules`, `an_access_logs`, `an_access_log_sessions`, `an_usage_overview`, `an_consumption`

The `an_access_logs` and `an_access_log_sessions` resources are paginated (max 100 per page); the response envelope includes `total_records` and `total_pages`.

## Role Usage

The collection includes a role for declarative configuration:

```yaml
- hosts: localhost
  vars:
    netbird_api_url: "https://netbird.example.com"
    netbird_api_token: "{{ vault_netbird_token }}"
    
    netbird_groups:
      - name: "developers"
        state: present
      - name: "production"
        state: present
    
    netbird_setup_keys:
      - name: "server-key"
        key_type: "reusable"
        expires_in: 604800
        state: present
    
    netbird_policies:
      - name: "allow-all"
        enabled: true
        rules:
          - name: "all-traffic"
            sources: ["group-id-1"]
            destinations: ["group-id-2"]
            protocol: "all"
            action: "accept"
        state: present
    
    # Networks with routing (replaces deprecated routes)
    netbird_networks:
      - name: "internal-network"
        description: "Corporate internal network"
        routers:
          - peer: "gateway-peer-id"
            metric: 100
            masquerade: true
        resources:
          - address: "172.16.0.0/16"
            name: "internal-range"
            groups: ["developers-group-id"]
          - address: "*.internal.example.com"
            name: "internal-domains"
            groups: ["developers-group-id"]
        state: present

  roles:
    - community.ansible_netbird
```

See `defaults/main.yml` for all available role variables.

## Examples

The `examples/` directory contains complete playbook examples:

- `basic_setup.yml` - Basic groups, keys, and policies setup
- `full_infrastructure.yml` - Complete infrastructure configuration using the role
- `dynamic_policies.yml` - Create policies based on existing groups
- `inventory_from_netbird.yml` - Export peers as Ansible inventory
- `peer_management.yml` - Manage and audit peers

## Installing the NetBird Client

The `client` role installs the NetBird client from the official package repositories, following the upstream [`install.sh`](https://github.com/netbirdio/netbird/blob/main/release_files/install.sh), and can enroll each host with a setup key:

```bash
ansible-playbook -i inventory.ini community.ansible_netbird.install \
  -e netbird_setup_key="$NETBIRD_SETUP_KEY" \
  -e netbird_setup_management_url=https://netbird.example.org
```

See [docs/install.md](docs/install.md) for supported platforms and all variables.

## Config as Code (IaC Roles)

This collection includes roles and playbooks for managing your entire NetBird configuration as YAML files in Git — with preview/diff, strict mode, and automatic name-to-ID resolution.

### Quick Start (Safe Workflow)

The recommended workflow uses the `safe_apply_netbird` playbook, which automatically backs up the current state before making any changes:

```bash
# 1. Export current state to YAML files
ansible-playbook community.ansible_netbird.export_netbird_config \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token"

# 2. Preview changes (default — backup + read-only diff, no modifications)
ansible-playbook community.ansible_netbird.safe_apply_netbird \
  -e "config_dir=/path/to/your/config" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token"

# 3. Apply changes (backup + preview + apply)
ansible-playbook community.ansible_netbird.safe_apply_netbird \
  -e "config_dir=/path/to/your/config" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token" \
  -e "apply=true"

# 4. Apply with strict mode (also removes unmanaged resources)
ansible-playbook community.ansible_netbird.safe_apply_netbird \
  -e "config_dir=/path/to/your/config" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token" \
  -e "apply=true" -e "use_strict=true"

# 5. Rollback to a backup
ansible-playbook community.ansible_netbird.safe_apply_netbird \
  -e "config_dir=/path/to/backups/20260330T120000" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token" \
  -e "apply=true"
```

The `safe_apply_netbird` playbook always creates a timestamped backup in `backups/` before doing anything. You can also use the individual playbooks directly:

```bash
# Export only
ansible-playbook community.ansible_netbird.export_netbird_config \
  -e "netbird_api_url=..." -e "netbird_api_token=..."

# Configure only (preview by default, add -e commit=true to apply)
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=..." -e "netbird_api_url=..." -e "netbird_api_token=..."
```

### Using Roles Directly

For inventory-based workflows (e.g., AAP), use the roles directly in your own playbooks:

```yaml
- name: Configure NetBird
  hosts: netbird_control_nodes
  gather_facts: false
  roles:
    - role: community.ansible_netbird.configure
      run_once: true
      vars:
        config_dir: "{{ playbook_dir }}/../netbird_config/{{ netbird_env }}"
```

### Features

- **Preview mode** (default) — shows a read-only diff of what would change before applying
- **Strict mode** — enforces full IaC by removing resources not defined in YAML
- **Setup key management** — create/rotate enrollment keys with auto_groups name resolution; key values registered for downstream Vault storage
- **Name-based config** — use plain names ("developers") instead of API IDs; resolved automatically
- **Dependency ordering** — resources applied in correct order (posture checks → groups → settings → setup keys → DNS → networks → services → policies; agent-network guardrails and providers before the AN policies and budget rules that reference them)
- **Export utility** — captures current API state as clean, ready-to-use YAML config files
- **Roles** — use `community.ansible_netbird.configure` and `community.ansible_netbird.export` directly in your own playbooks for full control

### Config Directory Structure

```
my_netbird_config/
├── settings.yml                    # Account-wide settings
├── networks.yml                    # Networks with routers and resources
├── services.yml                    # Reverse-proxy services and custom domains (optional)
├── agent_network.yml               # AI gateway: settings, providers, guardrails, policies, budget rules (optional)
├── setup_keys.yml                  # Peer enrollment keys (optional)
├── access_control/
│   ├── groups.yml                  # Groups
│   ├── posture_checks.yml          # Posture checks
│   └── policies.yml               # Policies
└── dns/
    ├── nameservers.yml             # DNS nameserver groups
    ├── zones.yml                   # DNS zones with records
    └── settings.yml               # DNS settings
```

A starter `config_skeleton/` directory is included in the collection with empty defaults and commented examples.

See [docs/guide_netbird_config_as_code.md](docs/guide_netbird_config_as_code.md) for the full guide.

## API Reference

This collection implements the [NetBird REST API](https://docs.netbird.io/api). Refer to the official documentation for detailed information about:

- [Authentication](https://docs.netbird.io/api/guides/authentication)
- [Accounts](https://docs.netbird.io/api/resources/accounts)
- [Users](https://docs.netbird.io/api/resources/users)
- [Peers](https://docs.netbird.io/api/resources/peers)
- [Groups](https://docs.netbird.io/api/resources/groups)
- [Setup Keys](https://docs.netbird.io/api/resources/setup-keys)
- [Policies](https://docs.netbird.io/api/resources/policies)
- [Networks](https://docs.netbird.io/api/resources/networks)
- [DNS](https://docs.netbird.io/api/resources/dns)
- [Posture Checks](https://docs.netbird.io/api/resources/posture-checks)
- [Services](https://docs.netbird.io/api/resources/services)
- [Agent Network](https://docs.netbird.io/api/resources/agent-network)
- [Identity Providers](https://docs.netbird.io/api/resources/identity-providers)
- [Events](https://docs.netbird.io/api/resources/events)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. This
project follows the [Ansible Community Code of Conduct](CODE_OF_CONDUCT.md).

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This collection is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Support

- [NetBird Documentation](https://docs.netbird.io)
- [NetBird GitHub](https://github.com/netbirdio/netbird)
- [NetBird Community](https://netbird.io/community)

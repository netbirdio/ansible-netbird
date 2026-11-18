# NetBird Configuration as Code Guide

## Overview

Manage your NetBird logical configuration (groups, policies, networks, DNS, posture checks, setup keys, account settings) as YAML files stored in Git. Changes are reviewed via pull requests and applied via the `configure_netbird` playbook.

```
Edit YAML → PR → Review → Merge → Apply
```

## Prerequisites

Install the collection:

```bash
ansible-galaxy collection install community.ansible_netbird
```

## Quick Start

### 1. Export Current State

Capture your current NetBird configuration as clean YAML files:

```bash
ansible-playbook community.ansible_netbird.export_netbird_config \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token"
```

Output is written to `/tmp/netbird_config_export/` by default.

### 2. Set Up Your Config Directory

Copy the exported files to your project (or start from the skeleton):

```bash
# From export
cp -r /tmp/netbird_config_export/ my_netbird_config/

# Or from skeleton (empty defaults with commented examples)
cp -r ~/.ansible/collections/ansible_collections/community/ansible_netbird/config_skeleton/ my_netbird_config/
```

### 3. Preview Changes

The playbook runs in **preview mode by default** — read-only, no modifications:

```bash
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=$(pwd)/my_netbird_config" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token"
```

### 4. Apply Changes

```bash
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=$(pwd)/my_netbird_config" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token" \
  -e "commit=true"
```

## Config Directory Structure

```
my_netbird_config/
├── settings.yml                    → netbird_settings
├── networks.yml                    → netbird_networks
├── setup_keys.yml                  → netbird_setup_keys (optional)
├── services.yml                    → netbird_services, netbird_service_domains (optional)
├── agent_network.yml               → netbird_an_settings, netbird_an_providers,
│                                     netbird_an_guardrails, netbird_an_policies,
│                                     netbird_an_budget_rules (optional)
├── access_control/
│   ├── groups.yml                  → netbird_groups
│   ├── posture_checks.yml          → netbird_posture_checks
│   └── policies.yml               → netbird_policies
└── dns/
    ├── nameservers.yml             → netbird_dns_nameserver_groups
    ├── zones.yml                   → netbird_dns_zones
    └── settings.yml               → netbird_dns_disabled_management_groups
```

The directory layout mirrors the NetBird UI navigation:
- `settings.yml` — Account-wide settings (UI: Settings)
- `access_control/` — Groups, posture checks, policies (UI: Access Control)
- `dns/` — Nameservers, zones, DNS settings (UI: DNS)
- `networks.yml` — Networks with routers and resources (UI: Networks)
- `setup_keys.yml` — Peer enrollment keys (optional, UI: Setup Keys)
- `services.yml` — Reverse-proxy services and their custom domains (optional)
- `agent_network.yml` — Agent Network (AI gateway) settings, providers, guardrails, policies and budget rules (optional)

## Resource Dependencies

Resources are applied in dependency order (handled automatically):

1. **Posture checks** — no dependencies (referenced by policies)
2. **Groups** — no dependencies (referenced by everything else)
3. **Account settings** — depends on groups
4. **Setup keys** — depends on groups (for auto_groups)
5. **DNS** — depends on groups
6. **Networks** — depends on groups
7. **Service custom domains** — no dependencies (referenced by services)
8. **Services** — depends on groups, network resources and custom domains
9. **Policies** — depends on groups + posture checks
10. **Agent Network guardrails and providers** — no dependencies
11. **Agent Network settings** — no dependencies
12. **Agent Network policies** — depends on groups, providers and guardrails
13. **Agent Network budget rules** — depends on groups

In strict mode, unmanaged resources are removed after everything is applied:
policies, networks, DNS, setup keys, posture checks, services, service domains,
Agent Network policies, budget rules, providers and guardrails, and finally
groups.

## Adding/Modifying Resources

Edit the appropriate file in your config directory.

### Groups

```yaml
# access_control/groups.yml
netbird_groups:
  - name: "developers"
    state: present
  - name: "production-servers"
    state: present
  - name: "deprecated-group"
    state: absent          # Will be deleted
```

### Posture Checks

```yaml
# access_control/posture_checks.yml
netbird_posture_checks:
  - name: "minimum-version"
    description: "Require minimum NetBird version"
    checks:
      nb_version_check:
        min_version: "0.25.0"
    state: present
```

### Policies

```yaml
# access_control/policies.yml
netbird_policies:
  - name: "developers-ssh"
    description: "Allow developers SSH to production"
    enabled: true
    source_posture_checks:
      - minimum-version
    rules:
      - name: "ssh-access"
        description: "SSH access rule"
        enabled: true
        sources:
          - developers
        destinations:
          - production-servers
        bidirectional: false
        protocol: "tcp"
        ports: ["22"]
        action: "accept"
    state: present
```

### DNS Nameservers

```yaml
# dns/nameservers.yml
netbird_dns_nameserver_groups:
  - name: "corporate-dns"
    description: "Corporate DNS servers"
    nameservers:
      - ip: "10.0.0.53"
        ns_type: "udp"
        port: 53
    groups:
      - developers
    domains:
      - "corp.example.com"
    enabled: true
    primary: false
    state: present
```

### DNS Zones

```yaml
# dns/zones.yml
netbird_dns_zones:
  - name: "Office Zone"     # optional -- omitted, the name defaults to the domain
    domain: "office.example.com"
    enabled: true
    enable_search_domain: false
    distribution_groups:
      - developers
    records:
      - name: "server1"
        type: "A"
        content: "10.0.1.1"
        ttl: 300
    state: present
```

### Networks

```yaml
# networks.yml
netbird_networks:
  - name: "internal-network"
    description: "Corporate internal network"
    routers:
      - peer: "gateway"            # peer name, resolved to an ID at apply time
        metric: 100
        masquerade: true
        enabled: true
    resources:
      - address: "172.16.0.0/16"
        name: "internal-range"
        enabled: true
        groups:
          - developers
    state: present
```

### Setup Keys

```yaml
# setup_keys.yml
netbird_setup_keys:
  - name: "server-enrollment"
    key_type: "reusable"              # one-off or reusable
    expires_in: 604800                # 7 days in seconds; 0 = never expires
    auto_groups:
      - servers                       # resolved to ID automatically
    usage_limit: 0                    # 0 = unlimited (reusable only)
    ephemeral: false
    state: present
```

> **Important:** Setup key values are returned by the NetBird API **only at creation time**. On subsequent runs, the key exists and `changed=false` is reported — the key value is not retrievable. Store key values securely when they are first created.

The role registers results as `netbird_setup_key_results`, making key values available to `post_tasks:` in wrapper playbooks for downstream storage (e.g., HashiCorp Vault, AWS Secrets Manager).

### Setup Key Rotation

The NetBird API does not support regenerating a setup key — the Update endpoint can only change `revoked` and `auto_groups`. Rotation requires a two-phase approach:

**Phase 1 — Create new key alongside old (both active):**

```yaml
# setup_keys.yml
netbird_setup_keys:
  - name: "server-enrollment"              # existing key, still active
    key_type: "reusable"
    auto_groups: [servers]
  - name: "server-enrollment-rotated"      # new key
    key_type: "reusable"
    auto_groups: [servers]
```

Apply with `commit=true`. The new key is created and its value is displayed (or stored via `post_tasks:`). Deploy the new key to clients while the old key still works.

**Phase 2 — Revoke old key after clients migrated:**

```yaml
# setup_keys.yml
netbird_setup_keys:
  - name: "server-enrollment"
    revoked: true                          # revoked, no longer usable
  - name: "server-enrollment-rotated"
    key_type: "reusable"
    auto_groups: [servers]
```

The old key is revoked. You can later change it to `state: absent` to delete it entirely.

### Services

Reverse-proxy services publish an internal application on a domain. Services
are matched by `domain`.

```yaml
# services.yml
netbird_services:
  - domain: "myapp.netbird.example.com"
    private: false
    enabled: true
    auth:
      bearer_auth:
        enabled: true
        distribution_groups:
          - all-users                 # resolved to ID automatically
    targets:
      - host: "10.0.0.30"
        port: 8080
        protocol: http
        target_id: "host-resource-id" # network resource ID, not a name
        target_type: host             # subnet, host, domain, peer, cluster
        enabled: true
        direct_upstream: false
        access_action: inherit        # the service's authentication applies
      - host: "10.0.0.30"
        port: 8080
        protocol: http
        target_id: "host-resource-id"
        target_type: host
        enabled: true
        direct_upstream: false
        path: /public/
        access_action: bypass         # no authentication under /public/
      - host: "10.0.0.30"
        port: 8080
        protocol: http
        target_id: "host-resource-id"
        target_type: host
        enabled: true
        direct_upstream: false
        path: /admin
        access_action: block          # /admin is never served
    state: present

netbird_service_domains:
  - domain: "app.example.com"
    target_cluster: "eu.proxy.netbird.io"
    validate: true
    state: present
```

- `access_groups` and `bearer_auth.distribution_groups` take group names.
  `target_id` takes the network resource ID; copy it from an export.
- `direct_upstream` defaults to `true` (dial the backend from the proxy's host
  network). Set it to `false` for targets the proxy reaches through the
  tunnel; some proxy clusters, NetBird Cloud's among them, refuse `true` on
  public services. The export always writes it.
- `access_action` (`inherit`, `bypass` or `block`) sets authentication per
  path on HTTP services. It needs NetBird management v0.81.0 or later, with
  every reverse proxy in the service's cluster upgraded. A target without
  `access_action` keeps the action it already has, including one set in the
  dashboard; a target that states it, `inherit` included, has it enforced.
- The export writes `access_action` for every target the server reports it
  on. Applying an older export therefore reverts actions changed in the
  dashboard since it was taken.
- Password and PIN secrets are never returned by the API, so the export leaves
  `password_auth`/`pin_auth` out with a comment. Re-add them before applying;
  leaving them out keeps the service's existing settings.

> **Upgrading from 1.4.x:** re-export after upgrading. Exports from earlier
> versions leave out `direct_upstream` when it is false, so applying them
> switches those targets to direct dialing (the preview now shows this), and
> they carry no `access_action`.

### Agent Network

The Agent Network (AI gateway) proxies LLM API calls through NetBird with
access control, limits and guardrails. Providers, guardrails, policies and
budget rules are matched by `name`.

```yaml
# agent_network.yml
netbird_an_settings:
  enable_log_collection: true
  redact_pii: true
  access_log_retention_days: 30

netbird_an_providers:
  - name: "openai-production"
    catalog_provider_id: "openai_api"
    upstream_url: "https://api.openai.com/v1"
    api_key: "{{ vault_openai_key }}"
    enabled: true
    state: present

netbird_an_guardrails:
  - name: "restrict-models"
    checks:
      model_allowlist:
        enabled: true
        models:
          - "gpt-4o"
    state: present

netbird_an_policies:
  - name: "dev-team-ai-access"
    enabled: true
    source_groups:
      - developers                    # resolved to ID automatically
    destination_provider_ids:
      - openai-production             # provider name, resolved automatically
    guardrail_ids:
      - restrict-models               # guardrail name, resolved automatically
    limits:
      budget_limit:
        enabled: true
        user_cap_usd: 50.00
        window_seconds: 2592000       # 30 days
    state: present

netbird_an_budget_rules:
  - name: "monthly-budget"
    enabled: true
    target_groups:
      - developers                    # resolved to ID automatically
    target_users: []                  # user IDs, not names
    limits:
      budget_limit:
        enabled: true
        group_cap_usd: 1000.00
        window_seconds: 2592000
    state: present
```

- Provider API keys are sealed: the API never returns them, so the export
  writes `api_key: ""`. An existing provider keeps its key when `api_key` is
  empty; creating a provider requires one. A non-empty `api_key` is sent on
  every apply (the module cannot compare it), which also rotates it.
- Updates carry forward any field you leave out. To turn off a limit or a
  guardrail check, keep it and set `enabled: false`.
- `netbird_an_settings` is applied as given and is never removed by strict
  mode.

## Name-Based ID Resolution

Config files use **plain names** for groups and posture checks — no IDs, no Jinja2 syntax. The playbook resolves names to API IDs automatically at runtime.

How it works:
1. Groups and posture checks are created first (dependency order)
2. The playbook fetches all groups/posture checks from the API and builds lookup maps
3. When applying DNS, networks, services, policies and Agent Network policies and budget rules, names are resolved to IDs transparently (Agent Network policies also resolve provider and guardrail names)

```yaml
# Just use plain names — the playbook handles the rest
sources:
  - developers
distribution_groups:
  - production-servers
source_posture_checks:
  - minimum-version
```

> **Note:** Router `peer` values in networks remain as peer IDs because peers are dynamic (they register via setup keys). The export playbook annotates peer IDs with hostnames in comments for reference.

**Not managed by IaC (intentional):**
- **Peers** — dynamic, register via setup keys
- **Users** — managed via IdP/LDAP sync

## Previewing Changes (Dry-Run Diff)

The playbook runs in **preview mode by default** — read-only, no modifications. To apply changes, pass `-e "commit=true"`.

Example output:

```
══════════════════════════════════════════════════════════════
 NETBIRD CONFIGURATION PREVIEW — MY_NETBIRD_CONFIG
══════════════════════════════════════════════════════════════

── Groups ────────────────────────────────────────────────────
  + ADD:                "monitoring-servers"
  - REMOVE:             "deprecated-group"
  ~ EXISTS (re-apply):  "developers"

── Policies ──────────────────────────────────────────────────
  ~ EXISTS (re-apply):  "developers-ssh"

══════════════════════════════════════════════════════════════
 SUMMARY
──────────────────────────────────────────────────────────────
 + Add:     1 resource(s)
 ~ Exists:  2 resource(s)
 - Remove:  1 resource(s)
══════════════════════════════════════════════════════════════
```

## Strict Mode (Full IaC Enforcement)

By default, the playbook only manages resources defined in YAML. Resources created manually in the webUI are left untouched. With **strict mode**, any resource in the API that is NOT defined in your YAML config will be deleted — making the YAML files the single source of truth.

```bash
# Preview what strict mode would do
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=$(pwd)/my_netbird_config" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token" \
  -e "strict=true"

# Apply with strict enforcement
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=$(pwd)/my_netbird_config" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token" \
  -e "commit=true" \
  -e "strict=true"
```

**Protected resources** (never deleted by strict mode):
- "All" group (auto-managed by NetBird)
- JWT-issued groups (synced from IdP)
- Peers (dynamic, register via setup keys)
- Users (managed via IdP/LDAP)

The preview always shows orphaned resources so you can see what strict mode would remove, even without `-e "strict=true"`.

## Using with Inventory (target_hosts)

By default, the playbooks run on `localhost`. If you use an Ansible inventory (e.g., with AAP or for multi-environment setups), set `target_hosts` to your inventory group:

```bash
ansible-playbook community.ansible_netbird.configure_netbird \
  -i inventory \
  -e "target_hosts=netbird_control_nodes" \
  -l netbird_control_nodes_preprod \
  -e "config_dir=/path/to/netbird_config/preprod" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token"
```

Or create your own playbooks that use the roles directly — this is the recommended approach for inventory-based workflows:

```yaml
# configure_netbird.yml (using the role directly)
- name: Configure NetBird
  hosts: netbird_control_nodes
  gather_facts: false
  roles:
    - role: community.ansible_netbird.configure
      run_once: true
      vars:
        config_dir: "{{ playbook_dir }}/../netbird_config/{{ netbird_env }}"
```

Then run with just a limit: `ansible-playbook configure_netbird.yml -i inventory -l preprod`

Using roles directly gives you full control over `hosts`, `gather_facts`, and variable resolution — and avoids `import_playbook` path resolution issues in AAP.

## Remote / Public API Endpoint

If your NetBird management plane runs on OpenShift or a cloud platform without SSH access, you can run the playbooks against the public API endpoint directly from `localhost`:

```yaml
# configure_netbird.yml (remote API)
- name: Configure NetBird via Public API
  hosts: localhost
  gather_facts: false
  roles:
    - role: community.ansible_netbird.configure
      run_once: true
      vars:
        netbird_api_url: "https://netbird.example.com"
        netbird_api_token: "{{ vault_netbird_token }}"
        config_dir: "{{ playbook_dir }}/../netbird_config/{{ netbird_env }}"
```

Or use the collection playbook directly:

```bash
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=$(pwd)/netbird_config/prod" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token" \
  -e "commit=true"
```

Both patterns work identically — the only difference is whether Ansible SSHes to a control node (and queries `localhost:33073`) or runs locally against a remote HTTPS endpoint.

## Multi-Environment Setup

For managing multiple environments (e.g., production and staging), create separate config directories:

```
netbird_config/
├── prod/
│   ├── settings.yml
│   ├── setup_keys.yml
│   ├── access_control/
│   ├── dns/
│   └── networks.yml
└── staging/
    ├── settings.yml
    ├── setup_keys.yml
    ├── access_control/
    ├── dns/
    └── networks.yml
```

Then target each environment with a different `config_dir`:

```bash
# Preview staging
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=$(pwd)/netbird_config/staging" \
  -e "netbird_api_url=https://staging-netbird.example.com" \
  -e "netbird_api_token=staging-token"

# Apply production
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=$(pwd)/netbird_config/prod" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=prod-token" \
  -e "commit=true"
```

## Disaster Recovery

To rebuild NetBird configuration from scratch using your YAML files:

```bash
ansible-playbook community.ansible_netbird.configure_netbird \
  -e "config_dir=$(pwd)/my_netbird_config" \
  -e "netbird_api_url=https://netbird.example.com" \
  -e "netbird_api_token=your-token" \
  -e "commit=true"
```

All resources defined in your config will be recreated. Add `-e "strict=true"` to also remove resources not in the config files.

## Idempotency

All operations are idempotent:
- Running the playbook twice produces the same result
- Resources that already match the desired state are not modified
- `changed=false` is reported when no changes are needed

# NetBird Configuration as Code Guide

## Overview

Manage your NetBird logical configuration (groups, policies, networks, DNS, posture checks, account settings) as YAML files stored in Git. Changes are reviewed via pull requests and applied via the `configure_netbird` playbook.

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

## Resource Dependencies

Resources are applied in dependency order (handled automatically):

1. **Account settings** — no dependencies
2. **Posture checks** — no dependencies (referenced by policies)
3. **Groups** — no dependencies (referenced by everything else)
4. **DNS** — depends on groups
5. **Networks** — depends on groups
6. **Policies** — depends on groups + posture checks

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
  - name: "Office Zone"
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
      - peer: "gateway-peer-id"    # Peer IDs stay as-is (peers are dynamic)
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

## Name-Based ID Resolution

Config files use **plain names** for groups and posture checks — no IDs, no Jinja2 syntax. The playbook resolves names to API IDs automatically at runtime.

How it works:
1. Groups and posture checks are created first (dependency order)
2. The playbook fetches all groups/posture checks from the API and builds lookup maps
3. When applying DNS, networks, and policies, names are resolved to IDs transparently

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
- **Setup keys** — key values are one-time secrets returned only at creation. The export playbook captures setup key metadata as a read-only reference.
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

## Multi-Environment Setup

For managing multiple environments (e.g., production and staging), create separate config directories:

```
netbird_config/
├── prod/
│   ├── settings.yml
│   ├── access_control/
│   ├── dns/
│   └── networks.yml
└── staging/
    ├── settings.yml
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

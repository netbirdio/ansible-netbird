# Examples

Runnable example playbooks for the `community.ansible_netbird` collection. Each
one runs on `localhost` against the NetBird REST API. Provide credentials via
environment variables (or the `api_url` / `api_token` module parameters) before
running:

```bash
export NETBIRD_API_URL="https://netbird.example.com"
export NETBIRD_API_TOKEN="nbp_EXAMPLEtokenvalue000000000000000000"

ansible-playbook basic_setup.yml
```

| Playbook | What it does |
|----------|--------------|
| `basic_setup.yml` | Minimal end-to-end setup: a group, a setup key, a policy, and a routed network. |
| `dynamic_policies.yml` | Generate access policies dynamically from a list of groups. |
| `full_infrastructure.yml` | Complete tenant configuration (account settings, groups, service users, setup keys, DNS, posture checks, networks) via the `configure` role. |
| `inventory_from_netbird.yml` | Build a dynamic Ansible inventory from NetBird peers. |
| `peer_management.yml` | Configure and audit peers in bulk. |

## Next steps

- Getting started: [Configure NetBird with Ansible](https://docs.netbird.io/selfhosted/iac/ansible)
- Managing a whole tenant declaratively: [Configuration as Code guide](../docs/guide_netbird_config_as_code.md)

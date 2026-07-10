# NetBird Self-Hosted Ansible Guide

This document describes how to use `getting_started.yml`, what each supported deployment mode does, and which variables are intended for operators to change. It intentionally omits low-level internal constants such as container image
names, fixed internal Traefik IPs, and generated secret values unless changing them is a normal deployment concern.

## Scope

`getting_started.yml` is an Ansible implementation of the NetBird self-hosted getting-started flow. It deploys the current combined NetBird server layout:
- `netbird-dashboard`
- `netbird-server`
- optional built-in Traefik
- optional NetBird reverse proxy and CrowdSec, only with built-in Traefik
- Some configuration options for automated deployment with other reverse proxies.

The playbook can also generate or install reverse-proxy configuration for a few external proxy modes. Some external modes are deliberately manual because they represent operator-owned infrastructure.

## Target Host Requirements

The target host must have:

- Linux with a public IPv4 address
- Docker Engine installed and running
- Docker Compose available as `docker compose` or `docker-compose`
- `jq`
- `openssl`
- an Ansible SSH user that can run `docker info`

\
For public TLS deployments, DNS for `netbird_domain` must point to the target host before the playbook performs public endpoint checks or before external proxies request certificates.

Required public firewall ports depend on mode, but most deployments need:

- `80/tcp` for HTTP challenge and redirect
- `443/tcp` for HTTPS
- `3478/udp` for NetBird STUN

The playbook does not install Docker, `jq`, or `openssl`. Missing prerequisites
fail early with explicit messages.

## Inventory

Example inventory:
```ini
[netbird]
203.0.113.10 ansible_user=root
```

Run with:
```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=builtin_traefik \
  -e traefik_acme_email=admin@example.org
```

## Required Variables

### `netbird_domain`

The public domain for the NetBird deployment.

```yaml
netbird_domain: netbird.example.org
```

Rules:

- Use a real FQDN for TLS deployments.
- Do not include `http://` or `https://`.
- Do not use the placeholder `netbird.example.com`.
- Use `use-ip` only for a non-TLS IP-based test deployment.

Example IP-only test:

```yaml
netbird_domain: use-ip
reverse_proxy_type: manual
```

When `netbird_domain=use-ip`, the playbook uses:

- `http`
- port `80`
- the host's detected primary IPv4 address

### `reverse_proxy_type`

Controls how public HTTPS traffic reaches NetBird.

```yaml
reverse_proxy_type: builtin_traefik
```

Allowed values:

- `builtin_traefik`
- `external_traefik`
- `nginx`
- `npm`
- `caddy`
- `manual`

## Common Variables

### `netbird_project_dir`

Where generated NetBird files are written.

```yaml
netbird_project_dir: "{{ ansible_user_dir }}/netbird"
```

Default for root-based VPS testing is usually `/root/netbird`.

Generated files include:

- `docker-compose.yml`
- `dashboard.env`
- `config.yaml`
- reverse-proxy snippets for selected modes
- generated secret files

### `start_netbird_services`

Controls whether Docker Compose services are started.

```yaml
start_netbird_services: true
```

Set to `false` if you only want generated files.

### `allow_existing_config`

Controls whether the playbook may operate on an existing generated NetBird
deployment directory.

```yaml
allow_existing_config: false
```

This variable is intentionally not declared in the default `vars` block. When it
is absent or `false`, the playbook refuses to reinitialize a directory that
already contains `config.yaml`.

Set it only for an intentional in-place rerun:

```bash
ansible-playbook ... -e allow_existing_config=true
```

### `bind_localhost_only`

Controls host-port exposure for external proxy modes.

```yaml
bind_localhost_only: true
```

When `true`, exposed NetBird HTTP ports bind to `127.0.0.1`.

When `false`, exposed ports bind to `0.0.0.0`.

Applies to:

- `nginx`
- `npm`
- `caddy`
- `manual`

Built-in Traefik and external Traefik use Docker labels/networks instead of
these exposed HTTP ports.

### `dashboard_host_port`

Host port for the dashboard container when using exposed-port modes.

```yaml
dashboard_host_port: 8080
```

### `management_host_port`

Host port for the combined NetBird server HTTP backend when using exposed-port
modes.

```yaml
management_host_port: 8081
```

### `netbird_stun_port`

Public UDP port for NetBird STUN.

```yaml
netbird_stun_port: 3478
```

This must be reachable directly over UDP. HTTP reverse proxies cannot proxy
STUN.

### `external_proxy_network`

Optional Docker network used to attach NetBird containers to an external reverse
proxy container.

```yaml
external_proxy_network: ""
```

Applies to:

- `nginx`
- `npm`
- `caddy`

If set, NetBird services join both the default NetBird network and the named
external network. The generated snippets then target container names such as
`netbird-server:80` and `netbird-dashboard:80`.

If unset, generated snippets target host ports such as `127.0.0.1:8081`.

## Existing Config Protection

The playbook refuses to overwrite an existing generated NetBird config by
default:

```text
/root/netbird/config.yaml already exists. This playbook will not reinitialize secrets by default.
```

To intentionally manage an existing deployment in place:

```bash
ansible-playbook ... -e allow_existing_config=true
```

Use this carefully. It preserves existing secret files when present, but it can
rewrite generated Compose and proxy configuration.

## Built-In Traefik Mode

Built-in Traefik is the default and most automated mode.

```yaml
reverse_proxy_type: builtin_traefik
traefik_acme_email: admin@example.org
```

It creates a Traefik container inside the NetBird Compose project. Traefik:

- listens on `80/tcp` and `443/tcp`
- requests certificates automatically
- routes dashboard, API, OAuth2, WebSocket, and gRPC traffic

### Required Built-In Traefik Variable

#### `traefik_acme_email`

Required when `reverse_proxy_type=builtin_traefik`.

```yaml
traefik_acme_email: admin@example.org
```

### Built-In Traefik NetBird Proxy Options

#### `builtin_traefik_enable_proxy`

Enables the NetBird reverse proxy service.

```yaml
builtin_traefik_enable_proxy: true
```

This option applies only to `builtin_traefik`.

#### `builtin_traefik_enable_crowdsec`

Enables CrowdSec alongside the NetBird reverse proxy.

```yaml
builtin_traefik_enable_crowdsec: true
```

This option applies only to `builtin_traefik`.

Validation rule:

- `builtin_traefik_enable_crowdsec=true` requires
  `builtin_traefik_enable_proxy=true`.

### Built-In Traefik Examples

Default recommended path:

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=builtin_traefik \
  -e traefik_acme_email=admin@example.org
```

Disable NetBird proxy and CrowdSec:

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=builtin_traefik \
  -e traefik_acme_email=admin@example.org \
  -e builtin_traefik_enable_proxy=false \
  -e builtin_traefik_enable_crowdsec=false
```

## External Traefik Mode

External Traefik mode generates Traefik labels on the NetBird containers. By default, it assumes Traefik already exists.

```yaml
reverse_proxy_type: external_traefik
traefik_external_network: traefik
traefik_entrypoint: websecure
traefik_certresolver: letsencrypt
```

Required external Traefik expectations:

- Traefik is running.
- Traefik has Docker provider enabled.
- Traefik is attached to the Docker network used by NetBird.
- Traefik has an HTTPS entrypoint.
- Traefik has a working certificate resolver.

### `traefik_external_network`

Docker network Traefik uses for service discovery.

```yaml
traefik_external_network: traefik
```

Required when `external_traefik_install_config=true`.

If omitted and `external_traefik_install_config=false`, NetBird uses its own
`netbird` network, which usually is not what an existing external Traefik
container needs.

### `traefik_entrypoint`

HTTPS entrypoint name in the external Traefik instance.

```yaml
traefik_entrypoint: websecure
```

### `traefik_certresolver`

Certificate resolver label to put on NetBird routers.

```yaml
traefik_certresolver: letsencrypt
```

If empty and `external_traefik_install_config=true`, the playbook uses
`external_traefik_certresolver`.

### Optional External Traefik Runtime Install

The playbook can also install a small standalone Traefik Compose runtime.

```yaml
external_traefik_install_config: true
external_traefik_project_dir: /opt/traefik
external_traefik_acme_email: admin@example.org
external_traefik_certresolver: letsencrypt
external_traefik_start: true
external_traefik_enable_dashboard: false
```

When enabled, the playbook:

- creates `traefik_external_network`
- writes `external_traefik_project_dir/docker-compose.yml`
- starts Traefik before NetBird when `external_traefik_start=true`
- attaches NetBird containers to the Traefik network
- validates the public endpoint through Traefik

#### `external_traefik_trusted_proxy_cidr`

Optional CIDR to add to NetBird's trusted HTTP proxy list.

```yaml
external_traefik_trusted_proxy_cidr: ""
```

Leave blank unless you know the Traefik source network CIDR that NetBird should
trust for forwarded headers.

### External Traefik Example

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=external_traefik \
  -e traefik_external_network=traefik \
  -e external_traefik_install_config=true \
  -e external_traefik_acme_email=admin@example.org
```

## Nginx Mode

Nginx mode generates `nginx-netbird.conf`.

By default, applying the config is manual:

```yaml
reverse_proxy_type: nginx
nginx_install_config: false
```

With no install option, the playbook:

- writes `/root/netbird/nginx-netbird.conf` or equivalent under
  `netbird_project_dir`
- pauses for manual proxy setup in interactive runs
- starts NetBird
- validates the direct backend endpoint, not the public proxy endpoint

### Host Nginx Install

The playbook supports host-installed Nginx.

```yaml
nginx_install_config: true
nginx_ssl_certificate: /etc/letsencrypt/live/netbird.example.org/fullchain.pem
nginx_ssl_certificate_key: /etc/letsencrypt/live/netbird.example.org/privkey.pem
nginx_config_path: /etc/nginx/sites-available/netbird
nginx_enabled_config_path: /etc/nginx/sites-enabled/netbird
nginx_disable_default_site: false
nginx_reload: true
```

When enabled, the playbook:

- installs the generated config to `nginx_config_path`
- symlinks it to `nginx_enabled_config_path`
- optionally removes `/etc/nginx/sites-enabled/default`
- runs `nginx -t`
- reloads Nginx when `nginx_reload=true`

### Certificate Handling

Nginx mode does not request certificates. You must provide valid certificate
paths before `nginx_install_config=true` can pass validation.

### Unsupported: Nginx Docker Proxy Runtime

Nginx running as a separate Docker reverse-proxy container is intentionally not
automated by this playbook.

You can still use `external_proxy_network` to attach NetBird containers to a
network used by your own Nginx container, but you must manage:

- Nginx container lifecycle
- mounted configs
- mounted certificates
- reloads
- public health checks

## Nginx Proxy Manager Mode

NPM mode can be used manually or with optional runtime/API automation.

```yaml
reverse_proxy_type: npm
```

The playbook always generates:

```text
npm-advanced-config.txt
```

This contains the Advanced tab config required for WebSocket, gRPC, API, and
OAuth2 routing.

### NPM Runtime Install

```yaml
npm_install_config: true
npm_project_dir: /opt/npm
npm_image: jc21/nginx-proxy-manager:latest
npm_network: npm
npm_http_port: 80
npm_https_port: 443
npm_admin_port: 81
npm_start: true
external_proxy_network: ""
```

When enabled, the playbook:

- creates `npm_network`
- writes `npm_project_dir/docker-compose.yml`
- starts NPM when `npm_start=true`
- attaches NetBird containers to `npm_network` if `external_proxy_network` is
  blank

### NPM Initial Admin

If both values are set, the generated NPM Compose file includes NPM's initial
admin bootstrap environment variables:

```yaml
npm_admin_identity: admin@example.org
npm_admin_secret: change-this-password
```

These create the initial NPM admin only when the NPM data volume has no active
users. If NPM already has users, those environment variables do not reset the
existing password.

### NPM Proxy Host API Automation

```yaml
npm_configure_proxy_host: true
npm_admin_identity: admin@example.org
npm_admin_secret: change-this-password
npm_api_url: ""
npm_proxy_host_ssl: true
npm_ssl_forced: true
npm_http2_support: true
npm_hsts_enabled: false
npm_hsts_subdomains: false
npm_block_exploits: true
npm_allow_websocket_upgrade: true
npm_existing_certificate_id: 0
```

When `npm_configure_proxy_host=true`, the playbook:

- waits for the NPM API
- logs in with `npm_admin_identity` and `npm_admin_secret`
- reads `npm-advanced-config.txt`
- reuses an existing certificate for the NetBird domain when present
- uses `npm_existing_certificate_id` when nonzero
- otherwise requests a Let's Encrypt HTTP-01 certificate when
  `npm_proxy_host_ssl=true`
- creates or updates the NPM Proxy Host
- enables HTTP/2 by default
- performs a public endpoint health check

`npm_api_url` defaults to:

```text
http://127.0.0.1:<npm_admin_port>/api
```

Set it only when the API is somewhere else.

### NPM Manual Setup

If `npm_configure_proxy_host=false`, configure NPM manually:

1. Open `http://<server-ip>:81`.
2. Create a Proxy Host for `netbird_domain`.
3. Forward to:
   - `netbird-dashboard:80` when NetBird is attached to the NPM Docker network
   - `127.0.0.1:8080` when proxying host ports
4. Enable HTTP/2 support in the SSL tab.
5. Paste `npm-advanced-config.txt` into the Advanced tab.

## Caddy Mode

Caddy mode generates `caddyfile-netbird.txt`.

```yaml
reverse_proxy_type: caddy
caddy_install_config: false
```

By default, applying the Caddyfile is manual.

### Host Caddy Install

```yaml
caddy_install_config: true
caddy_config_path: /etc/caddy/Caddyfile
caddy_reload: true
caddy_acme_email: admin@example.org
caddy_acme_ca: ""
```

When enabled, the playbook:

- installs the generated Caddyfile to `caddy_config_path`
- runs `caddy fmt --overwrite`
- runs `caddy validate`
- reloads Caddy
- starts NetBird
- reloads Caddy again after NetBird starts
- performs a public endpoint health check

### Caddy ACME Options

`caddy_acme_email` sets the ACME account email in the Caddyfile global options
block.

```yaml
caddy_acme_email: admin@example.org
```

`caddy_acme_ca` overrides the ACME CA.

```yaml
caddy_acme_ca: https://acme-staging-v02.api.letsencrypt.org/directory
```

Use staging only for testing. Browsers do not trust staging certificates.

Production default behavior with no `caddy_acme_ca` lets Caddy use its normal
issuer sequence. If Let's Encrypt is rate-limited, Caddy may fall back to
another issuer such as ZeroSSL when an email is configured.

## Manual Mode

Manual mode is intentionally minimal.

```yaml
reverse_proxy_type: manual
```

The playbook:

- exposes dashboard and management backend ports
- generates NetBird files
- starts NetBird
- checks the direct backend endpoint
- does not install or configure a reverse proxy
- does not perform a public endpoint check

This mode is for operator-owned proxy setups. Keep custom proxy automation
outside the playbook unless it belongs in a specific supported proxy mode.

Typical manual proxy targets:

- Dashboard: `127.0.0.1:8080`
- API/OAuth2/WebSocket/gRPC backend: `127.0.0.1:8081`

Use `bind_localhost_only=false` if your external proxy cannot reach
`127.0.0.1` on the NetBird host.

## NetBird User Creation

By default the playbook runs as the Ansible SSH user and does not create a new
Linux user.

```yaml
create_netbird_user: false
netbird_user: netbird
```

When `create_netbird_user=true`, the playbook:

- creates `netbird_user`
- adds it to the `docker` group
- verifies group membership
- verifies that user can run Docker

This requires become/root privileges and a Docker socket owned by the standard
`docker` group.

Example:

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=builtin_traefik \
  -e traefik_acme_email=admin@example.org \
  -e create_netbird_user=true \
  --ask-become-pass
```

## Generated Files

Generated files live under `netbird_project_dir`.

Common files:

- `docker-compose.yml`
- `dashboard.env`
- `config.yaml`
- `relay_auth_secret`
- `datastore_encryption_key`

Mode-specific files:

- `traefik-dynamic.yaml` for built-in Traefik NetBird proxy
- `proxy.env` for NetBird reverse proxy
- `nginx-netbird.conf` for Nginx
- `npm-advanced-config.txt` for Nginx Proxy Manager
- `caddyfile-netbird.txt` for Caddy

## Health Checks

The playbook uses two kinds of health checks.

### Public Endpoint Check

Uses:

```text
https://<netbird_domain>/oauth2/.well-known/openid-configuration
```

Runs for:

- `builtin_traefik`
- `external_traefik`
- `npm` when `npm_configure_proxy_host=true`
- `caddy` when `caddy_install_config=true`

### Direct Endpoint Check

Uses:

```text
http://127.0.0.1:<management_host_port>/oauth2/.well-known/openid-configuration
```

Runs for exposed-port modes:

- `nginx`
- `npm`
- `caddy`
- `manual`

The direct check proves NetBird is running, not that the public reverse proxy is
correct.

## Common Failure Modes

### Docker socket missing

Message:

```text
Docker socket /var/run/docker.sock was not found. Install and start Docker first.
```

Fix:

- install Docker
- start Docker
- verify `docker info`

### Docker permission failure

If the SSH user cannot access Docker, the playbook gives Docker group guidance
when the socket is owned by the `docker` group.

Fix:

```bash
sudo usermod -aG docker <user>
```

Then log out and back in.

### Existing config

Message:

```text
config.yaml already exists
```

Fix:

- delete the old deployment directory for a fresh deployment, or
- use `allow_existing_config=true` for an intentional in-place rerun

### DNS not updated

Symptoms:

- ACME validation fails
- public endpoint check times out
- browser reaches an old server

Check:

```bash
dig +short netbird.example.org A
```

### Firewall blocks public access

Symptoms:

- public endpoint times out
- ACME HTTP/TLS challenge fails

Check that inbound firewall allows:

- `80/tcp`
- `443/tcp`
- `3478/udp`

### Let's Encrypt rate limits

Symptoms:

- Caddy, Traefik, NPM, or certbot logs show HTTP 429 rate limit errors
- browser certificate remains invalid or stale

Options:

- wait until the rate limit clears
- test with Let's Encrypt staging where supported
- use an existing certificate where supported
- use a different test domain or subdomain

For Caddy testing:

```yaml
caddy_acme_ca: https://acme-staging-v02.api.letsencrypt.org/directory
```

Do not leave staging enabled for real browser testing; staging certs are
untrusted.

### Browser HSTS blocks bypass

If a domain previously served HSTS, browsers will refuse certificate bypasses.
Fix the server certificate rather than trying to bypass the warning.

## Example Commands

### Built-in Traefik

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=builtin_traefik \
  -e traefik_acme_email=admin@example.org
```

### External Traefik with Playbook-Installed Runtime

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=external_traefik \
  -e traefik_external_network=traefik \
  -e external_traefik_install_config=true \
  -e external_traefik_acme_email=admin@example.org
```

### Host Nginx

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=nginx \
  -e nginx_install_config=true \
  -e nginx_ssl_certificate=/etc/letsencrypt/live/netbird.example.org/fullchain.pem \
  -e nginx_ssl_certificate_key=/etc/letsencrypt/live/netbird.example.org/privkey.pem \
  -e nginx_disable_default_site=true
```

### Nginx Proxy Manager Fully Automated

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=npm \
  -e npm_install_config=true \
  -e npm_configure_proxy_host=true \
  -e npm_admin_identity=admin@example.org \
  -e npm_admin_secret='change-this-password'
```

### Caddy Host Install

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=caddy \
  -e caddy_install_config=true \
  -e caddy_acme_email=admin@example.org
```

### Manual Mode

```bash
ansible-playbook -i inventory.ini getting_started.yml \
  -e netbird_domain=netbird.example.org \
  -e reverse_proxy_type=manual \
  -e bind_localhost_only=false
```

Then configure your reverse proxy to route:

- `/relay*`, `/ws-proxy/*`, `/api/*`, `/oauth2/*` to `127.0.0.1:8081`
- gRPC paths to `h2c://127.0.0.1:8081`
- everything else to `127.0.0.1:8080`

## Security Notes

- Treat generated secret files as sensitive.
- Do not commit real `npm_admin_secret` values.
- Prefer inventory/group vars or Ansible Vault for credentials.
- `npm_admin_secret` may bootstrap the initial NPM admin user on a fresh NPM
  volume.
- Opening `bind_localhost_only=false` exposes backend ports to the network; use
  firewall rules or keep it `true` when the reverse proxy is on the same host.
- HSTS makes certificate mistakes visible and hard to bypass in browsers.

## What Is Intentionally Not Documented Here

These variables exist in the playbook but are not normal operator knobs:

- container image variables
- internal Traefik bridge IP/subnet/gateway
- generated secret filenames
- internal boolean derivations
- constants listing supported proxy modes

Change those only when developing the playbook or debugging a specific issue.

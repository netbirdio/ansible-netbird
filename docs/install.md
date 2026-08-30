# NetBird Client Installation

The `install.yml` playbook installs the NetBird client from the official NetBird package repositories. It can optionally install the desktop UI, manage the NetBird service, and enroll the client with a setup key.

This playbook installs clients only. To deploy a self-hosted NetBird server, use `getting-started.yml` instead.

## Supported Platforms

The playbook detects and supports the following package managers:

- Debian and Ubuntu: `apt`
- Fedora and other RPM-based distributions: `dnf`
- RHEL-compatible distributions: `yum`
- Image-based Fedora systems: `rpm-ostree`
- macOS with Homebrew: `brew`
- macOS without Homebrew: NetBird `.pkg`

Binary-only installation is not supported. The NetBird UI packages are supported only on `amd64` and `arm64`.

## Requirements

The Ansible control host needs Ansible installed and must be able to connect to each target host. Target hosts must provide:

- Python for Ansible
- Privilege escalation through `sudo`, `doas`, or another configured Ansible become method
- Internet access to the NetBird package repositories
- A supported package manager

The SSH user does not need to be root, but package and service tasks require become privileges. Use `--ask-become-pass` if the remote user requires a sudo password.

## Inventory

Create an inventory with a `netbird` group:

```ini
[netbird]
workstation.example.com ansible_user=deploy
192.0.2.20 ansible_user=deploy
```

The repository's `inventory.ini` can also be updated with the intended hosts.

## Basic Installation

Install the command-line client and start its service:

```bash
ansible-playbook -i inventory.ini install.yml --ask-become-pass
```

The default installation does not enroll the client. After installation, sign in interactively on the target host:

```bash
netbird up
```

## Unattended Enrollment

Pass a NetBird setup key to enroll hosts during installation:

```bash
ansible-playbook -i inventory.ini install.yml \
  --ask-become-pass \
  -e netbird_setup_key="$NETBIRD_SETUP_KEY"
```

For a self-hosted management server, also provide its URL:

```bash
ansible-playbook -i inventory.ini install.yml \
  --ask-become-pass \
  -e netbird_setup_key="$NETBIRD_SETUP_KEY" \
  -e netbird_setup_management_url="https://netbird.example.org"
```

When pairing with a reusable setup key, this allows automated mass deployment of NetBird clients.

Avoid placing setup keys directly in inventory files or source control. Ansible Vault or an environment-backed secret workflow is preferable. Tasks that handle the setup key suppress their output with `no_log`.

Enrollment requires `start_netbird_service=true`. By default, the playbook skips enrollment when `netbird status` already reports both Management and Signal as connected. Set `force_netbird_setup_key=true` to enroll again intentionally.

## Common Options

### Install the desktop UI

The UI is disabled by default, which is appropriate for servers and other headless systems:

```bash
ansible-playbook -i inventory.ini install.yml \
  -e install_netbird_ui=true
```

On Linux, the playbook warns if a desktop environment is not detected.

### Converge an existing installation

The playbook refuses to modify a host where the `netbird` command appears to be installed unless explicitly allowed:

```bash
ansible-playbook -i inventory.ini install.yml \
  -e allow_existing_netbird=true
```

This lets the selected package manager converge the existing installation. It does not uninstall NetBird or erase its configuration.

For a Homebrew reinstall, also set `allow_homebrew_reinstall=true`. This permits the playbook to stop and uninstall the existing NetBird service and unlink the package before running `brew install`.

### Control the service

The service is started and enabled at boot by default:

```yaml
start_netbird_service: true
enable_netbird_service: true
```

Override these values when only the package should be installed:

```bash
ansible-playbook -i inventory.ini install.yml \
  -e start_netbird_service=false \
  -e enable_netbird_service=false
```

The macOS `.pkg` path manages its own service and is excluded from the explicit service installation tasks.

### Force a package manager

Package-manager detection can be overridden with one of `apt`, `dnf`, `yum`, `rpm-ostree`, `brew`, or `pkg`:

```bash
ansible-playbook -i inventory.ini install.yml \
  -e force_package_manager=dnf
```

Only use this when the selected package manager is present and appropriate for the target.

## Variable Reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `install_netbird_ui` | `false` | Install the NetBird desktop UI in addition to the CLI. |
| `start_netbird_service` | `true` | Install and start the NetBird service. Required for setup-key enrollment. |
| `enable_netbird_service` | `true` | Enable the service at boot on Linux. |
| `netbird_setup_key` | `""` | Optional setup key for unattended enrollment. |
| `netbird_setup_management_url` | `""` | Optional management URL passed during setup-key enrollment. |
| `force_netbird_setup_key` | `false` | Enroll even when NetBird already reports a connected state. |
| `allow_existing_netbird` | `false` | Allow package convergence when NetBird is already installed. |
| `allow_homebrew_reinstall` | `false` | Permit the Homebrew-specific stop, uninstall, and unlink sequence. |
| `force_package_manager` | `""` | Override automatic package-manager detection. |

Repository URLs, package names, config paths, and the macOS package destination are also variables in `install.yml`. They are implementation defaults and normally should not be overridden.

## Verifying the Installation

Run the following commands on a target host:

```bash
netbird version
netbird status
```

If no setup key was supplied, connect the client with `netbird up`. On Linux, the service can also be inspected with:

```bash
systemctl status netbird
```

For `rpm-ostree`, a reboot may be required before a newly layered package is available in the booted deployment.

## Check Mode

Do not rely on `--check` as a complete dry run. Package-manager detection and status inspection run in check mode, but command-based installation and service operations cannot all be predicted safely without changing the target.

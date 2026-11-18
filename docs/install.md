# NetBird Client Installation

The `install.yml` playbook installs the NetBird client from the official NetBird package repositories. It is a thin wrapper around the `community.ansible_netbird.client` role, which follows [`install.sh`](https://github.com/netbirdio/netbird/blob/main/release_files/install.sh) from the NetBird repository. It can also install the desktop UI, manage the NetBird service, and enroll the client with a setup key.

This playbook installs clients only. To deploy a self-hosted NetBird server, use `getting_started.yml` instead.

## Supported Platforms

The role picks the package manager the same way `install.sh` does:

- Debian and Ubuntu: `apt`
- Fedora, RHEL and compatible distributions: `dnf`, or `yum` where `dnf` is missing
- Fedora Atomic desktops and other rpm-ostree systems: `rpm-ostree`
- macOS: the NetBird `.pkg` installer
- macOS with Homebrew: `brew`, only when selected with `force_package_manager=brew`

Binary-only installation (`install.sh` on Synology and hosts without a supported package manager) is not supported. On NixOS and on bootc systems without rpm-ostree the role stops and explains what to do instead, like `install.sh`. The UI packages exist only for `amd64` and `arm64`.

## Requirements

Target hosts need Python for Ansible, privilege escalation through `sudo`, `doas` or another become method, and HTTPS access to `pkgs.netbird.io`. The SSH user does not need to be root. Use `--ask-become-pass` if `sudo` asks for a password.

## Inventory

The playbook runs against the `netbird` group by default. Set `target_hosts` to use another group.

```ini
[netbird]
workstation.example.com ansible_user=deploy
192.0.2.20 ansible_user=deploy
```

## Basic Installation

Install the command-line client and start its service:

```bash
ansible-playbook -i inventory.ini community.ansible_netbird.install --ask-become-pass
```

From a checkout of this repository, use `playbooks/install.yml` instead of the collection name.

Without a setup key the client is installed but not connected. Sign in on the target host with:

```bash
netbird up
```

## Unattended Enrollment

Pass a setup key to enroll hosts during installation. A reusable key lets you roll NetBird out to many hosts in one run.

```bash
ansible-playbook -i inventory.ini community.ansible_netbird.install \
  -e netbird_setup_key="$NETBIRD_SETUP_KEY" \
  -e netbird_setup_management_url=https://netbird.example.org
```

Leave out `netbird_setup_management_url` to use NetBird Cloud.

The key reaches `netbird up` through the `NB_SETUP_KEY` environment variable rather than the command line, so other users on the host cannot see it in the process list, and the tasks that handle it use `no_log`. Keep the key out of inventory files and source control; Ansible Vault works well.

After `netbird up` the role waits for `netbird status` to report Management as connected and fails if it never does, because `netbird up` can exit successfully without logging in (for example when the management server's TLS certificate is not trusted).

Enrollment is skipped when `netbird status` already reports Management and Signal as connected, so re-running the playbook is safe. Set `force_netbird_setup_key=true` to enroll again, for example to move a host to another management server.

## Common Options

### Install the desktop UI

```bash
ansible-playbook -i inventory.ini community.ansible_netbird.install -e install_netbird_ui=true
```

`install.sh` skips the UI when `XDG_CURRENT_DESKTOP` is unset. Over SSH it is almost always unset, so the role installs the UI when asked and only warns.

### Upgrade NetBird

Packages are installed with `state: present` by default, so a re-run leaves the installed version alone. Set `netbird_package_state=latest` to upgrade on every run. This is not supported on rpm-ostree hosts, where NetBird is updated with the rest of the deployment by `rpm-ostree upgrade`.

### Existing installations

Re-running the playbook on a host it already manages converges it; the package manager is recorded in `/etc/netbird/install.conf` like `install.sh` does. If NetBird is already on the host but was installed some other way (the binary install of `install.sh`, another package manager, or by hand), the role stops rather than install a second copy. Remove the old install first, or set `allow_existing_netbird=true` to let the selected package manager take over.

For Homebrew, `allow_homebrew_reinstall=true` stops and uninstalls the existing NetBird service and unlinks the package before reinstalling it, which is what `install.sh` always does.

### rpm-ostree hosts

Packages layered with rpm-ostree only become available after a reboot. By default the role layers NetBird, says that a reboot is pending, and skips the service and enrollment steps; run the playbook again after rebooting. Set `rpm_ostree_reboot=true` to let the role reboot the host and carry on in the same run.

### Control the service

The service is started and enabled at boot by default. To install the package only:

```bash
ansible-playbook -i inventory.ini community.ansible_netbird.install \
  -e start_netbird_service=false -e enable_netbird_service=false
```

The macOS `.pkg` manages its own service.

### Force a package manager

Override detection with `apt`, `dnf`, `yum`, `rpm-ostree`, `brew` or `pkg`:

```bash
ansible-playbook -i inventory.ini community.ansible_netbird.install -e force_package_manager=dnf
```

## Variable Reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `install_netbird_ui` | `false` | Install the NetBird desktop UI as well as the CLI. |
| `netbird_package_state` | `present` | `present` keeps the installed version, `latest` upgrades. |
| `start_netbird_service` | `true` | Start the service. Required for setup key enrollment. |
| `enable_netbird_service` | `true` | Start the service at boot. |
| `netbird_setup_key` | `""` | Setup key for unattended enrollment. |
| `netbird_setup_management_url` | `""` | Management URL for a self-hosted server. |
| `force_netbird_setup_key` | `false` | Enroll even when the client is already connected. |
| `allow_existing_netbird` | `false` | Take over an install made some other way. |
| `allow_homebrew_reinstall` | `false` | Allow the Homebrew stop, uninstall and unlink sequence. |
| `rpm_ostree_reboot` | `false` | Reboot rpm-ostree hosts so NetBird can start in the same run. |
| `force_package_manager` | `""` | Override package manager detection. |

Repository URLs, the keyring path and the macOS package URL are also role variables (see `roles/client/defaults/main.yml`). They rarely need changing.

## Verifying the Installation

```bash
netbird version
netbird status
systemctl status netbird   # Linux
```

## Check Mode

`--check` runs detection and status checks, but it cannot predict the package and service steps that depend on the repository being configured first. Do not treat it as a complete dry run.

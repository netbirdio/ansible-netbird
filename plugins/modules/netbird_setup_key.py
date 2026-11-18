#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Ansible module for managing NetBird setup keys."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: netbird_setup_key
short_description: Manage NetBird setup keys
description:
  - Create, update, and delete setup keys in NetBird.
  - Setup keys are used to register new peers to the network.
version_added: "1.0.0"
author:
  - NetBird (@netbirdio)
options:
  state:
    description:
      - The desired state of the setup key.
    type: str
    choices: ['present', 'absent']
    default: present
  key_id:
    description:
      - The unique identifier of the setup key.
      - Required when state is absent or when updating by ID.
    type: str
  name:
    description:
      - Name of the setup key.
      - Required when creating a new setup key.
      - Fixed at creation. The API's update accepts only O(revoked) and
        O(auto_groups), so a key found by O(key_id) with a different name
        is not renamed - the module warns about the drift instead.
    type: str
  key_type:
    description:
      - Type of the setup key.
      - "C(one-off) keys can only be used once."
      - "C(reusable) keys can be used multiple times."
    type: str
    choices: ['one-off', 'reusable']
    default: one-off
  expires_in:
    description:
      - Expiration time in seconds.
      - Set to V(0) for a key that never expires.
      - Default is 86400 (24 hours).
    type: int
    default: 86400
  revoked:
    description:
      - Whether the key is revoked.
    type: bool
    default: false
  auto_groups:
    description:
      - List of group IDs to auto-assign to peers registered with this key.
      - When updating an existing key and this is not specified, the current auto_groups are preserved.
    type: list
    elements: str
  usage_limit:
    description:
      - Maximum number of times the key can be used.
      - 0 means unlimited (for reusable keys).
    type: int
    default: 0
  ephemeral:
    description:
      - Whether peers registered with this key are ephemeral.
      - Ephemeral peers are automatically removed when disconnected.
    type: bool
    default: false
  allow_extra_dns_labels:
    description:
      - Allow extra DNS labels for peers registered with this key.
    type: bool
    default: false
  rotate_when_invalid:
    description:
      - What to do when a key is matched by O(name) but cannot enrol a peer
        because it is revoked, expired, or out of uses.
      - When V(false), the key is left untouched and a warning is emitted.
        The task still reports C(changed=false), because nothing was done.
      - When V(true), a replacement is created from the supplied parameters
        and the unusable key is deleted afterwards, so a failed create leaves
        the old key in place. The replacement's secret is returned once, in
        the same way as any newly created key.
      - Requires O(name), since that is what the replacement is created with.
        A key addressed by O(key_id) alone is left untouched and warns
        instead.
      - Has no effect when the matched key is usable, nor when O(revoked=true)
        is the desired state, where a revoked key is what was asked for rather
        than a problem to fix.
    type: bool
    default: false
    version_added: "1.3.0"
extends_documentation_fragment:
  - community.ansible_netbird.netbird
attributes:
  check_mode:
    description: Can run in C(check_mode) and predict changes without modifying the target.
    support: full
  diff_mode:
    description: This module does not report a diff of the changes it makes.
    support: none
requirements:
  - python >= 3.9
'''

EXAMPLES = r'''
- name: Create a one-off setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "new-server-key"
    key_type: "one-off"
    expires_in: 3600
    state: present
  register: setup_key
  # The created key secret (setup_key.key) is returned ONLY on creation.
  # The registered result is sensitive — never print it.

- name: Persist the new setup key value securely (only available on creation)
  ansible.builtin.copy:
    content: "{{ setup_key.setup_key.key }}"
    dest: "/root/.netbird_setup_key"
    mode: "0600"
  no_log: true  # never write a credential to the job log
  when: setup_key.setup_key.key is defined

- name: Create a reusable setup key with auto groups
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "developer-machines"
    key_type: "reusable"
    expires_in: 604800
    auto_groups:
      - "developers-group-id"
    state: present

- name: Create an ephemeral setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    name: "temporary-access"
    key_type: "reusable"
    ephemeral: true
    state: present

- name: Revoke a setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    key_id: "key-id-123"
    revoked: true
    state: present

- name: Delete a setup key
  community.ansible_netbird.netbird_setup_key:
    api_url: "https://netbird.example.com"
    api_token: "{{ netbird_token }}"
    key_id: "key-id-123"
    state: absent
'''

RETURN = r'''
setup_key:
  description: The setup key object.
  returned: success
  type: dict
  contains:
    id:
      description: Setup key ID.
      type: str
    key:
      description:
        - The actual setup key value (only returned on creation).
        - This is a live credential. Ansible cannot mark an individual return
          field as sensitive at runtime, so set C(no_log) to C(true) on any
          task that registers or handles this result to keep it out of logs.
      type: str
    name:
      description: Setup key name.
      type: str
    type:
      description: Key type (one-off or reusable).
      type: str
    expires:
      description: Expiration timestamp.
      type: str
    revoked:
      description: Whether the key is revoked.
      type: bool
    auto_groups:
      description: Auto-assigned group IDs.
      type: list
    usage_limit:
      description: Usage limit.
      type: int
    used_times:
      description: Number of times the key has been used.
      type: int
    last_used:
      description: Last used timestamp.
      type: str
    ephemeral:
      description: Whether key creates ephemeral peers.
      type: bool
    valid:
      description: Whether the key is still valid.
      type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.ansible_netbird.plugins.module_utils.netbird_api import (
    NetBirdAPI,
    NetBirdAPIError,
    extract_ids,
    find_one_by_name,
    netbird_argument_spec
)


def find_setup_key_by_name(api, name):
    """Find a setup key by name."""
    keys, _unused = api.list_setup_keys()
    return find_one_by_name(api, keys, name, 'setup keys')


def setup_key_invalid_reason(key, desired_revoked=False):
    """Why this setup key cannot enrol a peer, or None if it can.

    A name lookup finds a key by name alone, so it happily returns one that
    is revoked, past its expiry, or out of uses. Such a key satisfies no
    desired state: reporting ``changed: false`` against it tells the
    operator enrolment is provisioned when the next peer to use it will
    fail, with nothing connecting the two events.

    ``desired_revoked`` is the task's own ``revoked`` parameter. A task asking
    for a revoked key has an unusable key as its desired state, so nothing
    here is a defect: without this, ``revoked: true`` would report a problem
    on every run, and with rotation enabled would delete and recreate the key
    every run, since the replacement is revoked too.

    ``valid`` is computed server-side and already covers expiry and
    revocation on current API versions, but it is checked last so the more
    specific reasons produce the more useful message.
    """
    if desired_revoked:
        return None

    if key.get('revoked'):
        return 'it is revoked'

    usage_limit = key.get('usage_limit') or 0
    used_times = key.get('used_times') or 0
    if usage_limit and used_times >= usage_limit:
        return 'it has no uses left (used %d of %d)' % (used_times, usage_limit)

    if key.get('valid') is False:
        return 'the API reports it as not valid (expired?)'

    return None


# Parameters the API fixes at creation time. Changing one on an existing key
# is silently ignored, so the module warns rather than pretending it applied.
# Keyed by module param name -> the field the API returns it as.
SETUP_KEY_IMMUTABLE_PARAMS = {
    'name': 'name',
    'key_type': 'type',
    'usage_limit': 'usage_limit',
    'ephemeral': 'ephemeral',
    'allow_extra_dns_labels': 'allow_extra_dns_labels',
}


def setup_key_immutable_drift(current, params, defaults):
    """Immutable parameters the task asked for that the existing key does not have.

    Only reports a parameter the caller set to something other than its
    argspec default. These parameters all carry defaults, so a value equal to
    the default is indistinguishable from one that was never specified, and
    warning on those would fire for every task that simply omits them. The
    consequence is a known blind spot: explicitly asking for a value that
    happens to equal the default is not detected. Removing the defaults would
    fix that properly, but it would change behaviour for existing playbooks.

    ``expires_in`` is deliberately absent: it is a duration at creation time
    and the API returns an absolute ``expires`` timestamp, so the two cannot
    be compared without guessing when the key was made.
    """
    drift = []
    for param, api_field in sorted(SETUP_KEY_IMMUTABLE_PARAMS.items()):
        requested = params.get(param)
        if requested is None or requested == defaults.get(param):
            continue
        if current.get(api_field) != requested:
            drift.append('%s (requested %r, key has %r)'
                         % (param, requested, current.get(api_field)))
    return drift


def setup_key_needs_update(current, params):
    """Check if setup key needs to be updated.

    ``name`` is deliberately not compared: the API's update only accepts
    ``revoked`` and ``auto_groups``, so a name mismatch is unreachable drift,
    not an update — treating it as one reported ``changed: true`` on every
    run while renaming nothing. It is covered by the immutable-drift warning
    instead.
    """
    if params.get('revoked') is not None and current.get('revoked') != params['revoked']:
        return True
    if params.get('auto_groups') is not None:
        current_groups = set(extract_ids(current.get('auto_groups') or []))
        desired_groups = set(extract_ids(params['auto_groups'] or []))
        if current_groups != desired_groups:
            return True
    return False


def run_module():
    """Main module execution."""
    argument_spec = netbird_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        key_id=dict(type='str'),
        name=dict(type='str'),
        key_type=dict(type='str', choices=['one-off', 'reusable'], default='one-off'),
        expires_in=dict(type='int', default=86400),
        revoked=dict(type='bool', default=False),
        auto_groups=dict(type='list', elements='str'),
        usage_limit=dict(type='int', default=0),
        ephemeral=dict(type='bool', default=False),
        allow_extra_dns_labels=dict(type='bool', default=False),
        rotate_when_invalid=dict(type='bool', default=False)
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[
            ('key_id', 'name'),
        ]
    )

    api = NetBirdAPI(
        module,
        module.params['api_url'],
        module.params['api_token'],
        module.params['validate_certs'],
        timeout=module.params['timeout']
    )

    state = module.params['state']
    key_id = module.params['key_id']
    name = module.params['name']

    result = dict(
        changed=False,
        setup_key={}
    )

    try:
        # Find existing setup key
        existing_key = None
        replaced_key_id = None
        if key_id:
            try:
                existing_key, _unused = api.get_setup_key(key_id)
            except NetBirdAPIError as e:
                if e.status_code != 404:
                    raise
        elif name:
            existing_key = find_setup_key_by_name(api, name)

        if state == 'absent':
            if existing_key:
                if not module.check_mode:
                    api.delete_setup_key(existing_key['id'])
                result['changed'] = True
                result['msg'] = 'Setup key deleted successfully'
            module.exit_json(**result)

        # state == 'present'
        if existing_key:
            # The key that was found may be one that cannot enrol anything: a
            # name lookup matches the name and nothing else. Without this the
            # task reports the desired state as met and the failure surfaces
            # later, at enrolment, with nothing pointing back here.
            invalid_reason = setup_key_invalid_reason(
                existing_key, module.params['revoked'])
            if invalid_reason:
                # Rotation creates a replacement from the task's own
                # parameters, so it needs a name to create with. Addressed by
                # key_id alone there is none -- which is why rotation is
                # documented as applying to a name match only.
                if module.params['rotate_when_invalid'] and not name:
                    module.warn(
                        "Setup key '%s' cannot be used because %s, and "
                        "rotate_when_invalid=true cannot replace it: the key "
                        "was addressed by key_id, so there is no name to "
                        "create the replacement with. Pass name as well to "
                        "allow rotation."
                        % (existing_key.get('name'), invalid_reason)
                    )
                elif module.params['rotate_when_invalid']:
                    module.warn(
                        "Setup key '%s' cannot be used because %s; replacing it "
                        "(rotate_when_invalid=true)."
                        % (existing_key.get('name'), invalid_reason)
                    )
                    # Fall through to the create path below. The replacement
                    # is created first and the invalid key deleted after, so
                    # a failed create leaves the old key in place; a failed
                    # delete leaves a same-named duplicate to clean up, which
                    # is recoverable where a destroyed key is not.
                    replaced_key_id = existing_key['id']
                    existing_key = None
                else:
                    module.warn(
                        "Setup key '%s' exists but cannot enrol a peer: "
                        "%s. Leaving it as-is — set rotate_when_invalid=true to "
                        "replace it, or remove it and re-run."
                        % (existing_key.get('name'), invalid_reason)
                    )

        if existing_key:
            drift = setup_key_immutable_drift(
                existing_key, module.params,
                {k: v.get('default') for k, v in argument_spec.items()},
            )
            if drift:
                module.warn(
                    "Setup key '%s' already exists and these parameters are "
                    "fixed at creation, so the request was not applied: %s. "
                    "Recreate the key if the change matters."
                    % (existing_key.get('name'), '; '.join(drift))
                )

            # Use existing values as fallback for fields the user didn't specify
            effective_auto_groups = module.params['auto_groups']
            if effective_auto_groups is None:
                effective_auto_groups = existing_key.get('auto_groups', [])

            # Revocation is one-way. The API refuses to undo it ("can't
            # un-revoke a revoked setup key"), so sending this module's own
            # `revoked: false` default against a revoked key failed the task
            # with a 422 about a field the playbook never mentioned. Carry the
            # current value forward instead, and say why.
            effective_revoked = module.params['revoked']
            if existing_key.get('revoked') and not effective_revoked:
                effective_revoked = True
                module.warn(
                    "Setup key '%s' is revoked, and the API does not allow "
                    "un-revoking one, so revoked=false was not sent. Delete "
                    "the key and create a new one, or set "
                    "rotate_when_invalid=true to have this module do it."
                    % existing_key.get('name')
                )

            # Check if update is needed
            update_params = {
                'name': name,
                'revoked': effective_revoked,
                'auto_groups': effective_auto_groups
            }

            if setup_key_needs_update(existing_key, update_params):
                if not module.check_mode:
                    key, _unused = api.update_setup_key(
                        existing_key['id'],
                        revoked=effective_revoked,
                        auto_groups=effective_auto_groups
                    )
                    result['setup_key'] = key
                else:
                    result['setup_key'] = existing_key
                result['changed'] = True
            else:
                result['setup_key'] = existing_key
        else:
            # Create new setup key
            if not name:
                module.fail_json(msg="name is required when creating a new setup key")

            if not module.check_mode:
                key, _unused = api.create_setup_key(
                    name=name,
                    key_type=module.params['key_type'],
                    expires_in=module.params['expires_in'],
                    revoked=module.params['revoked'],
                    auto_groups=module.params['auto_groups'] or [],
                    usage_limit=module.params['usage_limit'],
                    ephemeral=module.params['ephemeral'],
                    allow_extra_dns_labels=module.params['allow_extra_dns_labels']
                )
                result['setup_key'] = key
                # The creation response carries a one-time plaintext secret
                # (key). Ansible cannot flag a single return value as no_log,
                # so warn the operator to protect it.
                if isinstance(key, dict) and key.get('key'):
                    module.warn(
                        "A new setup key was created; its secret is in the "
                        "'key' return field and is shown only once. Store it "
                        "securely and set no_log: true on tasks that register "
                        "or handle this result."
                    )
                if replaced_key_id:
                    # Rotation: the replacement exists, now retire the invalid
                    # key it stands in for.
                    api.delete_setup_key(replaced_key_id)
            result['changed'] = True

        module.exit_json(**result)

    except NetBirdAPIError as e:
        module.fail_json(msg=str(e), status_code=e.status_code, response=e.response)


def main():
    run_module()


if __name__ == '__main__':
    main()

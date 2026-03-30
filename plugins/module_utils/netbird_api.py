# -*- coding: utf-8 -*-
# Copyright: (c) 2024, Community
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""NetBird API utilities for Ansible modules."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import json
import ssl
from ansible.module_utils.urls import open_url
from ansible.module_utils.basic import env_fallback
from ansible.module_utils.six.moves.urllib.error import HTTPError, URLError
from ansible.module_utils.six.moves.urllib.parse import urlencode


def extract_ids(items):
    """Extract IDs from a list that may contain dicts or plain strings.

    The NetBird API returns related objects as dicts (e.g.
    ``[{"id": "abc", "name": "..."}]``) while module parameters are plain
    ID strings.  This helper normalises both forms to a flat list of ID
    strings so they can be safely compared with ``set()``.
    """
    if not items:
        return []
    return [item['id'] if isinstance(item, dict) else item for item in items]


class NetBirdAPIError(Exception):
    """Exception raised for NetBird API errors."""
    def __init__(self, message, status_code=None, response=None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class NetBirdAPI:
    """NetBird API client for Ansible modules."""

    def __init__(self, module, api_url, api_token, validate_certs=True):
        """
        Initialize the NetBird API client.

        Args:
            module: Ansible module instance
            api_url: Base URL of the NetBird API
            api_token: Personal Access Token for authentication
            validate_certs: Whether to validate SSL certificates
        """
        self.module = module
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.validate_certs = validate_certs
        self.headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _request(self, method, endpoint, data=None, params=None):
        """
        Make an HTTP request to the NetBird API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint (e.g., /api/users)
            data: Request body data (dict)
            params: Query parameters (dict)

        Returns:
            tuple: (response_data, status_code)
        """
        url = f"{self.api_url}{endpoint}"

        if params:
            filtered = {k: v for k, v in params.items() if v is not None}
            if filtered:
                url = f"{url}?{urlencode(filtered)}"

        body = None
        if data is not None:
            body = json.dumps(data)

        try:
            response = open_url(
                url,
                method=method,
                headers=self.headers,
                data=body,
                validate_certs=self.validate_certs,
                timeout=30
            )
            status_code = response.getcode()
            response_body = response.read()

            if response_body:
                try:
                    response_data = json.loads(response_body)
                except (ValueError, json.JSONDecodeError):
                    response_data = response_body.decode('utf-8') if isinstance(response_body, bytes) else response_body
            else:
                response_data = None

            return response_data, status_code

        except HTTPError as e:
            status_code = e.code
            error_body = e.read()
            error_msg = str(e.reason)
            response_data = None

            if error_body:
                try:
                    response_data = json.loads(error_body)
                    if isinstance(response_data, dict):
                        error_msg = response_data.get('message', response_data.get('error', error_msg))
                except (ValueError, json.JSONDecodeError):
                    response_data = error_body.decode('utf-8') if isinstance(error_body, bytes) else error_body

            raise NetBirdAPIError(
                f"API request failed: {error_msg}",
                status_code=status_code,
                response=response_data
            )

        except URLError as e:
            raise NetBirdAPIError(
                f"Failed to connect to API: {str(e.reason)}",
                status_code=-1,
                response=None
            )

        except ssl.SSLError as e:
            raise NetBirdAPIError(
                f"SSL error: {str(e)}. Try setting validate_certs=false if using self-signed certificates.",
                status_code=-1,
                response=None
            )

    def get(self, endpoint, params=None):
        """Make a GET request."""
        return self._request('GET', endpoint, params=params)

    def post(self, endpoint, data=None):
        """Make a POST request."""
        return self._request('POST', endpoint, data=data)

    def put(self, endpoint, data=None):
        """Make a PUT request."""
        return self._request('PUT', endpoint, data=data)

    def patch(self, endpoint, data=None):
        """Make a PATCH request."""
        return self._request('PATCH', endpoint, data=data)

    def delete(self, endpoint):
        """Make a DELETE request."""
        return self._request('DELETE', endpoint)

    # Account operations
    def list_accounts(self):
        """List all accounts."""
        return self.get('/api/accounts')

    def get_account(self, account_id):
        """Get a specific account."""
        return self.get(f'/api/accounts/{account_id}')

    def update_account(self, account_id, settings):
        """Update an account."""
        return self.put(f'/api/accounts/{account_id}', data=settings)

    def delete_account(self, account_id):
        """Delete an account."""
        return self.delete(f'/api/accounts/{account_id}')

    # User operations
    def list_users(self, service_user=None):
        """List all users."""
        params = {}
        if service_user is not None:
            params['service_user'] = str(service_user).lower()
        return self.get('/api/users', params=params if params else None)

    def get_user(self, user_id):
        """Get a specific user."""
        users, _ = self.list_users()
        for user in users:
            if user.get('id') == user_id:
                return user, 200
        return None, 404

    def get_current_user(self):
        """Get the current user."""
        return self.get('/api/users/me')

    def create_user(self, email=None, name=None, role=None, auto_groups=None, is_service_user=False):
        """Create a new user."""
        data = {
            'role': role,
            'auto_groups': auto_groups or [],
            'is_service_user': is_service_user
        }
        if email:
            data['email'] = email
        if name:
            data['name'] = name
        return self.post('/api/users', data=data)

    def update_user(self, user_id, role=None, auto_groups=None, is_blocked=None):
        """Update a user."""
        data = {}
        if role is not None:
            data['role'] = role
        if auto_groups is not None:
            data['auto_groups'] = auto_groups
        if is_blocked is not None:
            data['is_blocked'] = is_blocked
        return self.put(f'/api/users/{user_id}', data=data)

    def delete_user(self, user_id):
        """Delete a user."""
        return self.delete(f'/api/users/{user_id}')

    def resend_user_invitation(self, user_id):
        """Resend user invitation."""
        return self.post(f'/api/users/{user_id}/invite')

    # Token operations
    def list_tokens(self, user_id):
        """List all tokens for a user."""
        return self.get(f'/api/users/{user_id}/tokens')

    def get_token(self, user_id, token_id):
        """Get a specific token."""
        return self.get(f'/api/users/{user_id}/tokens/{token_id}')

    def create_token(self, user_id, name, expires_in=None):
        """Create a new token."""
        data = {'name': name}
        if expires_in is not None:
            data['expires_in'] = expires_in
        return self.post(f'/api/users/{user_id}/tokens', data=data)

    def delete_token(self, user_id, token_id):
        """Delete a token."""
        return self.delete(f'/api/users/{user_id}/tokens/{token_id}')

    # Peer operations
    def list_peers(self):
        """List all peers."""
        return self.get('/api/peers')

    def get_peer(self, peer_id):
        """Get a specific peer."""
        return self.get(f'/api/peers/{peer_id}')

    def update_peer(self, peer_id, name=None, ssh_enabled=None, login_expiration_enabled=None,
                    inactivity_expiration_enabled=None, approval_required=None, ip=None):
        """Update a peer."""
        data = {}
        if name is not None:
            data['name'] = name
        if ssh_enabled is not None:
            data['ssh_enabled'] = ssh_enabled
        if login_expiration_enabled is not None:
            data['login_expiration_enabled'] = login_expiration_enabled
        if inactivity_expiration_enabled is not None:
            data['inactivity_expiration_enabled'] = inactivity_expiration_enabled
        if approval_required is not None:
            data['approval_required'] = approval_required
        if ip is not None:
            data['ip'] = ip
        return self.put(f'/api/peers/{peer_id}', data=data)

    def delete_peer(self, peer_id):
        """Delete a peer."""
        return self.delete(f'/api/peers/{peer_id}')

    # Setup Key operations
    def list_setup_keys(self):
        """List all setup keys."""
        return self.get('/api/setup-keys')

    def get_setup_key(self, key_id):
        """Get a specific setup key."""
        return self.get(f'/api/setup-keys/{key_id}')

    def create_setup_key(self, name, key_type='one-off', expires_in=86400, revoked=False,
                         auto_groups=None, usage_limit=0, ephemeral=False, allow_extra_dns_labels=False):
        """Create a new setup key."""
        data = {
            'name': name,
            'type': key_type,
            'expires_in': expires_in,
            'revoked': revoked,
            'auto_groups': auto_groups or [],
            'usage_limit': usage_limit,
            'ephemeral': ephemeral,
            'allow_extra_dns_labels': allow_extra_dns_labels
        }
        return self.post('/api/setup-keys', data=data)

    def update_setup_key(self, key_id, revoked=None, auto_groups=None):
        """Update a setup key. Only revoked and auto_groups can be changed after creation."""
        data = {}
        if revoked is not None:
            data['revoked'] = revoked
        if auto_groups is not None:
            data['auto_groups'] = auto_groups
        return self.put(f'/api/setup-keys/{key_id}', data=data)

    def delete_setup_key(self, key_id):
        """Delete a setup key."""
        return self.delete(f'/api/setup-keys/{key_id}')

    # Group operations
    def list_groups(self):
        """List all groups."""
        return self.get('/api/groups')

    def get_group(self, group_id):
        """Get a specific group."""
        return self.get(f'/api/groups/{group_id}')

    def create_group(self, name, peers=None, resources=None):
        """Create a new group."""
        data = {
            'name': name,
            'peers': peers or [],
        }
        if resources is not None:
            data['resources'] = resources
        return self.post('/api/groups', data=data)

    def update_group(self, group_id, name=None, peers=None, resources=None):
        """Update a group."""
        data = {}
        if name is not None:
            data['name'] = name
        if peers is not None:
            data['peers'] = peers
        if resources is not None:
            data['resources'] = resources
        return self.put(f'/api/groups/{group_id}', data=data)

    def delete_group(self, group_id):
        """Delete a group."""
        return self.delete(f'/api/groups/{group_id}')

    # Policy operations
    def list_policies(self):
        """List all policies."""
        return self.get('/api/policies')

    def get_policy(self, policy_id):
        """Get a specific policy."""
        return self.get(f'/api/policies/{policy_id}')

    def create_policy(self, name, enabled=True, description='', rules=None, source_posture_checks=None):
        """Create a new policy."""
        data = {
            'name': name,
            'enabled': enabled,
            'description': description,
            'rules': rules or []
        }
        if source_posture_checks is not None:
            data['source_posture_checks'] = source_posture_checks
        return self.post('/api/policies', data=data)

    def update_policy(self, policy_id, name=None, enabled=None, description=None, rules=None,
                      source_posture_checks=None):
        """Update a policy."""
        data = {}
        if name is not None:
            data['name'] = name
        if enabled is not None:
            data['enabled'] = enabled
        if description is not None:
            data['description'] = description
        if rules is not None:
            data['rules'] = rules
        if source_posture_checks is not None:
            data['source_posture_checks'] = source_posture_checks
        return self.put(f'/api/policies/{policy_id}', data=data)

    def delete_policy(self, policy_id):
        """Delete a policy."""
        return self.delete(f'/api/policies/{policy_id}')

    # Network operations
    def list_networks(self):
        """List all networks."""
        return self.get('/api/networks')

    def get_network(self, network_id):
        """Get a specific network."""
        return self.get(f'/api/networks/{network_id}')

    def create_network(self, name, description=''):
        """Create a new network."""
        data = {
            'name': name,
            'description': description
        }
        return self.post('/api/networks', data=data)

    def update_network(self, network_id, name=None, description=None):
        """Update a network."""
        data = {}
        if name is not None:
            data['name'] = name
        if description is not None:
            data['description'] = description
        return self.put(f'/api/networks/{network_id}', data=data)

    def delete_network(self, network_id):
        """Delete a network."""
        return self.delete(f'/api/networks/{network_id}')

    # Network Router operations
    def list_network_routers(self, network_id):
        """List all routers for a network."""
        return self.get(f'/api/networks/{network_id}/routers')

    def get_network_router(self, network_id, router_id):
        """Get a specific network router."""
        return self.get(f'/api/networks/{network_id}/routers/{router_id}')

    def create_network_router(self, network_id, peer_id=None, peer_groups=None, metric=9999,
                              masquerade=False, enabled=True):
        """Create a new network router."""
        data = {
            'metric': metric,
            'masquerade': masquerade,
            'enabled': enabled
        }
        if peer_id:
            data['peer'] = peer_id
        if peer_groups:
            data['peer_groups'] = peer_groups
        return self.post(f'/api/networks/{network_id}/routers', data=data)

    def update_network_router(self, network_id, router_id, peer_id=None, peer_groups=None,
                              metric=None, masquerade=None, enabled=None):
        """Update a network router."""
        data = {}
        if peer_id is not None:
            data['peer'] = peer_id
        if peer_groups is not None:
            data['peer_groups'] = peer_groups
        if metric is not None:
            data['metric'] = metric
        if masquerade is not None:
            data['masquerade'] = masquerade
        if enabled is not None:
            data['enabled'] = enabled
        return self.put(f'/api/networks/{network_id}/routers/{router_id}', data=data)

    def delete_network_router(self, network_id, router_id):
        """Delete a network router."""
        return self.delete(f'/api/networks/{network_id}/routers/{router_id}')

    # Network Resource operations
    def list_network_resources(self, network_id):
        """List all resources for a network."""
        return self.get(f'/api/networks/{network_id}/resources')

    def get_network_resource(self, network_id, resource_id):
        """Get a specific network resource."""
        return self.get(f'/api/networks/{network_id}/resources/{resource_id}')

    def create_network_resource(self, network_id, address, name='', description='', enabled=True, groups=None):
        """Create a new network resource."""
        data = {
            'address': address,
            'name': name,
            'description': description,
            'enabled': enabled,
            'groups': groups or []
        }
        return self.post(f'/api/networks/{network_id}/resources', data=data)

    def update_network_resource(self, network_id, resource_id, address=None, name=None, 
                                description=None, enabled=None, groups=None):
        """Update a network resource."""
        data = {}
        if address is not None:
            data['address'] = address
        if name is not None:
            data['name'] = name
        if description is not None:
            data['description'] = description
        if enabled is not None:
            data['enabled'] = enabled
        if groups is not None:
            data['groups'] = groups
        return self.put(f'/api/networks/{network_id}/resources/{resource_id}', data=data)

    def delete_network_resource(self, network_id, resource_id):
        """Delete a network resource."""
        return self.delete(f'/api/networks/{network_id}/resources/{resource_id}')

    # Route operations (deprecated but still functional)
    def list_routes(self):
        """List all routes."""
        return self.get('/api/routes')

    def get_route(self, route_id):
        """Get a specific route."""
        return self.get(f'/api/routes/{route_id}')

    def create_route(self, network_id, network, description='', peer_id=None, peer_groups=None,
                     metric=9999, masquerade=True, enabled=True, groups=None, keep_route=False,
                     domains=None):
        """Create a new route."""
        data = {
            'network_id': network_id,
            'network': network,
            'description': description,
            'metric': metric,
            'masquerade': masquerade,
            'enabled': enabled,
            'groups': groups or [],
            'keep_route': keep_route
        }
        if peer_id:
            data['peer'] = peer_id
        if peer_groups:
            data['peer_groups'] = peer_groups
        if domains:
            data['domains'] = domains
        return self.post('/api/routes', data=data)

    def update_route(self, route_id, network_id=None, network=None, description=None, 
                     peer_id=None, peer_groups=None, metric=None, masquerade=None, 
                     enabled=None, groups=None, keep_route=None, domains=None):
        """Update a route."""
        data = {}
        if network_id is not None:
            data['network_id'] = network_id
        if network is not None:
            data['network'] = network
        if description is not None:
            data['description'] = description
        if peer_id is not None:
            data['peer'] = peer_id
        if peer_groups is not None:
            data['peer_groups'] = peer_groups
        if metric is not None:
            data['metric'] = metric
        if masquerade is not None:
            data['masquerade'] = masquerade
        if enabled is not None:
            data['enabled'] = enabled
        if groups is not None:
            data['groups'] = groups
        if keep_route is not None:
            data['keep_route'] = keep_route
        if domains is not None:
            data['domains'] = domains
        return self.put(f'/api/routes/{route_id}', data=data)

    def delete_route(self, route_id):
        """Delete a route."""
        return self.delete(f'/api/routes/{route_id}')

    # DNS operations
    def get_dns_settings(self):
        """Get DNS settings."""
        return self.get('/api/dns/settings')

    def update_dns_settings(self, disabled_management_groups=None):
        """Update DNS settings."""
        data = {}
        if disabled_management_groups is not None:
            data['disabled_management_groups'] = disabled_management_groups
        return self.put('/api/dns/settings', data=data)

    def list_nameserver_groups(self):
        """List all nameserver groups."""
        return self.get('/api/dns/nameservers')

    def get_nameserver_group(self, nsgroup_id):
        """Get a specific nameserver group."""
        return self.get(f'/api/dns/nameservers/{nsgroup_id}')

    def create_nameserver_group(self, name, nameservers, description='', groups=None, 
                                 domains=None, enabled=True, primary=False, 
                                 search_domains_enabled=True):
        """Create a new nameserver group."""
        data = {
            'name': name,
            'nameservers': nameservers,
            'description': description,
            'groups': groups or [],
            'domains': domains or [],
            'enabled': enabled,
            'primary': primary,
            'search_domains_enabled': search_domains_enabled
        }
        return self.post('/api/dns/nameservers', data=data)

    def update_nameserver_group(self, nsgroup_id, name=None, nameservers=None, description=None,
                                 groups=None, domains=None, enabled=None, primary=None,
                                 search_domains_enabled=None):
        """Update a nameserver group."""
        data = {}
        if name is not None:
            data['name'] = name
        if nameservers is not None:
            data['nameservers'] = nameservers
        if description is not None:
            data['description'] = description
        if groups is not None:
            data['groups'] = groups
        if domains is not None:
            data['domains'] = domains
        if enabled is not None:
            data['enabled'] = enabled
        if primary is not None:
            data['primary'] = primary
        if search_domains_enabled is not None:
            data['search_domains_enabled'] = search_domains_enabled
        return self.put(f'/api/dns/nameservers/{nsgroup_id}', data=data)

    def delete_nameserver_group(self, nsgroup_id):
        """Delete a nameserver group."""
        return self.delete(f'/api/dns/nameservers/{nsgroup_id}')

    # DNS Zone operations
    def list_dns_zones(self):
        """List all DNS zones."""
        return self.get('/api/dns/zones')

    def get_dns_zone(self, zone_id):
        """Get a specific DNS zone."""
        return self.get(f'/api/dns/zones/{zone_id}')

    def create_dns_zone(self, name, domain, enabled=True, distribution_groups=None,
                         enable_search_domain=False):
        """Create a new DNS zone."""
        data = {
            'name': name,
            'domain': domain,
            'enabled': enabled,
            'enable_search_domain': enable_search_domain,
            'distribution_groups': distribution_groups or []
        }
        return self.post('/api/dns/zones', data=data)

    def update_dns_zone(self, zone_id, name=None, domain=None, enabled=None,
                         distribution_groups=None, enable_search_domain=None):
        """Update a DNS zone."""
        data = {}
        if name is not None:
            data['name'] = name
        if domain is not None:
            data['domain'] = domain
        if enabled is not None:
            data['enabled'] = enabled
        if distribution_groups is not None:
            data['distribution_groups'] = distribution_groups
        if enable_search_domain is not None:
            data['enable_search_domain'] = enable_search_domain
        return self.put(f'/api/dns/zones/{zone_id}', data=data)

    def delete_dns_zone(self, zone_id):
        """Delete a DNS zone."""
        return self.delete(f'/api/dns/zones/{zone_id}')

    # DNS Zone Record operations
    def list_dns_zone_records(self, zone_id):
        """List all records for a DNS zone."""
        return self.get(f'/api/dns/zones/{zone_id}/records')

    def get_dns_zone_record(self, zone_id, record_id):
        """Get a specific DNS zone record."""
        return self.get(f'/api/dns/zones/{zone_id}/records/{record_id}')

    def create_dns_zone_record(self, zone_id, name, record_type, content, ttl=300):
        """Create a DNS zone record."""
        data = {
            'name': name,
            'type': record_type,
            'content': content,
            'ttl': ttl
        }
        return self.post(f'/api/dns/zones/{zone_id}/records', data=data)

    def update_dns_zone_record(self, zone_id, record_id, name=None, record_type=None,
                               content=None, ttl=None):
        """Update a DNS zone record."""
        data = {}
        if name is not None:
            data['name'] = name
        if record_type is not None:
            data['type'] = record_type
        if content is not None:
            data['content'] = content
        if ttl is not None:
            data['ttl'] = ttl
        return self.put(f'/api/dns/zones/{zone_id}/records/{record_id}', data=data)

    def delete_dns_zone_record(self, zone_id, record_id):
        """Delete a DNS zone record."""
        return self.delete(f'/api/dns/zones/{zone_id}/records/{record_id}')

    # Posture Check operations
    def list_posture_checks(self):
        """List all posture checks."""
        return self.get('/api/posture-checks')

    def get_posture_check(self, check_id):
        """Get a specific posture check."""
        return self.get(f'/api/posture-checks/{check_id}')

    def create_posture_check(self, name, description='', checks=None):
        """Create a new posture check."""
        data = {
            'name': name,
            'description': description,
            'checks': checks or {}
        }
        return self.post('/api/posture-checks', data=data)

    def update_posture_check(self, check_id, name=None, description=None, checks=None):
        """Update a posture check."""
        data = {}
        if name is not None:
            data['name'] = name
        if description is not None:
            data['description'] = description
        if checks is not None:
            data['checks'] = checks
        return self.put(f'/api/posture-checks/{check_id}', data=data)

    def delete_posture_check(self, check_id):
        """Delete a posture check."""
        return self.delete(f'/api/posture-checks/{check_id}')

    # Event operations
    def list_events(self):
        """List all events."""
        return self.get('/api/events')

    # Identity Provider operations
    def list_identity_providers(self):
        """List all identity providers."""
        return self.get('/api/identity-providers')

    def get_identity_provider(self, idp_id):
        """Get a specific identity provider."""
        return self.get(f'/api/identity-providers/{idp_id}')

    def create_identity_provider(self, name, idp_type, issuer, client_id, client_secret):
        """Create a new identity provider."""
        data = {
            'name': name,
            'type': idp_type,
            'issuer': issuer,
            'client_id': client_id,
            'client_secret': client_secret
        }
        return self.post('/api/identity-providers', data=data)

    def update_identity_provider(self, idp_id, name=None, idp_type=None, issuer=None,
                                 client_id=None, client_secret=None):
        """Update an identity provider."""
        data = {}
        if name is not None:
            data['name'] = name
        if idp_type is not None:
            data['type'] = idp_type
        if issuer is not None:
            data['issuer'] = issuer
        if client_id is not None:
            data['client_id'] = client_id
        if client_secret is not None:
            data['client_secret'] = client_secret
        return self.put(f'/api/identity-providers/{idp_id}', data=data)

    def delete_identity_provider(self, idp_id):
        """Delete an identity provider."""
        return self.delete(f'/api/identity-providers/{idp_id}')

    # User Invite operations
    def list_user_invites(self):
        """List all user invites."""
        return self.get('/api/users/invites')

    def create_user_invite(self, email, name=None, role=None, auto_groups=None, expires_in=None):
        """Create a new user invite."""
        data = {'email': email}
        if name is not None:
            data['name'] = name
        if role is not None:
            data['role'] = role
        if auto_groups is not None:
            data['auto_groups'] = auto_groups
        if expires_in is not None:
            data['expires_in'] = expires_in
        return self.post('/api/users/invites', data=data)

    def delete_user_invite(self, invite_id):
        """Delete a user invite."""
        return self.delete(f'/api/users/invites/{invite_id}')

    def regenerate_user_invite(self, invite_id, expires_in=None):
        """Regenerate a user invite token."""
        data = {}
        if expires_in is not None:
            data['expires_in'] = expires_in
        return self.post(f'/api/users/invites/{invite_id}/regenerate', data=data)

    # User approval operations
    def approve_user(self, user_id):
        """Approve a pending user."""
        return self.post(f'/api/users/{user_id}/approve')

    def reject_user(self, user_id):
        """Reject a pending user."""
        return self.delete(f'/api/users/{user_id}/reject')

    # Geo-location operations
    def list_countries(self):
        """List all countries."""
        return self.get('/api/locations/countries')

    def list_cities_by_country(self, country_code):
        """List cities by country code."""
        return self.get(f'/api/locations/countries/{country_code}/cities')


def netbird_argument_spec():
    """Return the argument spec common to all NetBird modules."""
    return dict(
        api_url=dict(
            type='str',
            required=True,
            fallback=(env_fallback, ['NETBIRD_API_URL'])
        ),
        api_token=dict(
            type='str',
            required=True,
            no_log=True,
            fallback=(env_fallback, ['NETBIRD_API_TOKEN'])
        ),
        validate_certs=dict(
            type='bool',
            default=True
        )
    )



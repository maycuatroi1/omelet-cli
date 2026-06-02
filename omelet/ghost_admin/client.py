"""Thin wrapper around the Ghost Admin API.

Provides JWT auth, GET/PUT/DELETE primitives, and id/slug resolution used by
every higher-level operation in this package.
"""
import re
import time
from typing import Optional

import jwt
import requests


class GhostAdmin:
    """Thin wrapper around Ghost Admin API for bulk operations.

    Reuses credentials from Config (api_url + admin_api_key). Generates
    a fresh JWT per request — Ghost tokens expire in 5 minutes.
    """

    def __init__(self, api_url: str, admin_api_key: str):
        self.api_url = api_url.rstrip('/')
        key_id, secret = admin_api_key.split(':')
        self.key_id = key_id
        self.secret = secret

    def _token(self) -> str:
        iat = int(time.time())
        return jwt.encode(
            {'iat': iat, 'exp': iat + 300, 'aud': '/admin/'},
            bytes.fromhex(self.secret),
            algorithm='HS256',
            headers={'alg': 'HS256', 'typ': 'JWT', 'kid': self.key_id},
        )

    def _headers(self, json_body: bool = False) -> dict:
        h = {'Authorization': f'Ghost {self._token()}'}
        if json_body:
            h['Content-Type'] = 'application/json'
        return h

    def get_post_or_page(self, slug: str, formats: str = '', include: str = '') -> Optional[tuple]:
        """Find post or page by slug. Returns (object, kind) or None."""
        params = []
        if formats:
            params.append(f'formats={formats}')
        if include:
            params.append(f'include={include}')
        qs = '?' + '&'.join(params) if params else ''
        for kind in ('posts', 'pages'):
            r = requests.get(
                f'{self.api_url}/ghost/api/admin/{kind}/slug/{slug}/{qs}',
                headers=self._headers(),
            )
            if r.ok:
                return r.json()[kind][0], kind
        return None

    def get_by_id(self, obj_id: str, formats: str = '', include: str = '') -> Optional[tuple]:
        """Find post or page by id. Returns (object, kind) or None."""
        params = []
        if formats:
            params.append(f'formats={formats}')
        if include:
            params.append(f'include={include}')
        qs = '?' + '&'.join(params) if params else ''
        for kind in ('posts', 'pages'):
            r = requests.get(
                f'{self.api_url}/ghost/api/admin/{kind}/{obj_id}/{qs}',
                headers=self._headers(),
            )
            if r.ok:
                return r.json()[kind][0], kind
        return None

    def find(self, identifier: str, formats: str = '', include: str = '') -> Optional[tuple]:
        """Resolve identifier (24-hex id OR slug) to (object, kind). Tries id first if it matches."""
        if re.fullmatch(r'[0-9a-f]{24}', identifier):
            found = self.get_by_id(identifier, formats=formats, include=include)
            if found:
                return found
        return self.get_post_or_page(identifier, formats=formats, include=include)

    def update(self, kind: str, obj_id: str, updated_at: str, **fields) -> requests.Response:
        body = {kind: [{'id': obj_id, 'updated_at': updated_at, **fields}]}
        url = f'{self.api_url}/ghost/api/admin/{kind}/{obj_id}/'
        if 'html' in fields:
            url += '?source=html'
        return requests.put(url, headers=self._headers(json_body=True), json=body)

    def list_all(self, endpoint: str, params: str = '', limit: int = 100) -> list:
        """Paginate through all items at endpoint (e.g. 'posts', 'tags')."""
        all_items = []
        page = 1
        while True:
            sep = '&' if params else ''
            r = requests.get(
                f'{self.api_url}/ghost/api/admin/{endpoint}/?{params}{sep}limit={limit}&page={page}',
                headers=self._headers(),
            )
            if not r.ok:
                break
            data = r.json()
            all_items.extend(data[endpoint])
            if not data['meta']['pagination']['next']:
                break
            page += 1
        return all_items

    def delete(self, endpoint: str, obj_id: str) -> requests.Response:
        return requests.delete(
            f'{self.api_url}/ghost/api/admin/{endpoint}/{obj_id}/',
            headers=self._headers(),
        )

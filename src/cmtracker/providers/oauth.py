"""Minimale OAuth-1.0a-Signatur (HMAC-SHA1) wie von der Cardmarket-API verlangt."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote


def _enc(value: str) -> str:
    return quote(str(value), safe="~")


def build_auth_header(
    method: str,
    url: str,
    app_token: str,
    app_secret: str,
    access_token: str,
    access_token_secret: str,
    params: dict[str, str] | None = None,
    nonce: str | None = None,
    timestamp: str | None = None,
    include_realm: bool = True,
) -> str:
    """Erzeugt den ``Authorization``-Header.

    ``url`` muss ohne Query-String übergeben werden; Query-Parameter gehören in ``params``.
    """
    oauth = {
        "oauth_consumer_key": app_token,
        "oauth_token": access_token,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_version": "1.0",
    }
    all_params = {**oauth, **(params or {})}
    param_str = "&".join(
        f"{k}={v}" for k, v in sorted((_enc(k), _enc(v)) for k, v in all_params.items())
    )
    base_string = "&".join([method.upper(), _enc(url), _enc(param_str)])
    key = f"{_enc(app_secret)}&{_enc(access_token_secret)}"
    digest = hmac.new(key.encode(), base_string.encode(), hashlib.sha1).digest()
    oauth["oauth_signature"] = base64.b64encode(digest).decode()

    parts = [f'realm="{url}"'] if include_realm else []
    parts += [f'{k}="{_enc(v)}"' for k, v in oauth.items()]
    return "OAuth " + ", ".join(parts)

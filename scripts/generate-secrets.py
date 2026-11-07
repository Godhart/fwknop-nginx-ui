#!/usr/bin/env python3
"""Emit YAML (JSON is valid YAML) to stdout; redirect and encrypt with Vault."""
import base64
import json
import secrets
import sys
names = sys.argv[1:] or ['admin']
print(json.dumps({'vault_spa_clients': [dict(name=n,
    key_base64=base64.b64encode(secrets.token_bytes(32)).decode(),
    hmac_key_base64=base64.b64encode(secrets.token_bytes(32)).decode())
    for n in names]}, indent=2))

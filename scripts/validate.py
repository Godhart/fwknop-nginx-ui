#!/usr/bin/env python3
import base64
import ipaddress
import json
import re
import sys

RESERVED = {80, 443, 8081, 8444, 9000, 9080, 9180}

def validate(s, clients):
    assert s['spa_ssh_rescue_cidrs'], 'Set explicit rescue CIDR before deployment'
    for key in ['spa_ssh_rescue_cidrs', 'spa_web_bypass_cidrs']:
        for cidr in s[key]:
            net = ipaddress.ip_network(cidr, strict=True)
            assert net.prefixlen > 0, 'Do not use world-wide bypass/rescue'
    for key in ['spa_public_extra_tcp_ports', 'spa_public_extra_udp_ports',
                'spa_protected_tcp_ports', 'spa_protected_udp_ports']:
        for port in s[key]:
            assert type(port) is int and 1 <= port <= 65535 and port not in RESERVED
    assert type(s['spa_lease_seconds']) is int and 30 <= s['spa_lease_seconds'] <= 3600
    assert 1 <= s['spa_packet_max_age'] <= 600
    assert 1 <= s['spa_knock_udp_port'] <= 65535
    assert s['spa_knock_udp_port'] not in RESERVED
    assert 1 <= s['spa_ssh_port'] <= 65535 and s['spa_ssh_port'] not in RESERVED
    assert re.fullmatch(r'/[a-zA-Z0-9/_-]+', s['spa_root'])
    assert s['spa_stub_mode'] in ['page', 'empty', 'redirect']
    assert s['spa_redirect_scheme'] in ['http', 'https']
    assert 1 <= s['spa_redirect_port'] <= 65535
    assert clients and len({c['name'] for c in clients}) == len(clients)
    keys = set()
    for c in clients:
        assert re.fullmatch(r'[A-Za-z0-9_-]+', c['name'])
        for key in ['key_base64', 'hmac_key_base64']:
            assert len(base64.b64decode(c[key], validate=True)) == 32
        pair = (c['key_base64'], c['hmac_key_base64'])
        assert pair not in keys
        keys.add(pair)

if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        validate(data['settings'], data['clients'])
    except (AssertionError, ValueError, KeyError, TypeError) as exc:
        sys.exit('Invalid SPA configuration: ' + str(exc))

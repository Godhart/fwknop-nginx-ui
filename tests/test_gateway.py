import base64
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.s = yaml.safe_load((ROOT / 'group_vars/all/main.yml').read_text())
        self.s['spa_ssh_rescue_cidrs'] = ['198.51.100.1/32']
        self.s['spa_clients'] = [dict(name='test', key_base64=base64.b64encode(b'k'*32).decode(),
                                      hmac_key_base64=base64.b64encode(b'h'*32).decode())]
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(ROOT / 'templates'),
                                      undefined=jinja2.StrictUndefined)
        self.env.filters['to_json'] = json.dumps

    def render(self, filename):
        return self.env.get_template(filename + '.j2').render(**self.s)

    def test_all_templates_render(self):
        for p in (ROOT / 'templates').glob('*.j2'):
            self.assertTrue(self.render(p.name[:-3]))

    def test_valid_settings(self):
        module('validate').validate(self.s, self.s['spa_clients'])

    def test_reserved_ports_rejected(self):
        for port in module('validate').RESERVED:
            for key in ['spa_protected_tcp_ports','spa_public_extra_tcp_ports',
                        'spa_protected_udp_ports','spa_public_extra_udp_ports']:
                s = copy.deepcopy(self.s); s[key] = [port]
                with self.assertRaises(AssertionError):
                    module('validate').validate(s, s['spa_clients'])

    def test_rescue_required_and_world_rejected(self):
        for networks in [[], ['0.0.0.0/0'], ['::/0']]:
            self.s['spa_ssh_rescue_cidrs'] = networks
            with self.assertRaises(AssertionError):
                module('validate').validate(self.s, self.s['spa_clients'])

    def test_bad_client_rejected(self):
        self.s['spa_clients'][0]['name'] = 'test\nSOURCE ANY'
        with self.assertRaises(AssertionError):
            module('validate').validate(self.s, self.s['spa_clients'])

    def test_ipv6_rules(self):
        self.s['spa_web_bypass_cidrs'] = ['2001:db8::/64']
        self.s['spa_ssh_rescue_cidrs'] = ['2001:db8::1/128']
        rules = self.render('spa-gate.nft')
        self.assertIn('ip6 saddr 2001:db8::/64 return', rules)
        self.assertIn('ip6 saddr 2001:db8::1/128 tcp dport 22 accept', rules)

    def test_stub_modes_and_challenge(self):
        for mode, expected in [('page', 'return 200'), ('empty', 'return 444'),
                               ('redirect', 'return 302 http://$spa_redirect_host:80/')]:
            self.s['spa_stub_mode'] = mode
            conf = self.render('bootstrap.conf')
            self.assertIn(expected, conf)
            self.assertIn('proxy_pass http://127.0.0.1:9180;', conf)
        self.s['spa_http01'] = False
        self.assertNotIn('acme-challenge', self.render('bootstrap.conf'))

    def test_compose_no_publications_and_writable(self):
        service = yaml.safe_load(self.render('compose.yml'))['services']['nginx-ui']
        self.assertEqual(service['network_mode'], 'host')
        self.assertEqual(service['restart'], 'no')
        self.assertNotIn('ports', service)
        self.assertEqual(service['environment']['NGINX_UI_SERVER_HOST'], '127.0.0.1')
        self.assertTrue(all(not v.endswith(':ro') for v in service['volumes']))

    def test_firewall_admin_drop_precedes_established(self):
        rules = self.render('spa-gate.nft')
        self.assertLess(rules.index('tcp dport { 9000, 9080, 9180 } drop'),
                        rules.index('ct state established,related accept'))
        self.assertIn('tcp dport 80 redirect to :8081', rules)
        self.assertIn('tcp dport 443 redirect to :8444', rules)
        self.assertNotIn('flush ruleset', rules)

    def test_lease_input_validation(self):
        lease = module('spa-lease-add')
        for address, ttl in [('::1','300'),('1.2.3.4; id','300'),('1.2.3.4','29'),
                             ('224.0.0.1','300'),('0.0.0.0','300'),('1.2.3.4','3601')]:
            with self.assertRaises(ValueError): lease.build_transaction(address, ttl)

    def test_lease_atomic_refresh_and_no_shell(self):
        lease = module('spa-lease-add')
        batch = lease.build_transaction('198.51.100.2','300')
        self.assertEqual(len(batch.splitlines()), 3)
        with patch.object(lease.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertEqual(lease.main(['helper','198.51.100.2','300']), 0)
            self.assertEqual(run.call_args.args[0], ['/usr/sbin/nft','-f','-'])
            self.assertNotIn('shell', run.call_args.kwargs)
            self.assertEqual(run.call_args.kwargs['input'], batch)

    def test_table_replacement_atomic(self):
        helper = module('spa-gate-apply')
        self.assertEqual(helper.make_batch('table inet spa_gate {}', True),
                         'delete table inet spa_gate\ntable inet spa_gate {}\n')
        self.assertNotIn('delete', helper.make_batch('table inet spa_gate {}', False))

    def test_bootstrap_not_overwritten(self):
        tasks = yaml.safe_load((ROOT / 'playbook.yml').read_text())[0]['tasks']
        seeds = [t['ansible.builtin.template'] for t in tasks if 'ansible.builtin.template' in t
                 and t['ansible.builtin.template']['src'] in ['nginx.conf.j2','bootstrap.conf.j2']]
        self.assertEqual(len(seeds), 2)
        self.assertTrue(all(t['force'] is False for t in seeds))

    def test_ui_forwarded_headers_are_local_only(self):
        conf = self.render('bootstrap.conf')
        self.assertIn('map $http_x_forwarded_proto $forwarded_proto', conf)
        self.assertIn('map $http_x_forwarded_host $forwarded_host', conf)
        self.assertIn("'' $scheme;", conf)
        self.assertIn("'' $http_host;", conf)
        ui, public = conf.split('server {\n listen 80 default_server;', 1)
        self.assertIn('listen 127.0.0.1:9080;', ui)
        self.assertIn('proxy_set_header X-Forwarded-Proto $forwarded_proto;', ui)
        self.assertIn('proxy_set_header X-Forwarded-Host $forwarded_host;', ui)
        self.assertNotIn('$forwarded_proto', public)
        self.assertNotIn('$forwarded_host', public)

    def test_service_firewall_dependency(self):
        conf = self.render('spa-proxy.service')
        self.assertIn('Requires=docker.service spa-gate.service', conf)
        self.assertIn('ExecStartPre=/usr/local/sbin/spa-gate-apply', conf)

if __name__ == '__main__': unittest.main()

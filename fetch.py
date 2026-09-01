#!/usr/bin/env python3
# pyright: reportConstantRedefinition = none
# pyright: reportMissingTypeStubs = none
# pyright: reportRedeclaration = none
# pyright: reportMissingParameterType = none
# pyright: reportUnnecessaryIsInstance = none
# pyright: reportUnknownVariableType = none
# pyright: reportUnknownMemberType = none
# pyright: reportUnknownArgumentType = none
# pyright: reportArgumentType = none
# pyright: reportAttributeAccessIssue = none
# pyright: reportGeneralTypeIssues = none
import yaml
import json
import base64
from urllib.parse import quote, unquote, urlparse
import requests
from requests_file import FileAdapter
import datetime
import traceback
import binascii
import threading
import socket
import concurrent.futures
import sys
import os
import copy
from types import FunctionType as function
from typing import Set, List, Dict, Tuple, Union, Callable, Any, Optional, no_type_check

try: PROXY = open("local_proxy.conf").read().strip()
except FileNotFoundError: LOCAL = False; PROXY = None
else:
    if not PROXY: PROXY = None
    LOCAL = not PROXY

def b64encodes(s: str):
    return base64.b64encode(s.encode('utf-8')).decode('utf-8')

def b64encodes_safe(s: str):
    return base64.urlsafe_b64encode(s.encode('utf-8')).decode('utf-8')

def b64decodes(s: str):
    ss = s + '=' * ((4-len(s)%4)%4)
    try:
        return base64.b64decode(ss.encode('utf-8')).decode('utf-8',errors='ignore')
    except UnicodeDecodeError: raise
    except binascii.Error: raise

def b64decodes_safe(s: str):
    ss = s + '=' * ((4-len(s)%4)%4)
    try:
        return base64.urlsafe_b64decode(ss.encode('utf-8')).decode('utf-8',errors='ignore')
    except UnicodeDecodeError: raise
    except binascii.Error: raise

DEFAULT_UUID = '8'*8+'-8888'*3+'-'+'8'*12

CLASH2VMESS = {'name': 'ps', 'server': 'add', 'port': 'port', 'uuid': 'id', 
              'alterId': 'aid', 'cipher': 'scy', 'network': 'net', 'servername': 'sni'}
VMESS2CLASH: Dict[str, str] = {}
for k,v in CLASH2VMESS.items(): VMESS2CLASH[v] = k

VMESS_EXAMPLE = {
    "v": "2", "ps": "", "add": "0.0.0.0", "port": "0", "aid": "0", "scy": "auto",
    "net": "tcp", "type": "none", "tls": "", "id": DEFAULT_UUID
}

CLASH_CIPHER_VMESS = "auto aes-128-gcm chacha20-poly1305 none".split()
CLASH_CIPHER_SS = "aes-128-gcm aes-192-gcm aes-256-gcm aes-128-cfb aes-192-cfb \
        aes-256-cfb aes-128-ctr aes-192-ctr aes-256-ctr rc4-md5 chacha20-ietf \
        xchacha20 chacha20-ietf-poly1305 xchacha20-ietf-poly1305".split()
CLASH_SSR_OBFS = "plain http_simple http_post random_head tls1.2_ticket_auth tls1.2_ticket_fastauth".split()
CLASH_SSR_PROTOCOL = "origin auth_sha1_v4 auth_aes128_md5 auth_aes128_sha1 auth_chain_a auth_chain_b".split()

ABFURLS = (
    "https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/ChineseFilter/sections/adservers.txt",
    "https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/ChineseFilter/sections/adservers_firstparty.txt",
    "https://raw.githubusercontent.com/AdguardTeam/FiltersRegistry/master/filters/filter_224_Chinese/filter.txt",
    # "https://raw.githubusercontent.com/AdguardTeam/FiltersRegistry/master/filters/filter_15_DnsFilter/filter.txt",
    # "https://malware-filter.gitlab.io/malware-filter/urlhaus-filter-ag.txt",
    # "https://raw.githubusercontent.com/banbendalao/ADgk/master/ADgk.txt",
    # "https://raw.githubusercontent.com/hoshsadiq/adblock-nocoin-list/master/nocoin.txt",
    # "https://anti-ad.net/adguard.txt",
    "https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/AWAvenue-Ads-Rule.txt",
    "https://raw.githubusercontent.com/d3ward/toolz/master/src/d3host.adblock",
    # "https://raw.githubusercontent.com/Cats-Team/AdRules/main/dns.txt",
    # "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/light.txt",
    # "https://raw.githubusercontent.com/uniartisan/adblock_list/master/adblock_lite.txt",
    "https://raw.githubusercontent.com/afwfv/DD-AD/main/rule/DD-AD.txt",
    # "https://raw.githubusercontent.com/afwfv/DD-AD/main/rule/domain.txt",
)

ABFWHITE = (
    "https://raw.githubusercontent.com/privacy-protection-tools/dead-horse/master/anti-ad-white-list.txt",
    "file:///abpwhite.txt",
)

FAKE_IPS = "8.8.8.8; 8.8.4.4; 4.2.2.2; 4.2.2.1; 114.114.114.114; 127.0.0.1; 0.0.0.0".split('; ')
FAKE_DOMAINS = ".google.com .github.com".split()

FETCH_TIMEOUT = (6, 5)

BANNED_WORDS = b64decodes('5rOV6L2uIOi9ruWtkCDova4g57uDIOawlCDlip8gb25ndGFpd2Fu').split()

# !!! JUST FOR DEBUGING !!!
DEBUG_NO_NODES = os.path.exists("local_NO_NODES")
DEBUG_NO_DYNAMIC = os.path.exists("local_NO_DYNAMIC")
DEBUG_NO_ADBLOCK = os.path.exists("local_NO_ADBLOCK")

STOP = False
# 节点存活预检：写出订阅前对每个 (server, port) 做 TCP 连通测试，剔除端口不可达的死节点
# 本地调试可创建 local_NO_PRECHECK 文件关闭
PRECHECK = not os.path.exists("local_NO_PRECHECK")
PRECHECK_TIMEOUT = 2.5   # 单地址超时（秒）
PRECHECK_WORKERS = 150   # 并发线程数
STOP_FAKE_NODES = """vmess://ew0KICAidiI6ICIyIiwNCiAgInBzIjogIlx1NUU4Nlx1Nzk1RFx1NEU5QVx1NTFBQ1x1NEYxQVx1ODBEQ1x1NTIyOVx1NTNFQ1x1NUYwMCIsDQogICJhZGQiOiAid2ViLjUxLmxhIiwNCiAgInBvcnQiOiAiNDQzIiwNCiAgImlkIjogIjg4ODg4ODg4LTg4ODgtODg4OC04ODg4LTg4ODg4ODg4ODg4OCIsDQogICJhaWQiOiAiMCIsDQogICJzY3kiOiAiYXV0byIsDQogICJuZXQiOiAidGNwIiwNCiAgInR5cGUiOiAiaHR0cCIsDQogICJob3N0IjogIndlYi41MS5sYSIsDQogICJwYXRoIjogIi9pbWFnZXMvaW5kZXgvc2VydmljZS1waWMucG5nIiwNCiAgInRscyI6ICJ0bHMiLA0KICAic25pIjogIndlYi41MS5sYSIsDQogICJhbHBuIjogImh0dHAvMS4xIiwNCiAgImZwIjogImNocm9tZSINCn0=
vmess://ew0KICAidiI6ICIyIiwNCiAgInBzIjogIlx1NjU0Rlx1NjExRlx1NjVGNlx1NjcxRlx1RkYwQ1x1NjZGNFx1NjVCMFx1NjY4Mlx1NTA1QyIsDQogICJhZGQiOiAid2ViLjUxLmxhIiwNCiAgInBvcnQiOiAiNDQzIiwNCiAgImlkIjogImM2ZTg0MDcyLTJlNjktNDkyOC05MGFmLTQzNmIzZmNkMDY2MyIsDQogICJhaWQiOiAiMCIsDQogICJzY3kiOiAiYXV0byIsDQogICJuZXQiOiAidGNwIiwNCiAgInR5cGUiOiAiaHR0cCIsDQogICJob3N0IjogIndlYi41MS5sYSIsDQogICJwYXRoIjogIi9pbWFnZXMvaW5kZXgvc2VydmljZS1waWMucG5nIiwNCiAgInRscyI6ICJ0bHMiLA0KICAic25pIjogIndlYi41MS5sYSIsDQogICJhbHBuIjogImh0dHAvMS4xIiwNCiAgImZwIjogImNocm9tZSINCn0=
vmess://ew0KICAidiI6ICIyIiwNCiAgInBzIjogIlx1NTk4Mlx1NjcwOVx1OTcwMFx1ODk4MVx1RkYwQ1x1ODFFQVx1ODg0Q1x1NjQyRFx1NUVGQSIsDQogICJhZGQiOiAid2ViLjUxLmxhIiwNCiAgInBvcnQiOiAiNDQzIiwNCiAgImlkIjogImUwYzZiM2I3LTlmNWItNGJkNi05YWJmLTI2MDY2M2FhNGYxYiIsDQogICJhaWQiOiAiMCIsDQogICJzY3kiOiAiYXV0byIsDQogICJuZXQiOiAidGNwIiwNCiAgInR5cGUiOiAiaHR0cCIsDQogICJob3N0IjogIndlYi41MS5sYSIsDQogICJwYXRoIjogIi9pbWFnZXMvaW5kZXgvc2VydmljZS1waWMucG5nIiwNCiAgInRscyI6ICJ0bHMiLA0KICAic25pIjogIndlYi41MS5sYSIsDQogICJhbHBuIjogImh0dHAvMS4xIiwNCiAgImZwIjogImNocm9tZSINCn0=
"""

class UnsupportedType(Exception): pass
class NotANode(Exception): pass

session = requests.Session()
session.trust_env = False
if PROXY: session.proxies = {'http': PROXY, 'https': PROXY}
session.headers["User-Agent"] = 'Mozilla/5.0 (X11; Linux x86_64) Clash-verge/v2.0.3 AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.58'
session.mount('file://', FileAdapter())
    
exc_queue: List[str] = []

d = datetime.datetime.now()
if STOP or (d.month, d.day) in ((6, 4), (7, 1), (10, 1)):
    DEBUG_NO_NODES = DEBUG_NO_DYNAMIC = STOP = True

class Node:
    names: Set[str] = set()
    DATA_TYPE = Dict[str, Any]

    def __init__(self, data: Union[DATA_TYPE, str]) -> None:
        if isinstance(data, dict):
            self.data: __class__.DATA_TYPE = data
            self.type = data['type']
        elif isinstance(data, str):
            self.load_url(data)
        else: raise TypeError(f"Got {type(data)}")
        if not self.data['name']:
            self.data['name'] = "未命名"
        if 'password' in self.data:
            self.data['password'] = str(self.data['password'])
        self.data['type'] = self.type
        self.normalize_data()
        self.name: str = self.data['name']

    def normalize_data(self) -> None:
        """Normalize fields that differ between old Clash YAML and current cores."""
        data = self.data

        for key in ('port', 'alterId'):
            if key in data:
                try:
                    data[key] = int(str(data[key]).strip())
                except (TypeError, ValueError):
                    pass

        for key in ('tls', 'skip-cert-verify', 'udp'):
            if key not in data or isinstance(data[key], bool):
                continue
            if isinstance(data[key], int):
                data[key] = bool(data[key])
            elif isinstance(data[key], str):
                value = data[key].strip().lower()
                if value in ('1', 'true', 'yes', 'on', 'tls'):
                    data[key] = True
                elif value in ('0', 'false', 'no', 'off', ''):
                    data[key] = False

        if self.type == 'vmess':
            if data.get('network') == 'ws':
                opts = data.get('ws-opts', {})
                if not isinstance(opts, dict):
                    opts = {}

                # Some upstream files still use the pre-Meta ws-headers/ws-path layout.
                old_headers = data.pop('ws-headers', {})
                if isinstance(old_headers, dict):
                    host = old_headers.get('Host', old_headers.get('host'))
                    if host:
                        opts.setdefault('headers', {})['Host'] = host

                old_path = data.pop('ws-path', None)
                if old_path:
                    opts['path'] = old_path
                opts.setdefault('path', '/')

                headers = opts.get('headers', {})
                if not headers.get('Host'):
                    headers['Host'] = str(data.get('servername') or data.get('server') or '')
                opts['headers'] = headers
                data['ws-opts'] = opts
            else:
                data.pop('ws-headers', None)
                data.pop('ws-path', None)

        # Hysteria2 is always TLS based; its schema does not use a tls switch.
        if self.type == 'hysteria2':
            data.pop('tls', None)

    def __str__(self):
        return self.url

    def __hash__(self):
        data = self.data
        try:
            path = ""
            if self.type == 'vmess':
                net: str = data.get('network', '')
                path = net+':'
                if not net: pass
                elif net == 'ws':
                    opts: Dict[str, Any] = data.get('ws-opts', {})
                    path += opts.get('headers', {}).get('Host', '')
                    path += '/'+opts.get('path', '')
                elif net == 'h2':
                    opts: Dict[str, Any] = data.get('h2-opts', {})
                    path += ','.join(opts.get('host', []))
                    path += '/'+opts.get('path', '')
                elif net == 'grpc':
                    path += data.get('grpc-opts', {}).get('grpc-service-name','')
            elif self.type == 'ss':
                opts: Dict[str, Any] = data.get('plugin-opts', {})
                path = opts.get('host', '')
                path += '/'+opts.get('path', '')
            elif self.type == 'ssr':
                path = data.get('obfs-param', '')
            elif self.type == 'trojan':
                path = data.get('sni', '')+':'
                net: str = data.get('network', '')
                if not net: pass
                elif net == 'ws':
                    opts: Dict[str, Any] = data.get('ws-opts', {})
                    path += opts.get('headers', {}).get('Host', '')
                    path += '/'+opts.get('path', '')
                elif net == 'grpc':
                    path += data.get('grpc-opts', {}).get('grpc-service-name','')
            elif self.type == 'vless':
                path = data.get('sni', '')+':'
                net: str = data.get('network', '')
                if not net: pass
                elif net == 'ws':
                    opts: Dict[str, Any] = data.get('ws-opts', {})
                    path += opts.get('headers', {}).get('Host', '')
                    path += '/'+opts.get('path', '')
                elif net == 'grpc':
                    path += data.get('grpc-opts', {}).get('grpc-service-name','')
            elif self.type == 'hysteria2':
                path = data.get('sni', '')+':'
                path += data.get('obfs-password', '')+':'
                # print(self.url)
                # return hash(self.url)
            path += '@'+','.join(data.get('alpn', []))+'@'+data.get('password', '')+data.get('uuid', '')
            hashstr = f"{self.type}:{data['server']}:{data['port']}:{path}"
            return hash(hashstr)
        except Exception:
            print("节点 Hash 计算失败！", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return hash('__ERROR__')
    
    def __eq__(self, other: Union['Node', Any]):
        if isinstance(other, self.__class__):
            return hash(self) == hash(other)
        else:
            return False

    def load_url(self, url: str) -> None:
        try: self.type, dt = url.split("://", 1)
        except ValueError: raise NotANode(url)
        # === Fix begin ===
        if not self.type.isascii():
            self.type = ''.join([_ for _ in self.type if _.isascii()])
            url = self.type+'://'+url.split("://")[1]
        if self.type == 'hy2': self.type = 'hysteria2'
        # === Fix end ===
        if self.type == 'vmess':
            v = VMESS_EXAMPLE.copy()
            try: v.update(json.loads(b64decodes(dt)))
            except Exception:
                raise UnsupportedType('vmess', 'SP')
            self.data = {}
            for key, val in v.items():
                if key in VMESS2CLASH:
                    self.data[VMESS2CLASH[key]] = val
            self.data['tls'] = (v['tls'] == 'tls')
            self.data['alterId'] = int(self.data['alterId'])
            if v['net'] == 'ws':
                opts = {}
                if 'path' in v:
                    opts['path'] = v['path']
                if 'host' in v:
                    opts['headers'] = {'Host': v['host']}
                self.data['ws-opts'] = opts
            elif v['net'] == 'h2':
                opts = {}
                if 'path' in v:
                    opts['path'] = v['path']
                if 'host' in v:
                    opts['host'] = v['host'].split(',')
                self.data['h2-opts'] = opts
            elif v['net'] == 'grpc' and 'path' in v:
                self.data['grpc-opts'] = {'grpc-service-name': v['path']}

        elif self.type == 'ss':
            info = url.split('@')
            srvname = info.pop()
            if '#' in srvname:
                srv, name = srvname.split('#')
            else:
                srv = srvname
                name = ''
            server, port = srv.split(':')
            try:
                port = int(port)
            except ValueError:
                raise UnsupportedType('ss', 'SP')
            info = '@'.join(info)
            if not ':' in info:
                info = b64decodes_safe(info)
            if ':' in info:
                cipher, passwd = info.split(':')
            else:
                cipher = info
                passwd = ''
            self.data = {'name': unquote(name), 'server': server, 
                    'port': port, 'type': 'ss', 'password': passwd, 'cipher': cipher}

        elif self.type == 'ssr':
            if '?' in url:
                parts = dt.split(':')
            else:
                parts = b64decodes_safe(dt).split(':')
            try:
                passwd, info = parts[-1].split('/?')
            except: raise
            passwd = b64decodes_safe(passwd)
            self.data = {'type': 'ssr', 'server': parts[0], 'port': parts[1],
                    'protocol': parts[2], 'cipher': parts[3], 'obfs': parts[4],
                    'password': passwd, 'name': ''}
            for kv in info.split('&'):
                k_v = kv.split('=')
                if len(k_v) != 2:
                    k = k_v[0]
                    v = ''
                else: k,v = k_v
                if k == 'remarks':
                    self.data['name'] = v
                elif k == 'group':
                    self.data['group'] = v
                elif k == 'obfsparam':
                    self.data['obfs-param'] = v
                elif k == 'protoparam':
                    self.data['protocol-param'] = v

        elif self.type == 'trojan':
            parsed = urlparse(url)
            self.data = {'name': unquote(parsed.fragment), 'server': parsed.hostname, 
                    'port': parsed.port, 'type': 'trojan', 'password': unquote(parsed.username)} # type: ignore
            if parsed.query:
                for kv in parsed.query.split('&'):
                    k,v = kv.split('=',1)
                    if k in ('allowInsecure', 'insecure'):
                        self.data['skip-cert-verify'] = (v != '0')
                    elif k == 'sni': self.data['sni'] = v
                    elif k == 'alpn':
                        self.data['alpn'] = unquote(v).split(',')
                    elif k == 'type':
                        self.data['network'] = v
                    elif k == 'serviceName':
                        if 'grpc-opts' not in self.data:
                            self.data['grpc-opts'] = {}
                        self.data['grpc-opts']['grpc-service-name'] = v
                    elif k == 'host':
                        if 'ws-opts' not in self.data:
                            self.data['ws-opts'] = {}
                        if 'headers' not in self.data['ws-opts']:
                            self.data['ws-opts']['headers'] = {}
                        self.data['ws-opts']['headers']['Host'] = v
                    elif k == 'path':
                        if 'ws-opts' not in self.data:
                            self.data['ws-opts'] = {}
                        self.data['ws-opts']['path'] = v

        elif self.type == 'vless':
            parsed = urlparse(url)
            self.data = {'name': unquote(parsed.fragment), 'server': parsed.hostname, 
                    'port': parsed.port, 'type': 'vless', 'uuid': unquote(parsed.username)} # type: ignore
            self.data['tls'] = False
            if parsed.query:
                for kv in parsed.query.split('&'):
                    k,v = kv.split('=',1)
                    if k in ('allowInsecure', 'insecure'):
                        self.data['skip-cert-verify'] = (v != '0')
                    elif k == 'sni': self.data['servername'] = v
                    elif k == 'alpn':
                        self.data['alpn'] = unquote(v).split(',')
                    elif k == 'type':
                        self.data['network'] = v
                    elif k == 'serviceName':
                        if 'grpc-opts' not in self.data:
                            self.data['grpc-opts'] = {}
                        self.data['grpc-opts']['grpc-service-name'] = v
                    elif k == 'host':
                        if 'ws-opts' not in self.data:
                            self.data['ws-opts'] = {}
                        if 'headers' not in self.data['ws-opts']:
                            self.data['ws-opts']['headers'] = {}
                        self.data['ws-opts']['headers']['Host'] = v
                    elif k == 'path':
                        if 'ws-opts' not in self.data:
                            self.data['ws-opts'] = {}
                        self.data['ws-opts']['path'] = v
                    elif k == 'flow':
                        if v.endswith('-udp443'):
                            self.data['flow'] = v
                        else: self.data['flow'] = v+'!'
                    elif k == 'fp': self.data['client-fingerprint'] = v
                    elif k == 'security' and v == 'tls':
                        self.data['tls'] = True
                    elif k == 'pbk':
                        if 'reality-opts' not in self.data:
                            self.data['reality-opts'] = {}
                        self.data['reality-opts']['public-key'] = v
                    elif k == 'sid':
                        if 'reality-opts' not in self.data:
                            self.data['reality-opts'] = {}
                        self.data['reality-opts']['short-id'] = v
                    # TODO: Unused key encryption

        elif self.type == 'hysteria2':
            parsed = urlparse(url)
            self.data = {'name': unquote(parsed.fragment), 'server': parsed.hostname, 
                    'type': 'hysteria2', 'password': unquote(parsed.username)} # type: ignore
            if ':' in parsed.netloc:
                ports = parsed.netloc.split(':')[1]
                if ',' in ports:
                    self.data['port'], self.data['ports'] = ports.split(',',1)
                else:
                    self.data['port'] = ports
                try: self.data['port'] = int(self.data['port'])
                except ValueError: self.data['port'] = 443
            else:
                self.data['port'] = 443
            self.data['tls'] = False
            if parsed.query:
                k = v = ''
                for kv in parsed.query.split('&'):
                    if '=' in kv:
                        k,v = kv.split('=',1)
                    else:
                        v += '&' + kv
                    if k == 'insecure':
                        self.data['skip-cert-verify'] = (v != '0')
                    elif k == 'alpn':
                        self.data['alpn'] = unquote(v).split(',')
                    elif k in ('sni', 'obfs', 'obfs-password'):
                        self.data[k] = v
                    elif k == 'fp': self.data['fingerprint'] = v
        
        else: raise UnsupportedType(self.type)

    def format_name(self, max_len=30) -> None:
        self.data['name'] = self.name
        for word in BANNED_WORDS:
            self.data['name'] = self.data['name'].replace(word, '*'*len(word))
        if len(self.data['name']) > max_len:
            self.data['name'] = self.data['name'][:max_len]+'...'
        if self.data['name'] in Node.names:
            i = 0
            new: str = self.data['name']
            while new in Node.names:
                i += 1
                new = f"{self.data['name']} #{i}"
            self.data['name'] = new
        
    @property
    def isfake(self) -> bool:
        try:
            if 'server' not in self.data: return True
            if '.' not in (self.data['server'] or ''): return True
            if self.data['server'] in FAKE_IPS: return True
            if int(str(self.data['port'])) < 20: return True
            for domain in FAKE_DOMAINS:
                if self.data['server'] == domain.lstrip('.'): return True
                if self.data['server'].endswith(domain): return True
            # TODO: Fake UUID
            # if self.type == 'vmess' and len(self.data['uuid']) != len(DEFAULT_UUID):
            #     return True
            if 'sni' in self.data and 'google.com' in self.data['sni'].lower():
                # That's not designed for China
                self.data['sni'] = 'www.bing.com'
        except Exception:
            print("无法验证的节点！", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return False

    @property
    def url(self) -> str:
        data = self.data
        if self.type == 'vmess':
            v = VMESS_EXAMPLE.copy()
            for key,val in data.items():
                if key in CLASH2VMESS:
                    v[CLASH2VMESS[key]] = val
            if v['net'] == 'ws':
                if 'ws-opts' in data:
                    try:
                        v['host'] = data['ws-opts']['headers']['Host']
                    except KeyError: pass
                    if 'path' in data['ws-opts']:
                        v['path'] = data['ws-opts']['path']
            elif v['net'] == 'h2':
                if 'h2-opts' in data:
                    if 'host' in data['h2-opts']:
                        v['host'] = ','.join(data['h2-opts']['host'])
                    if 'path' in data['h2-opts']:
                        v['path'] = data['h2-opts']['path']
            elif v['net'] == 'grpc':
                if 'grpc-opts' in data:
                    if 'grpc-service-name' in data['grpc-opts']:
                        v['path'] = data['grpc-opts']['grpc-service-name']
            if ('tls' in data) and data['tls']:
                v['tls'] = 'tls'
            return 'vmess://'+b64encodes(json.dumps(v, ensure_ascii=False))

        if self.type == 'ss':
            passwd = b64encodes_safe(data['cipher']+':'+data['password'])
            return f"ss://{passwd}@{data['server']}:{data['port']}#{quote(data['name'])}"
        if self.type == 'ssr':
            ret = (':'.join([str(self.data[_]) for _ in ('server','port',
                                        'protocol','cipher','obfs')]) +
                    b64encodes_safe(self.data['password']) +
                    f"/?remarks={b64encodes_safe(self.data['name'])}")
            for k, urlk in (('obfs-param','obfsparam'), ('protocol-param','protoparam'), ('group','group')):
                if k in self.data:
                    ret += '&'+urlk+'='+b64encodes_safe(self.data[k])
            return "ssr://"+ret

        if self.type == 'trojan':
            passwd = quote(data['password'])
            name = quote(data['name'])
            ret = f"trojan://{passwd}@{data['server']}:{data['port']}?"
            if 'skip-cert-verify' in data:
                ret += f"allowInsecure={int(data['skip-cert-verify'])}&"
            if 'sni' in data:
                ret += f"sni={data['sni']}&"
            if 'alpn' in data:
                ret += f"alpn={quote(','.join(data['alpn']))}&"
            if 'network' in data:
                if data['network'] == 'grpc':
                    grpc_name = data.get('grpc-opts', {}).get('grpc-service-name', '')
                    ret += f"type=grpc&serviceName={quote(str(grpc_name))}&"
                elif data['network'] == 'ws':
                    ret += f"type=ws&"
                    if 'ws-opts' in data:
                        try:
                            ret += f"host={data['ws-opts']['headers']['Host']}&"
                        except KeyError: pass
                        if 'path' in data['ws-opts']:
                            ret += f"path={data['ws-opts']['path']}"
            ret = ret.rstrip('&')+'#'+name
            return ret

        if self.type == 'vless':
            passwd = quote(data['uuid'])
            name = quote(data['name'])
            ret = f"vless://{passwd}@{data['server']}:{data['port']}?"
            if 'skip-cert-verify' in data:
                ret += f"allowInsecure={int(data['skip-cert-verify'])}&"
            if 'servername' in data:
                ret += f"sni={data['servername']}&"
            if 'alpn' in data:
                ret += f"alpn={quote(','.join(data['alpn']))}&"
            if 'network' in data:
                if data['network'] == 'grpc':
                    grpc_name = data.get('grpc-opts', {}).get('grpc-service-name', '')
                    ret += f"type=grpc&serviceName={quote(str(grpc_name))}&"
                elif data['network'] == 'ws':
                    ret += f"type=ws&"
                    if 'ws-opts' in data:
                        try:
                            ret += f"host={data['ws-opts']['headers']['Host']}&"
                        except KeyError: pass
                        if 'path' in data['ws-opts']:
                            ret += f"path={data['ws-opts']['path']}"
            if 'flow' in data:
                flow: str = data['flow']
                if flow.endswith('!'):
                    ret += f"flow={flow[:-1]}&"
                else: ret += f"flow={flow}-udp443&"
            if 'client-fingerprint' in data:
                ret += f"fp={data['client-fingerprint']}&"
            if 'tls' in data and data['tls']:
                ret += f"security=tls&"
            elif 'reality-opts' in data:
                opts: Dict[str, str] = data['reality-opts']
                ret += f"security=reality&pbk={opts.get('public-key','')}&sid={opts.get('short-id','')}&"
            ret = ret.rstrip('&')+'#'+name
            return ret

        if self.type == 'hysteria2':
            passwd = quote(data['password'])
            name = quote(data['name'])
            ret = f"hysteria2://{passwd}@{data['server']}:{data['port']}"
            if 'ports' in data:
                ret += ','+data['ports']
            ret += '?'
            if 'skip-cert-verify' in data:
                ret += f"insecure={int(data['skip-cert-verify'])}&"
            if 'alpn' in data:
                ret += f"alpn={quote(','.join(data['alpn']))}&"
            if 'fingerprint' in data:
                ret += f"fp={data['fingerprint']}&"
            for k in ('sni', 'obfs', 'obfs-password'):
                if k in data:
                    ret += f"{k}={data[k]}&"
            ret = ret.rstrip('&')+'#'+name
            return ret

        if self.type in ('http', 'socks5'):
            username = data.get('username')
            password = data.get('password')
            if username is not None:
                auth = quote(str(username))
                if password is not None:
                    auth += ':'+quote(str(password))
                ret = f"{self.type}://{auth}@{data['server']}:{data['port']}"
            else:
                ret = f"{self.type}://{data['server']}:{data['port']}"
            return ret+f"#{quote(data['name'])}"

        raise UnsupportedType(self.type)

    @property
    def clash_data(self) -> DATA_TYPE:
        ret = self.data.copy()
        if 'password' in ret and ret['password'].isdigit():
            ret['password'] = '!!str '+ret['password']
        if 'uuid' in ret and len(ret['uuid']) != len(DEFAULT_UUID):
            ret['uuid'] = DEFAULT_UUID
        if 'group' in ret: del ret['group']
        if 'cipher' in ret and not ret['cipher']:
            ret['cipher'] = 'auto'
        if 'fingerprint' in ret:
            # 新版 mihomo 已把 fingerprint 更名为 client-fingerprint
            ret.setdefault('client-fingerprint', ret['fingerprint'])
            del ret['fingerprint']
        if self.type == 'vless' and ret.get('flow'):
            if ret['flow'].endswith('-udp443'):
                ret['flow'] = ret['flow'][:-7]
            elif ret['flow'].endswith('!'):
                ret['flow'] = ret['flow'][:-1]
        elif self.type == 'vless' and 'flow' in ret and not ret['flow']:
            del ret['flow'] # flow 为 null/空时删除，避免 mihomo 校验报错
        if 'reality-opts' in ret and not ret.get('tls'):
            ret['tls'] = True # REALITY 必须启用 TLS，部分上游订阅漏写该字段
        if self.type == 'hysteria2' and ret.get('obfs') in (None, '', 'none'):
            ret.pop('obfs', None) # obfs 为 none 视为不启用，避免 mihomo 报 missing obfs password
        if 'alpn' in ret and isinstance(ret['alpn'], str):
            # 'alpn' is not a slice
            ret['alpn'] = ret['alpn'].replace(' ','').split(',')
        return ret

    def supports_meta(self, noMeta=False) -> bool:
        if self.isfake: return False
        # http/socks5 公开代理不再一刀切丢弃：实测约 39% 从中国可用（延迟 P50≈200ms），
        # 可用性由中国探针真实测活判定。用户已确认接受明文/开放代理的隐私权衡。
        if self.type == 'vmess':
            if 'client-fingerprint' in self.data and str(self.data['client-fingerprint']).strip():
                supported = CLASH_CIPHER_VMESS + ['x-chacha20']
            else:
                supported = CLASH_CIPHER_VMESS
        elif self.type == 'ss' or self.type == 'ssr':
            supported = CLASH_CIPHER_SS
        elif self.type == 'trojan': return True
        elif noMeta: return False
        else: return True
        if 'network' in self.data and self.data['network'] in ('h2','grpc'):
            # A quick fix for #2
            self.data['tls'] = True
        if 'cipher' not in self.data: return False # 新版 mihomo 要求显式 cipher，缺失则丢弃节点
        if not self.data['cipher']: return False
        if self.data['cipher'] not in supported: return False
        try:
            if self.type == 'ssr':
                if 'obfs' in self.data and self.data['obfs'] not in CLASH_SSR_OBFS:
                    return False
                if 'protocol' in self.data and self.data['protocol'] not in CLASH_SSR_PROTOCOL:
                    return False
                if self.data.get('obfs', 'plain') != 'plain' and not self.data.get('obfs-password'):
                    return False # 新版 mihomo 要求 obfs 必须带 password
            if 'plugin-opts' in self.data and 'mode' in self.data['plugin-opts'] \
                    and not self.data['plugin-opts']['mode']: return False
        except Exception:
            print("无法验证的 Clash 节点！", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return False
        return True
    
    def supports_clash(self, meta=False) -> bool:
        if meta: return self.supports_meta()
        if self.type == 'vless': return False
        if self.data['type'] == 'vless': return False
        return self.supports_meta(noMeta=True)

    def supports_ray(self) -> bool:
        if self.isfake: return False
        # if self.type == 'ss':
        #     if 'plugin' in self.data and self.data['plugin']: return False
        # elif self.type == 'ssr':
        #     return False
        return True

class Source():
    @no_type_check
    def __init__(self, url: Union[str, function]) -> None:
        if isinstance(url, function):
            self.url: str = "dynamic://"+url.__name__
            self.url_source: function = url
        elif url.startswith('+'):
            self.url_source: str = url
            self.date = datetime.datetime.now()# + datetime.timedelta(days=1)
            self.gen_url()
        else:
            self.url: str = url
            self.url_source: None = None
        self.content: Union[str, List[str], int] = None
        self.sub: Union[List[str], List[Dict[str, str]]] = None
        self.cfg: Dict[str, Any] = {}
        self.local_result: Tuple[Dict[int, 'Node'], Set[str]] = ({}, set())

    def gen_url(self) -> None:
        self.url_source: str
        tags = self.url_source.split()
        url = tags.pop()
        while tags:
            tag = tags.pop(0)
            if tag[0] != '+': break
            if tag == '+date':
                url = self.date.strftime(url)
                self.date -= datetime.timedelta(days=1)
        self.url = url

    @no_type_check
    def get(self, depth=2) -> None:
        global exc_queue
        if self.content: return
        try:
            if self.url.startswith("dynamic:"):
                self.content: Union[str, List[str]] = self.url_source()
            else:
                global session
                if '#' in self.url:
                    segs = self.url.split('#')
                    self.cfg = dict([_.split('=',1) for _ in segs[-1].split('&')])
                    if 'max' in self.cfg:
                        try:
                            self.cfg['max'] = int(self.cfg['max'])
                        except ValueError:
                            exc_queue.append("最大节点数限制不是整数！")
                            del self.cfg['max']
                    if 'ignore' in self.cfg:
                        self.cfg['ignore'] = [_ for _ in self.cfg['ignore'].split(',') if _.strip()]
                    self.url = '#'.join(segs[:-1])
                with session.get(self.url, stream=True) as r:
                    if r.status_code != 200:
                        if depth > 0 and isinstance(self.url_source, str):
                            exc = f"'{self.url}' 抓取时 {r.status_code}"
                            self.gen_url()
                            exc += "，重新生成链接：\n\t"+self.url
                            exc_queue.append(exc)
                            self.get(depth-1)
                        else:
                            self.content = r.status_code
                        return
                    self.content = self._download(r)
        except KeyboardInterrupt: raise
        except requests.exceptions.RequestException:
            self.content = -1
        except:
            self.content = -2
            exc = "在抓取 '"+self.url+"' 时发生错误：\n"+traceback.format_exc()
            exc_queue.append(exc)
        else:
            self.parse()
            # 节点解析（重计算）随下载在各抓取线程内并行完成，主线程只按序注册
            try:
                self.local_result = merge_local(self)
            except KeyboardInterrupt: raise
            except: traceback.print_exc()

    def _download(self, r: requests.Response) -> str:
        content: str = ""
        tp = None
        pending = None
        early_stop = False
        for chunk in r.iter_content():
            if early_stop: pending = None; break
            chunk: bytes
            if pending is not None:
                chunk = pending + chunk
                pending = None
            if tp == 'sub':
                content += chunk.decode(errors='ignore')
                continue
            lines: List[bytes] = chunk.splitlines()
            if lines and lines[-1] and chunk and lines[-1][-1] == chunk[-1]:
                pending = lines.pop()
            while lines:
                line = lines.pop(0).rstrip().decode(errors='ignore').replace('\\r','')
                if not line: continue
                if not tp:
                    if ': ' in line or line.endswith(':'):
                        kv = line.split(':', 1)
                        key = kv[0]
                        # YAML 顶层键允许字母/数字/连字符/下划线（如 allow-lan、mixed-port）；
                        # 旧逻辑 kv[0].isalpha() 会把含连字符的键误判为 sub，导致整个配置解析为 0 节点
                        if key and key[0].isalpha() and all(c.isalnum() or c in '-_' for c in key):
                            tp = 'yaml'
                    elif line[0] == '#': pass
                    else: tp = 'sub'
                if tp == 'yaml':
                    if content:
                        if line in ("proxy-groups:", "rules:", "script:"):
                            early_stop=True; break
                        content += line+'\n'
                    elif line == "proxies:":
                        content = line+'\n'
                elif tp == 'sub':
                    content = chunk.decode(errors='ignore')
        if pending is not None: content += pending.decode(errors='ignore')
        return content

    def parse(self) -> None:
        global exc_queue
        try:
            text = self.content
            if isinstance(text, str):
                if "proxies:" in text:
                    # Clash config
                    config = yaml.full_load(text.replace("!<str>","!!str"))
                    sub = config['proxies']
                elif '://' in text:
                    # V2Ray raw list
                    sub = text.strip().splitlines()
                else:
                    # V2Ray Sub
                    sub = b64decodes(text.strip()).strip().splitlines()
            else: sub = text # 动态节点抓取后直接传入列表

            if 'max' in self.cfg and len(sub) > self.cfg['max']:
                exc_queue.append(f"此订阅有 {len(sub)} 个节点，最大限制为 {self.cfg['max']} 个，忽略此订阅。")
                self.sub = []
            elif sub and 'ignore' in self.cfg:
                if isinstance(sub[0], str):
                    self.sub = [_ for _ in sub if _.split('://', 1)[0] not in self.cfg['ignore']]
                elif isinstance(sub[0], dict):
                    self.sub = [_ for _ in sub if _.get('type', '') not in self.cfg['ignore']] #type:ignore
                else: self.sub = sub
            else: self.sub = sub
        except KeyboardInterrupt: raise
        except: exc_queue.append(
                "在解析 '"+self.url+"' 时发生错误：\n"+traceback.format_exc())

class DomainTree:
    def __init__(self) -> None:
        self.children: Dict[str, __class__] = {}
        self.here: bool = False

    def insert(self, domain: str) -> None:
        segs = domain.split('.')
        segs.reverse()
        self._insert(segs)

    def _insert(self, segs: List[str]) -> None:
        if not segs:
            self.here = True
            return
        if segs[0] not in self.children:
            self.children[segs[0]] = __class__()
        child = self.children[segs[0]]
        del segs[0]
        child._insert(segs)

    def remove(self, domain: str) -> None:
        segs = domain.split('.')
        segs.reverse()
        self._remove(segs)

    def _remove(self, segs: List[str]) -> None:
        self.here = False
        if not segs:
            self.children.clear()
            return
        if segs[0] in self.children:
            child = self.children[segs[0]]
            del segs[0]
            child._remove(segs)

    def get(self) -> List[str]:
        ret: List[str] = []
        for name, child in self.children.items():
            if child.here: ret.append(name)
            else: ret.extend([_+'.'+name for _ in child.get()])
        return ret

def extract(url: str) -> Union[Set[str], int]:
    global session
    res = session.get(url)
    if res.status_code != 200: return res.status_code
    urls: Set[str] = set()
    if '#' in url:
        mark = '#'+url.split('#', 1)[1]
    else:
        mark = ''
    for line in res.text.strip().splitlines():
        if line.startswith("http"):
            urls.add(line+mark)
    return urls

merged: Dict[int, Node] = {}
unknown: Set[str] = set()
used: Dict[int, Dict[int, str]] = {}

def merge_local(source_obj: Source):
    """纯解析（无全局副作用）：把已抓取的源解析为本地节点字典，供各抓取线程并行调用。
    返回 (nodes 有序字典 {hash: Node}, unknown 集合)。不做名字去重注册。"""
    nodes: Dict[int, Node] = {}
    unk: Set[str] = set()
    sub = source_obj.sub
    if not sub: return nodes, unk
    for p in sub:
        if isinstance(p, str) and '://' not in p: continue
        try: n = Node(p)
        except KeyboardInterrupt: raise
        except UnsupportedType as e:
            if len(e.args) == 1:
                print(f"不支持的类型：{e}")
            unk.add(p) # type: ignore
        except: traceback.print_exc()
        else:
            hashn = hash(n)
            if hashn not in nodes:
                nodes[hashn] = n
            else:
                nodes[hashn].data.update(n.data)
    return nodes, unk

def register_local(source_obj: Source, sourceId=-1) -> None:
    """把 merge_local 的本地结果按源序号注册进全局字典（主线程串行调用，
    保证名字去重与多源合并顺序与串行版完全一致）。"""
    global merged, unknown
    if not source_obj.sub: print("空订阅，跳过！", end='', flush=True); return
    nodes, unk = source_obj.local_result
    unknown.update(unk)
    for hashn, n in nodes.items():
        n.format_name()
        Node.names.add(n.data['name'])
        if hashn not in merged:
            merged[hashn] = n
        else:
            merged[hashn].data.update(n.data)
        if hashn not in used:
            used[hashn] = {}
        used[hashn][sourceId] = n.name

def raw2fastly(url: str) -> str:
    if not LOCAL: return url
    url: Union[str, List[str]]
    if url.startswith("https://raw.githubusercontent.com/"):
        # url = url[34:].split('/')
        # url[1] += '@'+url[2]
        # del url[2]
        # url = "https://fastly.jsdelivr.net/gh/"+('/'.join(url))
        # return url
        return "https://ghproxy.cn/"+url
    return url

def merge_adblock(adblock_name: str, rules: Dict[str, str]) -> None:
    print("正在解析 Adblock 列表... ", end='', flush=True)
    blocked: Set[str] = set()
    unblock: Set[str] = set()
    # 所有广告列表相互独立，先并行下载（仅网络 I/O 并行），再按原顺序串行解析
    def _fetch(url) -> Tuple[str, Optional[requests.Response], str]:
        url = raw2fastly(url)
        try:
            return (url, session.get(url), "")
        except requests.exceptions.RequestException as e:
            try:
                return (url, None, f"{url} 下载失败：{e.args[0].reason}")
            except Exception:
                traceback.print_exc()
                return (url, None, f"{url} 下载失败：无法解析的错误！")
    all_urls = list(ABFURLS) + list(ABFWHITE)
    results: List[Tuple[str, Optional[requests.Response], str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, max(1, len(all_urls)))) as ex:
        results = list(ex.map(_fetch, all_urls))

    for i, (url, res, err) in enumerate(results):
        is_white = i >= len(ABFURLS)
        if res is None:
            print(err)
            continue
        if res.status_code != 200:
            print(url, res.status_code)
            continue
        for line in res.text.strip().splitlines():
            line = line.strip()
            if is_white:
                if not line or line[0] == '!': continue
                else: unblock.add(line.split('^')[0].strip('|^'))
            else:
                if not line or line[0] in '!#': continue
                elif line[:2] == '@@':
                    unblock.add(line.split('^')[0].strip('@|^'))
                elif line[:2] == '||' and ('/' not in line) and ('?' not in line) and \
                                (line[-1] == '^' or line.endswith("$all")):
                    blocked.add(line.strip('al').strip('|^$'))

    domain_root = DomainTree()
    domain_keys: Set[str] = set()
    for domain in blocked:
        if '/' in domain: continue
        if '*' in domain:
            domain = domain.strip('*')
            if '*' not in domain:
                domain_keys.add(domain)
            continue
        segs = domain.split('.')
        if len(segs) == 4 and domain.replace('.','').isdigit(): # IP
            for seg in segs: # '223.73.212.020' is not valid
                if not seg: break
                if seg[0] == '0' and seg != '0': break
            else:
                rules[f'IP-CIDR,{domain}/32'] = adblock_name
        else:
            domain_root.insert(domain)
    for domain in unblock:
        domain_root.remove(domain)

    for domain in domain_keys:
        rules[f'DOMAIN-KEYWORD,{domain}'] = adblock_name

    for domain in domain_root.get():
        for key in domain_keys:
            if key in domain: break
        else: rules[f'DOMAIN-SUFFIX,{domain}'] = adblock_name

    print(f"共有 {len(rules)} 条规则")

def precheck_alive(timeout: float = PRECHECK_TIMEOUT, workers: int = PRECHECK_WORKERS) -> int:
    """节点存活预检：对去重后的 (server, port) 地址做 TCP 连通测试，从 merged 中剔除端口不可达的死节点。
    GitHub Actions（海外 runner）与本地均可运行；本地创建 local_NO_PRECHECK 文件可关闭。
    安全阈值：若单轮剔除比例超过 85%，视为当前网络异常，放弃剔除。返回剔除的节点数。"""
    global merged
    addrs: Dict[Tuple[str, int], List[int]] = {}
    for hashn, n in merged.items():
        d = n.data
        host, port = d.get('server'), d.get('port')
        if not host or not port: continue
        try: key = (str(host), int(port))
        except (TypeError, ValueError): continue
        addrs.setdefault(key, []).append(hashn)
    if not addrs: return 0

    def test(addr) -> Tuple[Tuple[str, int], bool]:
        try:
            s = socket.create_connection(addr, timeout=timeout)
            s.close()
            return (addr, True)
        except (OSError, Exception):
            return (addr, False)

    print(f"\n正在做存活预检：{len(addrs)} 个去重地址，并发 {workers}，超时 {timeout}s ...")
    alive, dead = 0, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for addr, ok in ex.map(test, list(addrs.keys())):
            if ok: alive += 1
            else: dead.append(addr)
    to_remove = [h for addr in dead for h in addrs[addr]]
    total = len(merged)
    if total and len(to_remove) / total > 0.85:
        print(f"⚠ 预检死节点 {len(to_remove)}/{total} 超过 85%，疑似当前网络异常，本轮放弃剔除。")
        return 0
    for hashn in to_remove:
        merged.pop(hashn, None)
    print(f"预检完成：存活地址 {alive}，死地址 {len(dead)}，剔除死节点 {len(to_remove)} 个，剩余 {len(merged)} 个。")
    return len(to_remove)


# ── GeoIP 地区分类（用服务器 IP 真实归属，替代不可靠的节点名关键词匹配） ──
import ipaddress

_geoip_reader = None
_geoip_init_done = False
_geoip_dns_cache: Dict[str, Optional[str]] = {}

# CDN/anycast 前缀：这类 IP 没有固定国家（全球任播），不应硬塞进国家分组。
# 包括 MaxMind 对这些段的伪国家码（如 "CLOUDFLARE"/"FASTLY"）与真实 CDN 前缀。
_ANON_GEO_CODES = {"CLOUDFLARE", "FASTLY", "CDN", "GOOGLE", "AKAMAI", "AMAZON.COM",
                   "AMAZON.COM, INC.", "MICROSOFT", "META", "FACEBOOK"}
_ANON_IP_PREFIXES = (
    "104.16.", "104.17.", "104.18.", "104.19.", "104.20.", "104.21.", "104.22.", "104.23.",
    "104.24.", "104.25.", "104.26.", "104.27.", "104.28.", "104.29.", "104.30.", "104.31.",
    "172.64.", "172.65.", "172.66.", "172.67.", "172.68.", "172.69.", "172.70.", "172.71.",
    "173.245.", "103.21.", "103.22.2", "103.31.", "141.101.", "108.162.", "190.93.",
    "188.114.", "197.234.", "198.41.", "162.158.", "162.159.", "131.0.72.",
    "45.80.110.", "45.80.111.", "66.81.24", "23.227.",
)


def _is_anon_ip(ip: str) -> bool:
    """判断 IP 是否属于 CDN/anycast 段（无固定国家归属）。"""
    return any(ip.startswith(p) for p in _ANON_IP_PREFIXES)


def _init_geoip() -> None:
    """加载 MaxMind country.mmdb（Actions 已下载到 MIHOMO_DATA 目录）。失败则静默回退名字分类。"""
    global _geoip_reader, _geoip_init_done
    if _geoip_init_done: return
    _geoip_init_done = True
    data_dir = os.environ.get("MIHOMO_DATA", "mihomo_data")
    path = os.path.join(data_dir, "country.mmdb")
    if not os.path.exists(path):
        print(f"GeoIP: 未找到 {path}，地区分类回退为名字关键词匹配")
        return
    try:
        import maxminddb
        _geoip_reader = maxminddb.open_database(path)
        print(f"GeoIP: 数据库已加载 {path}")
    except Exception as e:
        print(f"GeoIP: 加载失败（{e}），回退为名字关键词匹配")


# 中国 DoH（与国内用户视角一致，且 Actions 美国节点访问阿里 DNS 无障碍）
_DOH_URLS = [
    ("https://223.5.5.5/resolve", "name"),      # 阿里 DNS
    ("https://1.12.12.12/resolve", "name"),     # 腾讯 DNSPod
]


def _doh_resolve(server: str) -> Optional[str]:
    """通过中国 DoH 解析域名（与中国用户视角一致）。失败返回 None。"""
    for base, _ in _DOH_URLS:
        try:
            r = session.get(base, params={"type": "A", "name": server}, timeout=5)
            if r.status_code != 200: continue
            data = r.json()
            for ans in data.get("Answer", []):
                if ans.get("type") == 1:  # A 记录
                    return ans.get("data")
        except Exception:
            continue
    return None


def _resolve_node_ip(node: 'Node') -> Optional[str]:
    """取节点服务器 IP；域名依次尝试中国 DoH → 本地 DNS（带缓存）。"""
    server = str(node.data.get('server', '')).strip().strip('[]')
    if not server: return None
    try:
        return str(ipaddress.ip_address(server))
    except ValueError:
        pass
    if server in _geoip_dns_cache:
        return _geoip_dns_cache[server]
    ip = _doh_resolve(server)
    if not ip:
        try:
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(3)
            infos = socket.getaddrinfo(server, None, type=socket.SOCK_STREAM)
            socket.setdefaulttimeout(old_timeout)
            for info in infos:
                ip = info[4][0]
                break
        except Exception:
            ip = None
    _geoip_dns_cache[server] = ip
    return ip


def _warmup_dns(servers: List[str]) -> None:
    """分类前并发预热：对全部域名型节点做 DNS 解析（中国 DoH 优先），
    避免分类阶段对几千节点串行解析。"""
    domains = []
    for s in servers:
        s = str(s).strip().strip('[]')
        if not s: continue
        try:
            ipaddress.ip_address(s)
        except ValueError:
            if s not in _geoip_dns_cache:
                domains.append(s)
    if not domains: return
    # 同域名只解析一次
    uniq = sorted(set(domains))
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        futs = {ex.submit(_doh_resolve, d): d for d in uniq}
        for fut in concurrent.futures.as_completed(futs):
            d = futs[fut]
            try:
                _geoip_dns_cache[d] = fut.result()
            except Exception:
                _geoip_dns_cache[d] = None
            done += 1
            if done % 200 == 0:
                print(f"GeoIP: DNS 预热 {done}/{len(uniq)}", flush=True)
    print(f"GeoIP: DNS 预热完成，共 {len(uniq)} 个域名", flush=True)


# 地区分类专用哨兵：
#   GEO_ANON  = 节点属于 CDN/anycast（无固定国家，不应硬塞国家分组）
#   None      = GeoIP 无法判定（域名解析失败 / IP 不在库中），才允许回退名字匹配
GEO_ANON = "__ANYCAST__"


def _geo_country(node: 'Node') -> Optional[str]:
    """返回节点服务器 IP 的真实国家/地区归属。

    返回值约定：
    - 真实国家 → ISO 代码（如 "JP"/"US"/"CN"/"HK"/"CZ"），**无论是否在本项目分组配置中**；
    - CDN/anycast（无固定国家）→ GEO_ANON 哨兵；
    - 无法判定（域名解析失败 / IP 不在库）→ None（此时才允许回退名字关键词匹配）。
    """
    if _geoip_reader is None: return None
    ip = _resolve_node_ip(node)
    if not ip: return None
    if _is_anon_ip(ip): return GEO_ANON  # CDN/anycast 无固定国家
    try:
        rec = _geoip_reader.get(ip)
    except Exception:
        return None
    if isinstance(rec, dict):
        code = (rec.get('country') or {}).get('iso_code')
        if not code: return None
        code = str(code).upper()
        # MaxMind 对部分 CDN/云段返回伪国家码（如 "CLOUDFLARE"），视为无归属
        if code in _ANON_GEO_CODES: return GEO_ANON
        return code
    return None


def main():
    global exc_queue, merged, FETCH_TIMEOUT, ABFURLS, AUTOURLS, AUTOFETCH
    sources = open("sources.list", encoding="utf-8").read().strip().splitlines()
    if DEBUG_NO_NODES:
        # !!! JUST FOR DEBUGING !!!
        print("!!! 警告：您已启用无节点调试，程序产生的配置不能被直接使用 !!!")
        sources = []
    if DEBUG_NO_DYNAMIC:
        # !!! JUST FOR DEBUGING !!!
        print("!!! 警告：您已选择不抓取动态节点 !!!")
        AUTOURLS = AUTOFETCH = []
    print("正在生成动态链接...")
    # AUTOURLS 各自发起网络请求，串行会逐个等待；改为并行生成（顺序无关，只收集结果）
    _AUTO_ERR = object()
    def _run_auto(fun):
        print("正在生成 '"+fun.__name__+"'... ", end='', flush=True)
        try: return fun()
        except requests.exceptions.RequestException: print("失败！")
        except: print("错误：");traceback.print_exc()
        return _AUTO_ERR
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(AUTOURLS))) as ex:
        for url in ex.map(_run_auto, AUTOURLS):
            if url is _AUTO_ERR: continue
            if url:
                if isinstance(url, str):
                    sources.append(url)
                elif isinstance(url, (list, tuple, set)):
                    sources.extend(url)
                print("成功！")
            else: print("跳过！")
    print("正在整理链接...")
    sources_final: Union[Set[str], List[str]] = set()
    airports: Set[str] = set()
    for source in sources:
        if source == 'EOF': break
        if not source: continue
        if source[0] == '#': continue
        sub = source
        if sub[0] == '!':
            if LOCAL: continue
            sub = sub[1:]
        if sub[0] == '*':
            isairport = True
            sub = sub[1:]
        else: isairport = False
        if sub[0] == '+':
            tags = sub.split()
            sub = tags.pop()
            sub = ' '.join(tags) + ' ' +raw2fastly(sub)
        else:
            sub = raw2fastly(sub)
        if isairport: airports.add(sub)
        else: sources_final.add(sub)

    if airports:
        print("正在抓取机场列表...")
        # 各机场列表相互独立，并行下载（允许乱序打印）
        def _fetch_airport(sub) -> Union[int, Set[str], None]:
            print("合并 '"+sub+"'... ", end='', flush=True)
            try:
                res = extract(sub)
            except KeyboardInterrupt:
                return None
            except requests.exceptions.RequestException:
                print("合并失败！")
                return None
            except: traceback.print_exc(); return None
            if isinstance(res, int):
                print(res)
                return res
            print("完成！")
            return res
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(airports)))) as ex:
            for res in ex.map(_fetch_airport, list(airports)):
                if res is None: continue
                if not isinstance(res, int):
                    for url in res:
                        sources_final.add(url)

    print("正在整理链接...")
    sources_final = list(sources_final)
    sources_final.sort()
    sources_obj = [Source(url) for url in (sources_final + AUTOFETCH)]

    print("开始抓取！")
    threads = [threading.Thread(target=_.get, daemon=True) for _ in sources_obj]
    for thread in threads: thread.start()
    for i in range(len(sources_obj)):
        try:
            for t in range(1, FETCH_TIMEOUT[0]+1):
                print("抓取 '"+sources_obj[i].url+"'... ", end='', flush=True)
                try: threads[i].join(timeout=FETCH_TIMEOUT[1])
                except KeyboardInterrupt:
                    print("正在退出...")
                    FETCH_TIMEOUT = (1, 0)
                    break
                if not threads[i].is_alive(): break
                print(f"{5*t}s")
            if threads[i].is_alive():
                print("超时！")
                continue
            res = sources_obj[i].content
            if isinstance(res, int):
                if res < 0: print("抓取失败！")
                else: print(res)
            else:
                print("正在合并... ", end='', flush=True)
                try:
                    # 节点解析已在各抓取线程内并行完成（merge_local），此处只做串行注册
                    register_local(sources_obj[i], sourceId=i)
                except KeyboardInterrupt:
                    print("正在退出...")
                    break
                except:
                    print("失败！")
                    traceback.print_exc()
                else: print("完成！")
        except KeyboardInterrupt:
            print("正在退出...")
            break
        while exc_queue:
            print(exc_queue.pop(0), file=sys.stderr, flush=True)

    if STOP:
        merged = {}
        for nid, nd in enumerate(STOP_FAKE_NODES.splitlines()):
            merged[nid] = Node(nd)

    if PRECHECK:
        try:
            precheck_alive()
        except KeyboardInterrupt: raise
        except:
            exc_queue.append("存活预检出错（已跳过剔除）：\n"+traceback.format_exc())

    print("\n正在写出 V2Ray 订阅...")
    txt = ""
    unsupports = 0
    for hashp, p in merged.items():
        try:
            if hashp in used:
                # 注意：这一步也会影响到下方的 Clash 订阅，不用再执行一遍！
                p.data['name'] = ','.join([str(_) for _ in sorted(list(used[hash(p)]))])+'|'+p.data['name']
            if p.supports_ray():
                try:
                    txt += p.url + '\n'
                except UnsupportedType as e:
                    print(f"不支持的类型：{e}")
            else: unsupports += 1
        except: traceback.print_exc()
    for p in unknown:
        txt += p+'\n'
    print(f"共有 {len(merged)-unsupports} 个正常节点，{len(unknown)} 个无法解析的节点，共",
            len(merged)+len(unknown),f"个。{unsupports} 个节点不被 V2Ray 支持。")

    with open("list_raw.txt", 'w', encoding="utf-8") as f:
        f.write(txt)
    with open("list.txt", 'w', encoding="utf-8") as f:
        f.write(b64encodes(txt))
    print("写出完成！")

    with open("config.yml", encoding="utf-8") as f:
        conf: Dict[str, Any] = yaml.full_load(f)
    
    rules: Dict[str, str] = {}
    if DEBUG_NO_ADBLOCK:
        # !!! JUST FOR DEBUGING !!!
        print("!!! 警告：您已关闭对 Adblock 规则的抓取 !!!")
    else:
        merge_adblock(conf['proxy-groups'][-2]['name'], rules)

    snip_conf: Dict[str, Dict[str, Any]] = {}
    ctg_nodes: Dict[str, List[Node.DATA_TYPE]] = {}
    ctg_nodes_meta: Dict[str, List[Node.DATA_TYPE]] = {}
    categories: Dict[str, List[str]] = {}
    try:
        with open("snippets/_config.yml", encoding="utf-8") as f:
            snip_conf = yaml.full_load(f)
    except (OSError, yaml.error.YAMLError):
        print("片段配置读取失败：")
        traceback.print_exc()
    else:
        print("正在按地区分类节点...")
        categories = snip_conf['categories']
        for ctg in categories:
            ctg_nodes[ctg] = []
            ctg_nodes_meta[ctg] = []
        _init_geoip()
        # 分类前并发预热 DNS（中国 DoH），避免几千节点串行解析
        _warmup_dns([n.data.get('server', '') for n in merged.values()])
        geo_hits = 0; name_hits = 0; conflicts = 0; redir_hits = 0
        anon_hits = 0; noregion_hits = 0
        redir_keys = [k for k in categories.get('redir', []) if k != 'OVERALL']
        for node in merged.values():
            if node.supports_meta():
                # 分类一律用当前显示名 data['name']（最终名），而非 node.name（创建时快照）。
                # 多源同名节点经 data.update() 后名字会变（如追加 "->" 中转标记），快照会漏判。
                disp_name = node.data.get('name', '') or node.name
                # 0) 中转/接力节点（名字含 "->" 或 "中转"）优先归入 redir，不受 GeoIP 影响
                if any(k in disp_name for k in redir_keys):
                    ctgs: List[str] = ['redir']
                    redir_hits += 1
                else:
                    # 1) 优先用 GeoIP 真实归属（服务器 IP 的实际国家）
                    geo_code = _geo_country(node)
                    if geo_code is None:
                        # GeoIP 无法判定（域名解析失败 / IP 不在库）→ 才允许回退名字关键词
                        ctgs = []
                        for ctg, keys in categories.items():
                            if ctg == 'redir': continue
                            for key in keys:
                                if key in disp_name:
                                    ctgs.append(ctg)
                                    break
                            if ctgs and keys[-1] == 'OVERALL':
                                break
                        if ctgs: name_hits += 1
                    elif geo_code == GEO_ANON:
                        # CDN/anycast 无固定国家 → 不打地区标签（节点仍保留在主订阅）
                        anon_hits += 1
                        ctgs = []
                    elif geo_code in categories:
                        # 真实国家且分组存在
                        ctgs = [geo_code]
                        geo_hits += 1
                        # 检测名字与真实归属冲突（仅统计，不影响分类——以真实为准）
                        name_ctgs: List[str] = []
                        for ctg_n, keys_n in categories.items():
                            if ctg_n == 'redir': continue
                            for key_n in keys_n:
                                if key_n in disp_name:
                                    name_ctgs.append(ctg_n)
                                    break
                            if name_ctgs and keys_n[-1] == 'OVERALL':
                                break
                        if name_ctgs and name_ctgs != [geo_code]:
                            conflicts += 1
                    else:
                        # 真实国家存在但本项目无对应分组（如 CZ）→ 不信任名字，不打标签
                        noregion_hits += 1
                        ctgs = []
                if len(ctgs) == 1:
                    if node.supports_clash():
                        ctg_nodes[ctgs[0]].append(node.clash_data)
                    ctg_nodes_meta[ctgs[0]].append(node.clash_data)
        print(f"地区分类: GeoIP 定位 {geo_hits} 个，名字回退 {name_hits} 个，"
              f"中转 {redir_hits} 个，CDN/anycast 不打标签 {anon_hits} 个，"
              f"无对应分组不打标签 {noregion_hits} 个，"
              f"名字与真实归属冲突已按真实纠正 {conflicts} 个")
        for ctg, proxies in ctg_nodes.items():
            with open("snippets/nodes_"+ctg+".yml", 'w', encoding="utf-8") as f:
                yaml.dump({'proxies': proxies}, f, allow_unicode=True)
        for ctg, proxies in ctg_nodes_meta.items():
            with open("snippets/nodes_"+ctg+".meta.yml", 'w', encoding="utf-8") as f:
                yaml.dump({'proxies': proxies}, f, allow_unicode=True)

    print("正在写出 Clash & Meta 订阅...")
    keywords: List[str] = []
    suffixes: List[str] = []
    match_rule = None
    for rule in conf['rules']:
        rule: str
        tmp = rule.strip().split(',')
        if len(tmp) == 2 and tmp[0] == 'MATCH':
            match_rule = rule
            break
        if len(tmp) == 3:
            rtype, rargument, rpolicy = tmp
            if rtype == 'DOMAIN-KEYWORD':
                keywords.append(rargument)
            elif rtype == 'DOMAIN-SUFFIX':
                suffixes.append(rargument)
        elif len(tmp) == 4:
            rtype, rargument, rpolicy, rresolve = tmp
            rpolicy += ','+rresolve
        else: print("规则 '"+rule+"' 无法被解析！"); continue
        for kwd in keywords:
            if kwd in rargument and kwd != rargument:
                print(rargument, "已被 KEYWORD", kwd, "命中")
                break
        else:
            for sfx in suffixes:
                if ('.'+rargument).endswith('.'+sfx) and sfx != rargument:
                    print(rargument, "已被 SUFFIX", sfx, "命中")
                    break
            else:
                k = rtype+','+rargument
                if k not in rules:
                    rules[k] = rpolicy
    conf['rules'] = [','.join(_) for _ in rules.items()]+[match_rule]

    # Clash & Meta
    global_fp: Optional[str] = conf.get('global-client-fingerprint', None)
    proxies: List[Node.DATA_TYPE] = []
    proxies_meta: List[Node.DATA_TYPE] = []
    ctg_base: Dict[str, Any] = conf['proxy-groups'][3].copy()
    names_clash: Union[Set[str], List[str]] = set()
    names_clash_meta: Union[Set[str], List[str]] = set()
    for p in merged.values():
        if p.supports_meta():
            if ('client-fingerprint' in p.data and
                    p.data['client-fingerprint'] == global_fp):
                del p.data['client-fingerprint']
            proxies_meta.append(p.clash_data)
            names_clash_meta.add(p.data['name'])
            if p.supports_clash():
                proxies.append(p.clash_data)
                names_clash.add(p.data['name'])
    names_clash = list(names_clash) or ['DIRECT'] # 0 节点时兜底，避免空 proxies 导致 mihomo 校验失败
    names_clash_meta = list(names_clash_meta) or ['DIRECT']
    conf_meta = copy.deepcopy(conf)

    # Clash
    conf['proxies'] = proxies
    for group in conf['proxy-groups']:
        if not group['proxies']:
            group['proxies'] = names_clash
    if snip_conf:
        conf['proxy-groups'][-1]['proxies'] = []
        ctg_selects: List[str] = conf['proxy-groups'][-1]['proxies']
        ctg_disp: Dict[str, str] = snip_conf['categories_disp']
        # 地区子组模板：fallback 类型，自动逐个探测首个可用节点
        ctg_auto = ctg_base.copy()
        ctg_auto['type'] = 'fallback'
        ctg_auto['url'] = 'https://speed.cloudflare.com/__down?bytes=200000'
        ctg_auto['interval'] = 300
        for ctg, payload in ctg_nodes.items():
            if ctg in ctg_disp:
                disp = ctg_auto.copy()
                disp['name'] = ctg_disp[ctg]
                if not payload: disp['proxies'] = ['REJECT']
                else: disp['proxies'] = [_['name'] for _ in payload]
                conf['proxy-groups'].append(disp)
                ctg_selects.append(disp['name'])
    try:
        dns_mode: Optional[str] = conf['dns']['enhanced-mode']
    except:
        dns_mode: Optional[str] = None
    else:
        conf['dns']['enhanced-mode'] = 'fake-ip'
    with open("list.yml", 'w', encoding="utf-8") as f:
        f.write(datetime.datetime.now().strftime('# Update: %Y-%m-%d %H:%M\n'))
        f.write(yaml.dump(conf, allow_unicode=True).replace('!!str ',''))
    with open("snippets/nodes.yml", 'w', encoding="utf-8") as f:
        f.write(yaml.dump({'proxies': proxies}, allow_unicode=True).replace('!!str ',''))

    # Meta
    conf = conf_meta
    conf['proxies'] = proxies_meta
    for group in conf['proxy-groups']:
        if not group['proxies']:
            group['proxies'] = names_clash_meta
    if snip_conf:
        conf['proxy-groups'][-1]['proxies'] = []
        ctg_selects: List[str] = conf['proxy-groups'][-1]['proxies']
        ctg_disp: Dict[str, str] = snip_conf['categories_disp']
        # 地区子组模板：fallback 类型，自动逐个探测首个可用节点
        ctg_auto = ctg_base.copy()
        ctg_auto['type'] = 'fallback'
        ctg_auto['url'] = 'https://speed.cloudflare.com/__down?bytes=200000'
        ctg_auto['interval'] = 300
        for ctg, payload in ctg_nodes_meta.items():
            if ctg in ctg_disp:
                disp = ctg_auto.copy()
                disp['name'] = ctg_disp[ctg]
                if not payload: disp['proxies'] = ['REJECT']
                else: disp['proxies'] = [_['name'] for _ in payload]
                conf['proxy-groups'].append(disp)
                ctg_selects.append(disp['name'])
    if dns_mode:
        conf['dns']['enhanced-mode'] = dns_mode
    with open("list.meta.yml", 'w', encoding="utf-8") as f:
        f.write(datetime.datetime.now().strftime('# Update: %Y-%m-%d %H:%M\n'))
        f.write(yaml.dump(conf, allow_unicode=True).replace('!!str ',''))
    with open("snippets/nodes.meta.yml", 'w', encoding="utf-8") as f:
        f.write(yaml.dump({'proxies': proxies_meta}, allow_unicode=True).replace('!!str ',''))

    if snip_conf:
        print("正在写出配置片段...")
        name_map: Dict[str, str] = snip_conf['name-map']
        snippets: Dict[str, List[str]] = {}
        for rpolicy in name_map.values(): snippets[rpolicy] = []
        for rule, rpolicy in rules.items():
            if ',' in rpolicy: rpolicy = rpolicy.split(',')[0]
            if rpolicy in name_map:
                snippets[name_map[rpolicy]].append(rule)
        for name, payload in snippets.items():
            with open("snippets/"+name+".yml", 'w', encoding="utf-8") as f:
                yaml.dump({'payload': payload}, f, allow_unicode=True)

    print("正在写出统计信息...")
    out = "序号,链接,节点数\n"
    for i, source in enumerate(sources_obj):
        out += f"{i},{source.url},"
        try: out += f"{len(source.sub)}"
        except: out += '0'
        out += '\n'
    out += f"\n总计,,{len(merged)}\n"
    open("list_result.csv",'w').write(out)

    print("写出完成！")

if __name__ == '__main__':
    from dynamic import AUTOURLS, AUTOFETCH # type: ignore
    AUTOFUNTYPE = Callable[[], Union[str, List[str], Tuple[str], Set[str], None]]
    AUTOURL: List[AUTOFUNTYPE]
    AUTOFETCH: List[AUTOFUNTYPE]
    main()

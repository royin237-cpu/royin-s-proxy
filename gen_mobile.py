#!/usr/bin/env python3
"""
gen_mobile.py — 生成移动端轻量订阅 list.mobile.yml
iOS 的 VPN 扩展（NetworkExtension）内存限制很严格，
完整版订阅（1800+ 节点、数万条规则，数 MB）会导致 Clash Mi 等客户端
启动 VPN 时崩溃（"the vpn session failed because an internal error occurred"）。

本脚本从 snippets/nodes_<地区>.meta.yml 每个地区取少量存活节点（预检后产物），
配合极简分组与规则，生成约几十 KB 的轻量订阅，专供 iOS/Android 手机端使用。
"""
import os
import yaml
from collections import OrderedDict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE_DIR, "list.mobile.yml")
TAKE_PER_REGION = 15   # 每个地区最多取 15 个节点

REGIONS = OrderedDict([
    ("JP", "日本"), ("US", "美国"), ("HK", "香港"), ("TW", "台湾"),
    ("SG", "新加坡"), ("KR", "韩国"), ("GB", "英国"), ("FR", "法国"),
    ("DE", "德国"), ("CA", "加拿大"), ("RU", "俄罗斯"), ("SE", "瑞典"),
    ("EE", "爱沙尼亚"), ("NL", "荷兰"), ("RO", "罗马尼亚"),
    ("IN", "印度"), ("TH", "泰国"), ("TR", "土耳其"), ("AU", "澳大利亚"),
    ("IT", "意大利"), ("ES", "西班牙"), ("BR", "巴西"), ("VN", "越南"),
    ("ID", "印尼"), ("PH", "菲律宾"), ("UA", "乌克兰"), ("PL", "波兰"),
    ("FI", "芬兰"), ("CN", "中国"),
])


def load_region_proxies():
    proxies = []
    for code in REGIONS:
        path = os.path.join(BASE_DIR, "snippets", f"nodes_{code}.meta.yml")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            try:
                raw = yaml.safe_load(f)
            except yaml.YAMLError:
                continue
        # snippets 文件为 {proxies: [...]} 结构，取出节点列表
        if isinstance(raw, dict):
            nodes = raw.get("proxies") or []
        elif isinstance(raw, list):
            nodes = raw
        else:
            nodes = []
        for n in nodes[:TAKE_PER_REGION]:
            if isinstance(n, dict) and n.get("name"):
                proxies.append(normalize_proxy(n))
    return proxies


def normalize_proxy(node):
    node = dict(node)
    if node.get("type") == "hysteria2":
        node.pop("tls", None)
    if node.get("type") == "vmess" and node.get("network") == "ws":
        opts = dict(node.get("ws-opts") or {})
        headers = dict(opts.get("headers") or {})
        headers.setdefault("Host", str(node.get("servername") or node.get("server") or ""))
        opts["headers"] = headers
        opts.setdefault("path", "/")
        node["ws-opts"] = opts
    node.pop("ws-headers", None)
    node.pop("ws-path", None)
    for key in ("port", "alterId"):
        if key in node:
            try:
                node[key] = int(str(node[key]).strip())
            except (TypeError, ValueError):
                pass
    for key in ("tls", "udp", "skip-cert-verify"):
        if key in node and type(node[key]) is not bool:
            if isinstance(node[key], int):
                node[key] = bool(node[key])
            elif isinstance(node[key], str):
                value = node[key].strip().lower()
                if value in ("1", "true", "yes", "on", "tls"):
                    node[key] = True
                elif value in ("0", "false", "no", "off", ""):
                    node[key] = False
    return node


def main():
    proxies = load_region_proxies()
    if not proxies:
        print("[gen_mobile] 无可用节点，跳过生成。")
        return
    names = [p["name"] for p in proxies]

    config = OrderedDict()
    config["mixed-port"] = 7890
    config["allow-lan"] = False
    config["mode"] = "rule"
    config["log-level"] = "info"
    config["ipv6"] = False
    config["proxies"] = proxies
    # 用普通 dict（SafeDumper 不支持 OrderedDict）
    config["proxy-groups"] = [
        {"name": "🚀 节点选择", "type": "select",
         "proxies": ["♻️ 自动选择", "🎯 全球直连"] + names},
        {"name": "♻️ 自动选择", "type": "fallback",
         "url": "http://www.gstatic.com/generate_204",
         "interval": 300, "proxies": names},
        {"name": "🐟 漏网之鱼", "type": "select",
         "proxies": ["🚀 节点选择", "♻️ 自动选择", "🎯 全球直连"]},
        {"name": "🎯 全球直连", "type": "select", "proxies": ["DIRECT"]},
    ]
    config["rules"] = [
        "DOMAIN-SUFFIX,local,DIRECT",
        "IP-CIDR,127.0.0.0/8,DIRECT",
        "IP-CIDR,10.0.0.0/8,DIRECT",
        "IP-CIDR,172.16.0.0/12,DIRECT",
        "IP-CIDR,192.168.0.0/16,DIRECT",
        "GEOIP,CN,DIRECT",
        "MATCH,🐟 漏网之鱼",
    ]

    update = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Update: {update}\n")
        f.write(f"# 移动端轻量订阅：{len(proxies)} 个存活节点（每地区最多 {TAKE_PER_REGION} 个），精简规则\n")
        yaml.safe_dump(dict(config), f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"[gen_mobile] list.mobile.yml generated: {len(proxies)} nodes, {size_kb:.0f} KB")


if __name__ == "__main__":
    main()

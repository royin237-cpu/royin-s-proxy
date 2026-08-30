#!/usr/bin/env python3
"""
gen_mobile.py — 生成移动端订阅 list.mobile.yml

背景：本脚本早期自带一套精简分组（🚀 节点选择 / ♻️ 自动选择 / 🐟 漏网之鱼 / 🎯 全球直连），
与 list.yml、list.meta.yml 的分组（🚀 选择代理 / ♻ 自动选择 / 🔰 延迟最低 / ✅ 手动选择 /
🌐 突破锁区 / ❓ 疑似国内 / 🐟 漏网之鱼 / 🚨 病毒网站 / ⛔ 广告拦截 / 🗺️ 选择地区 / 各国地区组）
完全不一致，导致手机端与桌面端的代理组对不上。

现改为**从已生成的 list.meta.yml 派生**，保证与线上主订阅完全一致：
  - 代理组：名称、类型、顺序全部沿用（10 个功能组 + 30 个地区组）
  - 规则：原样沿用（含 fetch.py 合并进来的广告拦截规则）
  - 节点：按地区组截断（每个地区最多 TAKE_PER_REGION 个），控制体积，
          规避 iOS VPN 扩展（NetworkExtension）内存限制导致的启动崩溃。

list.meta.yml 已由 check_alive.py 过滤为存活节点，因此本脚本必须在 check_alive.py 之后
执行（fetch.yml 中的步骤顺序已保证）。若 list.meta.yml 不存在则跳过生成，保留上一次产物。
"""
import copy
import os
import yaml
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE_DIR, "list.mobile.yml")
SOURCE = os.path.join(BASE_DIR, "list.meta.yml")
SNIPPET_CONF = os.path.join(BASE_DIR, "snippets", "_config.yml")
TAKE_PER_REGION = 15   # 每个地区最多取 15 个节点

SPECIAL_VALUES = {"DIRECT", "REJECT", "PASS"}
SELECT_REGION = "🗺️ 选择地区"


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError:
            f.seek(0)
            return yaml.full_load(f)


def dump_yaml(data):
    try:
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False,
                              default_flow_style=False)
    except yaml.representer.RepresenterError:
        # full_load 引进的锚点/自定义标签降级处理，与 fetch.py 同样去掉 !!str 标签
        return (yaml.dump(data, allow_unicode=True, sort_keys=False,
                          default_flow_style=False).replace('!!str ', ''))


def normalize_proxy(node):
    """移动端客户端对个别字段更严格，做一次归一化（沿用历史修复）。"""
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


def region_group_names(groups):
    """地区组的显示名集合（保持 list.meta.yml 中的原有顺序）。"""
    try:
        conf = load_yaml(SNIPPET_CONF) or {}
        disp = conf.get("categories_disp") or {}
        names = [disp[c] for c in (conf.get("categories") or {}) if c in disp]
        if names:
            known = {g.get("name") for g in groups}
            return [n for n in names if n in known]
    except OSError:
        pass
    # 兜底：🗺️ 选择地区 组里列出的名字就是地区组名
    for group in groups:
        if group.get("name") == SELECT_REGION:
            return [n for n in (group.get("proxies") or []) if n not in SPECIAL_VALUES]
    return []


def main():
    if not os.path.exists(SOURCE):
        print(f"[gen_mobile] {os.path.basename(SOURCE)} 不存在，跳过生成。")
        return
    base = load_yaml(SOURCE)
    groups = [copy.deepcopy(g) for g in (base.get("proxy-groups") or [])]
    all_proxies = {p["name"]: p for p in (base.get("proxies") or []) if p.get("name")}
    if not groups or not all_proxies:
        print("[gen_mobile] list.meta.yml 无节点或代理组，跳过生成。")
        return

    group_names = {g.get("name") for g in groups}
    region_names = region_group_names(groups)

    # 1) 按地区组截断，收集移动端要保留的节点名
    keep = []
    keep_set = set()
    for name in region_names:
        group = next(g for g in groups if g.get("name") == name)
        picked = [n for n in (group.get("proxies") or [])
                  if n in all_proxies and n not in keep_set][:TAKE_PER_REGION]
        keep.extend(picked)
        keep_set.update(picked)
    proxies = [normalize_proxy(all_proxies[n]) for n in keep]
    if not proxies:
        print("[gen_mobile] 无可用节点，跳过生成。")
        return

    # 2) 逐个代理组：过滤到保留节点；地区组只留本地区节点，空则 REJECT
    for group in groups:
        if group.get("name") in region_names:
            # 截断到 TAKE_PER_REGION：上游数据若有跨地区重复（同名节点被归入多组），
            # 仅按 keep_set 过滤会让本组超出上限，这里再截一次保证体积可控
            group["proxies"] = [n for n in (group.get("proxies") or [])
                                if n in keep_set][:TAKE_PER_REGION]
            if not group["proxies"]:
                group["proxies"] = ["REJECT"]
            continue
        filtered = [x for x in (group.get("proxies") or [])
                    if x in keep_set or x in group_names or x in SPECIAL_VALUES]
        if filtered:
            group["proxies"] = filtered
        elif group.get("type") in ("url-test", "fallback", "load-balance"):
            group["proxies"] = list(keep)     # 自动测速组兜底：放全部保留节点
        else:
            group["proxies"] = ["DIRECT"]     # select 组兜底

    # 3) 🗺️ 选择地区 只放地区组名（过滤模式下原样保留，此处保证顺序与内容一致）
    for group in groups:
        if group.get("name") == SELECT_REGION:
            group["proxies"] = list(region_names) or ["DIRECT"]
            break

    conf = copy.deepcopy(base)
    conf["proxies"] = proxies
    conf["proxy-groups"] = groups
    # 4) 移动端特有的顶层字段覆盖（规则与代理组原样沿用 list.meta.yml）
    conf["mixed-port"] = 7890
    conf["allow-lan"] = False
    conf["mode"] = "rule"
    conf["log-level"] = "info"
    conf["ipv6"] = False
    conf["external-controller"] = "127.0.0.1:9090"
    dns = conf.get("dns")
    if isinstance(dns, dict):
        # 移动端 fake-ip 兼容性较差，且末尾 GEOIP,CN 规则依赖真实解析结果
        dns["enhanced-mode"] = "redir-host"

    update = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Update: {update}\n")
        f.write(f"# 移动端订阅：{len(proxies)} 个存活节点（每地区最多 {TAKE_PER_REGION} 个），"
                f"代理组与规则同 list.meta.yml\n")
        f.write(dump_yaml(conf))
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"[gen_mobile] list.mobile.yml generated: {len(proxies)} nodes, "
          f"{len(groups)} proxy-groups, {len(conf.get('rules') or [])} rules, {size_kb:.0f} KB")


if __name__ == "__main__":
    main()

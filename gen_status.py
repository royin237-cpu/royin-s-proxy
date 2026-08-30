#!/usr/bin/env python3
"""
gen_status.py — 生成静态状态 JSON 文件（web/status.json）
供 GitHub Pages 纯静态部署使用，无需 serve.py 后端。

读取：
  - list_result.csv   → 源抓取统计
  - snippets/*.meta.yml → 地区节点数
  - list.meta.yml     → 更新时间（首行注释）

输出：
  - web/status.json
"""
import csv
import json
import os
import re
from datetime import datetime
from collections import OrderedDict

import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
OUTPUT_PATH = os.path.join(WEB_DIR, "status.json")

REGION_MAP = OrderedDict([
    ("JP", ("\U0001f1ef\U0001f1f5", "日本")), ("US", ("\U0001f1fa\U0001f1f8", "美国")),
    ("CN", ("\U0001f1e8\U0001f1f3", "中国")), ("HK", ("\U0001f1ed\U0001f1f0", "香港")),
    ("TW", ("\U0001f1f9\U0001f1fc", "台湾")), ("CA", ("\U0001f1e8\U0001f1e6", "加拿大")),
    ("FR", ("\U0001f1eb\U0001f1f7", "法国")), ("SG", ("\U0001f1f8\U0001f1ec", "新加坡")),
    ("GB", ("\U0001f1ec\U0001f1e7", "英国")), ("KR", ("\U0001f1f0\U0001f1f7", "韩国")),
    ("RU", ("\U0001f1f7\U0001f1fa", "俄罗斯")), ("DE", ("\U0001f1e9\U0001f1ea", "德国")),
    ("SE", ("\U0001f1f8\U0001f1ea", "瑞典")), ("EE", ("\U0001f1ea\U0001f1ea", "爱沙尼亚")),
    ("CH", ("\U0001f1e8\U0001f1ed", "瑞士")), ("NL", ("\U0001f1f3\U0001f1f1", "荷兰")),
    ("RO", ("\U0001f1f7\U0001f1f4", "罗马尼亚")), ("IN", ("\U0001f1ee\U0001f1f3", "印度")),
    ("TH", ("\U0001f1f9\U0001f1ed", "泰国")), ("TR", ("\U0001f1f9\U0001f1f7", "土耳其")),
    ("AU", ("\U0001f1e6\U0001f1fa", "澳大利亚")), ("IT", ("\U0001f1ee\U0001f1f9", "意大利")),
    ("ES", ("\U0001f1ea\U0001f1f8", "西班牙")), ("BR", ("\U0001f1e7\U0001f1f7", "巴西")),
    ("VN", ("\U0001f1fb\U0001f1f3", "越南")), ("ID", ("\U0001f1ee\U0001f1e9", "印尼")),
    ("PH", ("\U0001f1f5\U0001f1ed", "菲律宾")), ("UA", ("\U0001f1fa\U0001f1e6", "乌克兰")),
    ("PL", ("\U0001f1f5\U0001f1f1", "波兰")), ("FI", ("\U0001f1eb\U0001f1ee", "芬兰")),
])


def parse_update_time():
    meta_path = os.path.join(BASE_DIR, "list.meta.yml")
    if not os.path.exists(meta_path):
        return ""
    with open(meta_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    m = re.match(r"#\s*Update:\s*(.+)", first_line)
    return m.group(1) if m else ""


def _count_proxies(path):
    """用 YAML 解析统计 proxies 节点数（权威口径）。

    不能用 `- name:` 行数：节点块首字段可能是 cipher/client-fingerprint/alterId 等，
    只有 proxy-groups 才固定以 `- name:` 开头，行数统计会严重低估节点数。
    """
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return 0
    if isinstance(data, dict):
        proxies = data.get("proxies") or []
    elif isinstance(data, list):
        proxies = data
    else:
        proxies = []
    return len(proxies)


def parse_regions():
    regions = {}
    for code, (flag, name) in REGION_MAP.items():
        snip = os.path.join(BASE_DIR, "snippets", f"nodes_{code}.meta.yml")
        count = _count_proxies(snip)
        if count > 0:
            regions[code] = {"flag": flag, "name": name, "count": count}
    return regions


def parse_sources():
    csv_path = os.path.join(BASE_DIR, "list_result.csv")
    sources = []
    total = 0
    if not os.path.exists(csv_path):
        return sources, total
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 3 and row[0].strip() == "总计":
                try:
                    total = int(row[2])
                except ValueError:
                    pass
                continue
            if len(row) >= 3:
                try:
                    idx = int(row[0]) if row[0].strip().isdigit() else 0
                except ValueError:
                    idx = 0
                try:
                    nodes = int(row[2]) if row[2].strip().isdigit() else 0
                except ValueError:
                    nodes = 0
                url = row[1][:80] if len(row) > 1 else ""
                sources.append({"index": idx, "url": url, "nodes": nodes})
    return sources, total


def count_alive_nodes():
    """统计 check_alive 过滤后的实际节点数（从 list.meta.yml 用 YAML 解析读取）"""
    return _count_proxies(os.path.join(BASE_DIR, "list.meta.yml"))


def main():
    update_time = parse_update_time()
    regions = parse_regions()
    sources, csv_total = parse_sources()
    # 优先使用 check_alive 过滤后的实际节点数
    alive_total = count_alive_nodes()
    total = alive_total if alive_total > 0 else csv_total

    data = {
        "total": total,
        "regions": regions,
        "update_time": update_time,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": sources,
    }

    os.makedirs(WEB_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[gen_status] web/status.json generated: {total} alive nodes (csv_total={csv_total}), {len(sources)} sources, {len(regions)} regions")


if __name__ == "__main__":
    main()

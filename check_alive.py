#!/usr/bin/env python3
"""Filter generated subscriptions using real mihomo proxy delay checks."""
import argparse
import base64
import concurrent.futures
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, unquote
from urllib.request import urlopen

import yaml


ROOT = Path(__file__).resolve().parent
# 多端点测速：逗号分隔，依次尝试，任一通过即判定存活（首个成功即返回）
_raw_urls = os.environ.get("ALIVE_TEST_URLS") or os.environ.get(
    "ALIVE_TEST_URL", "https://www.gstatic.com/generate_204"
)
TEST_URLS = [u.strip() for u in _raw_urls.split(",") if u.strip()]
TIMEOUT_MS = int(os.environ.get("ALIVE_TIMEOUT_MS", "7000"))
# 延迟上限：超过视为龟速节点，直接剔除（不进存活名单）
MAX_DELAY_MS = int(os.environ.get("ALIVE_MAX_DELAY_MS", "5000"))
WORKERS = int(os.environ.get("ALIVE_WORKERS", "128"))
MIN_ALIVE_RATIO = float(os.environ.get("ALIVE_MIN_RATIO", "0.005"))
RETRY = int(os.environ.get("ALIVE_RETRY", "1"))
# 订阅总量上限：按延迟升序只保留最快的 N 个存活节点（0 或未设置 = 不限制）。
# 免费节点质量参差，云端在海外机房测活，大量节点对国内用户仍会 timeout，
# 只保留延迟最低的一批可显著降低客户端实际测到的 timeout 比例，并控制订阅体积。
MAX_KEEP = int(os.environ.get("ALIVE_MAX_KEEP", "0"))
# 单源配额：每个来源最多保留的节点数（0 或未设置 = 不限制）。
# 防止聚合源独霸名额（如 Au1rxx 曾占 150 名额中的 128 个，且其节点国内不通），
# 保证订阅来源多样性——用户能用的节点更可能被保留。
MAX_PER_SOURCE = int(os.environ.get("ALIVE_MAX_PER_SOURCE", "0"))
# 垃圾协议预过滤：公开抓取的 http/socks5 代理多为海外机房内网代理，
# 国内直连基本不可用，且占据订阅体积，测活前直接剔除
DROP_TYPES = {t.strip() for t in os.environ.get("ALIVE_DROP_TYPES", "http,socks5").split(",") if t.strip()}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def api_get(url, timeout):
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def start_mihomo(proxies, binary):
    config = {
        "mixed-port": free_port(),
        "external-controller": f"127.0.0.1:{free_port()}",
        "mode": "direct",
        "ipv6": False,
        "log-level": "error",
        "unified-delay": True,
        "tcp-concurrent": True,
        "profile": {"store-selected": False, "store-fake-ip": False},
        "proxies": proxies,
        "rules": ["MATCH,DIRECT"],
    }
    config_path = ROOT / "tmp_alive_config.yml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    process = subprocess.Popen(
        [str(binary), "-f", str(config_path), "-d", str(ROOT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, f"http://{config['external-controller']}", config_path


def test_proxy(base, name):
    """严格模式：所有测速端点都必须通过（延迟>0 且 <= 上限）。
    任一端点失败/超时/龟速 → 该节点判定不可用。
    返回值为各端点中最差延迟。"""
    worst = 0
    for test_url in TEST_URLS:
        endpoint = f"{base}/proxies/{quote(name, safe='')}/delay"
        endpoint += f"?url={quote(test_url, safe='')}&timeout={TIMEOUT_MS}"
        try:
            result = api_get(endpoint, TIMEOUT_MS / 1000 + 2)
            delay = result.get("delay")
        except Exception:
            return None  # 任一端点不可达，直接剔除
        if not (isinstance(delay, int) and delay > 0):
            return None
        if delay > MAX_DELAY_MS:
            return None  # 龟速剔除
        worst = max(worst, delay)
    return worst if worst > 0 else None


def measure(binary, proxies):
    process, base, config_path = start_mihomo(proxies, binary)
    delays = {}
    try:
        for _ in range(50):
            try:
                api_get(f"{base}/version", 1)
                break
            except Exception:
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    raise RuntimeError(f"mihomo exited: {output}")
                time.sleep(0.1)
        else:
            raise RuntimeError("mihomo API did not start")

        print(f"[alive] testing {len(proxies)} proxies through {TEST_URLS}", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {
                executor.submit(test_proxy, base, proxy["name"]): proxy["name"]
                for proxy in proxies
            }
            for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
                delay = future.result()
                if delay is not None:
                    delays[futures[future]] = delay
                if index % 100 == 0 or index == len(futures):
                    print(
                        f"[alive] {index}/{len(futures)} tested, {len(delays)} alive",
                        flush=True,
                    )
    finally:
        process.terminate()
        try:
            process.wait(3)
        except subprocess.TimeoutExpired:
            process.kill()
        try:
            try:
                config_path.unlink()
            except OSError:
                pass
        except FileNotFoundError:
            pass
    return delays


def load_yaml(path):
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def source_of(name: str) -> str:
    """从节点名提取来源标识。命名形如 '7|xxx' 或 '7,21|xxx'，取首个源序号。"""
    if "|" in name:
        head = name.split("|", 1)[0]
        return head.split(",")[0].strip()
    return "?"


def apply_source_quota(merged: dict, per_source: int) -> dict:
    """单源配额：按延迟升序均衡各来源节点数。

    merged: {节点名: 延迟ms}，已按延迟升序传入。
    返回：受配额约束后的新 dict（仍按延迟升序）。
    """
    if per_source <= 0:
        return merged
    counts = {}
    result = {}
    for name, delay in merged.items():
        src = source_of(name)
        if counts.get(src, 0) >= per_source:
            continue  # 该来源已达配额，跳过（延迟更慢的同源节点被挤掉）
        counts[src] = counts.get(src, 0) + 1
        result[name] = delay
    return result


def save_yaml(path, data, header=""):
    with path.open("w", encoding="utf-8") as stream:
        if header:
            stream.write(header)
        yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)


def _region_group_names():
    """地区分组的显示名集合（来自 snippets/_config.yml 的 categories_disp）。
    这些组清空时必须保持为空/REJECT，绝不能塞入随机节点——否则地区组会混入各国节点。"""
    try:
        cfg = load_yaml(ROOT / "snippets" / "_config.yml")
        return set((cfg.get("categories_disp") or {}).values())
    except Exception:
        return set()


def update_config(path, alive_names, delay_by_name):
    data = load_yaml(path)
    old_count = len(data.get("proxies", []))
    proxies = [p for p in data.get("proxies", []) if p.get("name") in alive_names]
    if not proxies:
        return 0
    data["proxies"] = proxies
    proxy_names = {p["name"] for p in proxies}

    # 收集所有 proxy-group 的 name（组间引用不应被过滤）
    group_names = {g.get("name", "") for g in data.get("proxy-groups", [])}
    # 保留的特殊值
    special_vals = {"DIRECT", "REJECT", "PASS"}
    region_names = _region_group_names()
    region_emptied = 0

    for group in data.get("proxy-groups", []):
        group["proxies"] = [
            item
            for item in group.get("proxies", [])
            if item in proxy_names or item in group_names or item in special_vals
        ]
        # 空组兜底：
        #   地区组 → REJECT（无该地区存活节点时保持"无节点"，绝不塞入其他国家的节点）
        #   其他 select → DIRECT；其他 url-test/fallback/load-balance → 按延迟取存活节点
        if not group.get("proxies"):
            gtype = group.get("type", "select")
            if group.get("name") in region_names:
                group["proxies"] = ["REJECT"]
                region_emptied += 1
            elif gtype in ("url-test", "fallback", "load-balance"):
                # 按延迟升序（快节点优先），限制最多 50 个避免过大
                ordered = sorted(proxy_names, key=lambda n: delay_by_name.get(n, 99999))
                group["proxies"] = ordered[:50]
            else:
                group["proxies"] = ["DIRECT"]

    text = path.read_text(encoding="utf-8", errors="ignore")
    first = text.splitlines()[0] if text else ""
    header = first + "\n" if first.startswith("#") else ""
    save_yaml(path, data, header)
    print(f"[alive] {path.name}: {old_count} -> {len(proxies)}"
          + (f"（{region_emptied} 个地区组无存活节点，已置空为 REJECT）" if region_emptied else ""))
    return len(proxies)


def update_v2ray(alive_names):
    raw_path = ROOT / "list_raw.txt"
    encoded_path = ROOT / "list.txt"
    if not raw_path.exists():
        return 0
    lines = []
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        if not line or "#" not in line:
            continue
        name = line.rsplit("#", 1)[-1]
        if name in alive_names or unquote(name) in alive_names:
            lines.append(line)
    if not lines:
        return 0
    raw = "\n".join(lines) + "\n"
    raw_path.write_text(raw, encoding="utf-8")
    encoded_path.write_text(
        base64.b64encode(raw.encode("utf-8")).decode("ascii"), encoding="utf-8"
    )
    print(f"[alive] list.txt: {len(lines)}")
    return len(lines)


def update_snippets(alive_names):
    for path in (ROOT / "snippets").glob("nodes*.yml"):
        data = load_yaml(path)
        proxies = data.get("proxies")
        if not proxies:
            continue
        filtered = [p for p in proxies if p.get("name") in alive_names]
        if filtered:
            data["proxies"] = filtered
            save_yaml(path, data)
            print(f"[alive] {path.relative_to(ROOT)}: {len(proxies)} -> {len(filtered)}")


def default_binary():
    env = os.environ.get("MIHOMO_BIN")
    if env and Path(env).exists():
        return Path(env)
    local = ROOT / "mihomo"
    if local.exists():
        return local
    verge = Path(r"D:\1_software\clash\clash_verge_rev\Clash Verge\verge-mihomo.exe")
    if verge.exists():
        return verge
    raise SystemExit("mihomo binary not found; set MIHOMO_BIN")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="list.meta.yml")
    args = parser.parse_args()

    binary = default_binary()
    data = load_yaml(ROOT / args.input)
    proxies = data.get("proxies", [])
    if not proxies:
        raise SystemExit("no proxies found")

    # 垃圾协议预过滤：剔除 http/socks5 等公开代理类型
    if DROP_TYPES:
        before = len(proxies)
        proxies = [p for p in proxies if p.get("type") not in DROP_TYPES]
        if before != len(proxies):
            print(f"[alive] pre-filtered {before - len(proxies)} junk-type proxies "
                  f"(types={DROP_TYPES}), remaining {len(proxies)}", flush=True)
    if not proxies:
        raise SystemExit("no proxies left after junk-type filtering")

    try:
        (ROOT / "probe_proxies.json").write_text(json.dumps(proxies, ensure_ascii=False), encoding="utf-8")
        targets = [{"name": p.get("name",""), "server": p.get("server",""), "port": p.get("port",0)} for p in proxies if p.get("name") and p.get("server") and p.get("port")]
        (ROOT / "probe_targets.json").write_text(json.dumps(targets, ensure_ascii=False), encoding="utf-8")
        print(f"[alive] exported {len(proxies)} probe targets", flush=True)
    except OSError as e:
        print(f"[alive] WARNING: export probe targets failed: {e}", flush=True)

    # 多轮测活取交集：所有轮都通过的节点才算存活（消除偶发抖动）
    rounds = []
    for _ in range(RETRY + 1):
        res = measure(binary, proxies)
        if res:
            rounds.append(res)
    if not rounds:
        raise SystemExit("alive check found 0 usable proxies in all rounds, keeping unfiltered")

    alive_names = set(rounds[0])
    for res in rounds[1:]:
        alive_names &= set(res)
    if not alive_names:
        # 交集为空（极罕见），退回最严格的一轮
        alive_names = min((set(r) for r in rounds), key=len)
    merged = {n: rounds[-1].get(n, 0) for n in alive_names}
    print(f"[alive] rounds={[len(r) for r in rounds]}, intersection={len(merged)}", flush=True)

    # 按延迟升序排序（快节点在前），并应用总量上限
    ordered = sorted(merged.items(), key=lambda kv: kv[1])
    if MAX_KEEP > 0 and len(ordered) > MAX_KEEP:
        print(f"[alive] trimming {len(ordered)} -> {MAX_KEEP} fastest nodes (ALIVE_MAX_KEEP={MAX_KEEP})", flush=True)
        ordered = ordered[:MAX_KEEP]
    merged = dict(ordered)

    # 单源配额：防止某个源独霸名额
    if MAX_PER_SOURCE > 0:
        before = len(merged)
        merged = apply_source_quota(merged, MAX_PER_SOURCE)
        print(f"[alive] source quota {MAX_PER_SOURCE}/source: {before} -> {len(merged)} nodes", flush=True)

    if len(merged) / len(proxies) < MIN_ALIVE_RATIO:
        print(f"[alive] WARNING: only {len(merged)}/{len(proxies)} alive "
              f"({len(merged)/len(proxies)*100:.2f}%), below threshold {MIN_ALIVE_RATIO*100:.2f}%")
        print("[alive] proceeding with filtering anyway (few alive > 4000 dead)")

    (ROOT / "alive_result.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # 中国真实测活优先：asia_probe_result.json 由中国服务器 mihomo 实测产出，是用户真实视角权威结果；
    # 云端(美国)测活仅作探针失效/过期时的兜底。
    merged_china = None
    asia_path = ROOT / "asia_probe_result.json"
    meta_path = ROOT / "asia_probe_meta.json"
    if asia_path.exists():
        try:
            asia = json.loads(asia_path.read_text(encoding="utf-8"))
            fresh = True
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    age = time.time() - float(meta.get("generated", 0))
                    fresh = age < 36 * 3600
                    print(f"[alive] asia probe meta: age={age/3600:.1f}h fresh={fresh}", flush=True)
                except (json.JSONDecodeError, OSError, ValueError):
                    fresh = True
            # 匹配键用 server|port|type 稳定身份（节点名每轮抓取会变，按名匹配会丢节点）
            key_map = {}
            for p in proxies:
                k = f"{p.get('server')}|{p.get('port')}|{p.get('type')}"
                key_map[k] = p.get("name")
            inter = {}
            for k, d in asia.items():
                if k in key_map:
                    inter[key_map[k]] = d
                elif k in key_map.values():
                    inter[k] = d  # 旧格式（按名）兼容
            if fresh and inter:
                merged_china = inter
                print(f"[alive] China real-alive filter: {len(proxies)} raw -> {len(inter)} (matched by server:port:type)", flush=True)
            else:
                print(f"[alive] WARNING: asia probe stale/empty (fresh={fresh}, inter={len(inter)}), fallback to cloud-alive", flush=True)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[alive] WARNING: read asia_probe_result.json failed ({e}), fallback to cloud-alive", flush=True)
    else:
        print("[alive] no asia_probe_result.json, fallback to cloud-alive", flush=True)
    if merged_china is not None:
        merged = merged_china

    alive_names = set(merged)
    update_config(ROOT / "list.meta.yml", alive_names, merged)
    update_config(ROOT / "list.yml", alive_names, merged)
    update_v2ray(alive_names)
    update_snippets(alive_names)
    print(f"[alive] completed: {len(merged)} usable proxies")


if __name__ == "__main__":
    main()

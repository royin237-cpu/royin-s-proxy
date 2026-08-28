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
    for test_url in TEST_URLS:
        endpoint = f"{base}/proxies/{quote(name, safe='')}/delay"
        endpoint += f"?url={quote(test_url, safe='')}&timeout={TIMEOUT_MS}"
        try:
            result = api_get(endpoint, TIMEOUT_MS / 1000 + 2)
            delay = result.get("delay")
            if isinstance(delay, int) and delay > 0:
                if delay > MAX_DELAY_MS:
                    return None  # 存活但龟速，视为不可用
                return delay
        except Exception:
            continue
    return None


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


def save_yaml(path, data, header=""):
    with path.open("w", encoding="utf-8") as stream:
        if header:
            stream.write(header)
        yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)


def update_config(path, alive_names, delay_by_name):
    data = load_yaml(path)
    old_count = len(data.get("proxies", []))
    proxies = [p for p in data.get("proxies", []) if p.get("name") in alive_names]
    if not proxies:
        return 0
    data["proxies"] = proxies
    proxy_names = {p["name"] for p in proxies}

    for group in data.get("proxy-groups", []):
        group["proxies"] = [
            item
            for item in group.get("proxies", [])
            if item in proxy_names or item == "DIRECT"
        ]
        if not group.get("proxies"):
            group["proxies"] = ["DIRECT"]

    text = path.read_text(encoding="utf-8", errors="ignore")
    first = text.splitlines()[0] if text else ""
    header = first + "\n" if first.startswith("#") else ""
    save_yaml(path, data, header)
    print(f"[alive] {path.name}: {old_count} -> {len(proxies)}")
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

    merged = {}
    for _ in range(RETRY + 1):
        merged.update(measure(binary, proxies))
        if merged:
            break
    if not merged:
        raise SystemExit("alive check found 0 usable proxies, keeping unfiltered")

    if len(merged) / len(proxies) < MIN_ALIVE_RATIO:
        print(f"[alive] WARNING: only {len(merged)}/{len(proxies)} alive "
              f"({len(merged)/len(proxies)*100:.2f}%), below threshold {MIN_ALIVE_RATIO*100:.2f}%")
        print("[alive] proceeding with filtering anyway (few alive > 4000 dead)")

    (ROOT / "alive_result.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    alive_names = set(merged)
    update_config(ROOT / "list.meta.yml", alive_names, merged)
    update_config(ROOT / "list.yml", alive_names, merged)
    update_v2ray(alive_names)
    update_snippets(alive_names)
    print(f"[alive] completed: {len(merged)} usable proxies")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
asia_probe.py — 亚洲探针：从亚洲视角对代理节点做 TCP 连通性二次校验。

用法：
  python asia_probe.py --input list.meta.yml --output asia_probe_result.json

原理：
  GitHub Actions 云端测活（美国机房）通过的节点，对国内用户可能仍 timeout。
  本脚本对每个节点的 server:port 做一次 TCP 握手测试（从运行环境出发），
  若部署在亚洲区域的免费平台（如 Oracle Cloud 日本/新加坡 VM）上运行，
  则能剔除"美国可达但亚洲不可达"的节点。

输出：
  JSON 字典 {节点名: 延迟ms}，仅包含 TCP 握手成功的节点。
  与 alive_result.json 格式一致，可供 check_alive.py 做二次过滤。

注意：
  TCP 握手成功 ≠ 代理协议可用，但能快速排除"端口完全不通"的死节点。
  延迟为 TCP connect 耗时，仅供参考（非代理端到端延迟）。
"""
import argparse
import concurrent.futures
import json
import socket
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
TIMEOUT_S = 3.0  # TCP 握手超时
WORKERS = 64  # 并发数


def tcp_ping(host: str, port: int, timeout: float = TIMEOUT_S) -> int | None:
    """对 host:port 做 TCP 握手，返回耗时 ms 或 None（失败）。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.monotonic()
        sock.connect((host, int(port)))
        elapsed_ms = int((time.monotonic() - start) * 1000)
        sock.close()
        return elapsed_ms
    except (OSError, ValueError, OverflowError):
        return None


def probe_all(proxies: list) -> dict:
    """对全部代理节点做 TCP 探测，返回 {节点名: 延迟ms}。"""
    results = {}

    def probe_one(proxy):
        name = proxy.get("name", "")
        server = proxy.get("server", "")
        port = proxy.get("port", 0)
        if not server or not port:
            return name, None
        delay = tcp_ping(server, port)
        return name, delay

    total = len(proxies)
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(probe_one, p): p for p in proxies}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            name, delay = future.result()
            if delay is not None:
                results[name] = delay
            if i % 100 == 0 or i == total:
                print(f"[asia_probe] {i}/{total} probed, {len(results)} reachable", flush=True)

    return results


def main():
    parser = argparse.ArgumentParser(description="亚洲探针：TCP 连通性二次校验")
    parser.add_argument("--input", default="list.meta.yml",
                        help="输入订阅文件（默认 list.meta.yml）")
    parser.add_argument("--output", default="asia_probe_result.json",
                        help="输出 JSON 路径（默认 asia_probe_result.json）")
    args = parser.parse_args()

    input_path = ROOT / args.input
    output_path = ROOT / args.output

    with input_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    proxies = data.get("proxies") or []
    if not proxies:
        print("[asia_probe] no proxies found, writing empty result")
        output_path.write_text("{}", encoding="utf-8")
        return

    print(f"[asia_probe] probing {len(proxies)} proxies from $(hostname -I 2>/dev/null || echo 'unknown')", flush=True)
    results = probe_all(proxies)

    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"[asia_probe] completed: {len(results)}/{len(proxies)} reachable from Asia", flush=True)
    print(f"[asia_probe] output: {output_path}", flush=True)


if __name__ == "__main__":
    main()

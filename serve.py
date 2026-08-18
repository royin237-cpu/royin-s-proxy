#!/usr/bin/env python3
"""
AutoMergePublicNodes — Dashboard Backend
单文件 HTTP 服务（纯标准库），提供：
  GET /                → 面板页面 (web/dashboard.html)
  GET /api/status      → JSON：节点统计 / 地区分布 / 更新时间 / 源抓取结果
  GET /api/update      → 触发 fetch.py 后台更新（非阻塞，返回任务状态）
  GET /api/update/status → 查询更新进度
  GET /list.meta.yml   → Meta 订阅文件
  GET /list.yml        → Clash 订阅文件
  GET /list.txt        → V2Ray 订阅文件（base64）
  GET /snippets/<file> → 配置片段
  GET /list_result.csv → 源抓取统计
"""
import os, sys, json, csv, subprocess, threading, time, re
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote
from datetime import datetime
from collections import OrderedDict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
PORT = 8088
VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
FETCH_SCRIPT = os.path.join(BASE_DIR, "fetch.py")

# ── 全局更新状态 ──
update_state = {"running": False, "done": False, "output": "", "started": 0, "finished": 0, "error": ""}

# ── 地区代码 → 国旗 emoji / 中文名映射 ──
REGION_MAP = OrderedDict([
    ("JP", ("🇯🇵", "日本")), ("US", ("🇺🇸", "美国")), ("CN", ("🇨🇳", "中国")),
    ("HK", ("🇭🇰", "香港")), ("TW", ("🇹🇼", "台湾")), ("CA", ("🇨🇦", "加拿大")),
    ("FR", ("🇫🇷", "法国")), ("SG", ("🇸🇬", "新加坡")), ("GB", ("🇬🇧", "英国")),
    ("KR", ("🇰🇷", "韩国")), ("RU", ("🇷🇺", "俄罗斯")), ("DE", ("🇩🇪", "德国")),
    ("SE", ("🇸🇪", "瑞典")), ("EE", ("🇪🇪", "爱沙尼亚")),
])


def parse_list_meta():
    """从 list.meta.yml 读取节点数、地区分布、更新时间"""
    meta_path = os.path.join(BASE_DIR, "list.meta.yml")
    if not os.path.exists(meta_path):
        return {"total": 0, "regions": {}, "update_time": ""}
    # 读取更新时间（第一行注释）
    update_time = ""
    with open(meta_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
        m = re.match(r"#\s*Update:\s*(.+)", first_line)
        if m:
            update_time = m.group(1)
    # 统计各地区节点数（从 snippets 读取，避免完整 yaml 解析）
    regions = {}
    for code, (flag, name) in REGION_MAP.items():
        snip = os.path.join(BASE_DIR, "snippets", f"nodes_{code}.meta.yml")
        count = 0
        if os.path.exists(snip):
            with open(snip, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("- name:"):
                        count += 1
        if count > 0:
            regions[code] = {"flag": flag, "name": name, "count": count}
    # 总数从 list_result.csv 最后一行读取
    total = 0
    csv_path = os.path.join(BASE_DIR, "list_result.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            for row in reader:
                if len(row) >= 3 and row[0].strip() == "总计":
                    try:
                        total = int(row[2])
                    except ValueError:
                        pass
    return {"total": total, "regions": regions, "update_time": update_time}


def parse_sources():
    """从 list_result.csv 读取各源抓取结果"""
    csv_path = os.path.join(BASE_DIR, "list_result.csv")
    sources = []
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 3 and row[0].strip() == "总计":
                    continue
                if len(row) >= 3:
                    sources.append({
                        "index": int(row[0]) if row[0].isdigit() else 0,
                        "url": row[1][:80],
                        "nodes": int(row[2]) if row[2].isdigit() else 0,
                    })
    return sources


def run_fetch_async():
    """后台运行 fetch.py"""
    global update_state
    update_state = {"running": True, "done": False, "output": "", "started": time.time(), "finished": 0, "error": ""}
    try:
        proc = subprocess.run(
            [VENV_PYTHON, FETCH_SCRIPT],
            capture_output=True, text=True, timeout=300,
            cwd=BASE_DIR,
        )
        update_state["output"] = proc.stdout[-2000:] if proc.stdout else ""
        if proc.returncode != 0:
            update_state["error"] = proc.stderr[-500:] if proc.stderr else f"exit code {proc.returncode}"
    except subprocess.TimeoutExpired:
        update_state["error"] = "fetch.py 执行超时（5分钟）"
    except Exception as e:
        update_state["error"] = str(e)
    finally:
        update_state["running"] = False
        update_state["done"] = True
        update_state["finished"] = time.time()


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file_content(self, path, content_type="text/plain; charset=utf-8"):
        if not os.path.exists(path) or not os.path.isfile(path):
            self.send_error(404, "Not Found")
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        # ── 面板首页 ──
        if path == "/" or path == "/dashboard" or path == "/dashboard.html":
            self.send_file_content(os.path.join(WEB_DIR, "dashboard.html"), "text/html; charset=utf-8")
            return

        # ── 状态 API ──
        if path == "/api/status":
            data = parse_list_meta()
            data["sources"] = parse_sources()
            data["server_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data["fetch_running"] = update_state["running"]
            self.send_json(data)
            return

        # ── 触发更新 ──
        if path == "/api/update":
            if update_state["running"]:
                self.send_json({"ok": False, "msg": "更新正在进行中，请等待完成"}, 409)
            else:
                t = threading.Thread(target=run_fetch_async, daemon=True)
                t.start()
                self.send_json({"ok": True, "msg": "已触发后台更新，请稍后查询 /api/update/status"})
            return

        # ── 更新进度查询 ──
        if path == "/api/update/status":
            self.send_json({
                "running": update_state["running"],
                "done": update_state["done"],
                "output": update_state["output"],
                "error": update_state["error"],
                "elapsed": round(update_state["finished"] - update_state["started"], 1) if update_state["finished"] else round(time.time() - update_state["started"], 1) if update_state["started"] else 0,
            })
            return

        # ── 订阅文件分发 ──
        sub_files = {
            "/list.meta.yml": ("list.meta.yml", "text/yaml; charset=utf-8"),
            "/list.yml": ("list.yml", "text/yaml; charset=utf-8"),
            "/list.txt": ("list.txt", "text/plain; charset=utf-8"),
            "/list_result.csv": ("list_result.csv", "text/csv; charset=utf-8"),
        }
        if path in sub_files:
            fname, ctype = sub_files[path]
            self.send_file_content(os.path.join(BASE_DIR, fname), ctype)
            return

        # ── snippets 文件 ──
        if path.startswith("/snippets/"):
            fname = unquote(path[len("/snippets/"):])
            # 安全检查：禁止路径穿越
            if ".." in fname or "/" in fname or "\\" in fname:
                self.send_error(403, "Forbidden")
                return
            self.send_file_content(os.path.join(BASE_DIR, "snippets", fname), "text/yaml; charset=utf-8")
            return

        # ── favicon ──
        if path == "/favicon.ico":
            self.send_error(404)
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # 简化日志
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def main():
    os.chdir(BASE_DIR)
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"🚀 Dashboard 服务已启动: http://127.0.0.1:{PORT}")
    print(f"   订阅链接: http://127.0.0.1:{PORT}/list.meta.yml")
    print(f"   按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()

# AutoMergePublicNodes 项目长期约定

## 运行 fetch.py 的前提
- **必须存在 `local_proxy.conf`**，内容为 `http://127.0.0.1:7890`（指向 Verge 运行时 mixed-port）。
- 2026-08 实测：**直连 GitHub raw 已可用**（curl 200），无代理也能抓到节点；代理仅提速。
- Verge 运行时端口以 `%APPDATA%/io.github.clash-verge-rev.clash-verge-rev/verge.yaml` 的 `verge_mixed_port` 为准（当前 **7890**，旧记忆里的 7897 已过期）。
- 内核路径：`D:\1_software\clash\clash_verge_rev\Clash Verge\verge-mihomo.exe`；校验命令：`verge-mihomo.exe -t -f <yml> -d <APPDATA 目录>`。
- 依赖环境：项目内 `.venv/`（Python 3.13 managed），需装 PyYAML / requests / requests-file（requests-file 来自 github.com，需 github 可达）。无 venv 时先 `python -m venv .venv && pip install -r requirements.txt`。

## 配置红线（违反会导致 Verge 加载失败）
- `config.yml` 及生成的 `list.meta.yml` / `list.yml` **不能含 `global-client-fingerprint`**：新版 mihomo 已移除顶层该字段，加载报 "global-client-fingerprint configuration is removed"。fetch.py 只读取不写回此字段，模板无则产物无。
- 生成的订阅里 `✅ 手动选择` 等分组通过 `*id001` 锚点引用全部节点；若节点数为 0 则该锚点为空数组，Verge 报 "use or proxies missing"。fetch.py 已在写出段兜底 `['DIRECT']`。
- 新版 mihomo 校验更严，fetch.py `clash_data`/`supports_meta` 已加兜底：REALITY 必 tls=true；`fingerprint`→`client-fingerprint`；vmess/ss 缺 cipher 丢弃；hysteria2 `obfs: none` 删除；ssr obfs≠plain 且无 obfs-password 丢弃。
- `sources.list` 行末 `#` 注释会被 fetch.py 当参数解析（`split('=',1)` 抛 ValueError），要禁用某源须整行以 `#` 开头。

## Verge 订阅同步
- Verge profiles 目录 `%APPDATA%/.../profiles/` 存**导入时副本**，非软链。
- 本地 `list.meta.yml` 对应 `profiles/LciaAAmThknc.yaml`（uid LciaAAmThknc）；更新后需 `cp` 覆盖该文件，再在 Verge 里启用该订阅。
- 远程订阅 `RYOSM9Zxx0dD`(yml) 走 ghproxy 拉 GitHub peasoft/NoMoreWalls 的 list.meta.yml，同步需 `git push`（gitee 镜像与 GitHub 不同步）。
- 备用机场：SakuraCat（RnTKkRa0K1UT，无到期日）、云鸟（RVhVmnxu1gUR，2026-07 到期注意）。

## 版本与远程
- 远程：`master/master` = 提交 `d656da0`（两个 "q" 提交代码主体一致，仅差 `.idea/`/记忆等）。
- 远程在 gitee，当前网络 `git fetch` 认证失败（terminal prompts disabled），但本地 `remotes/master/master` 引用即最新。
- 还原到远程：`git reset --hard master/master` + `git clean -fdx`（注意 `.idea/` 下 7 个文件是 git 跟踪的，误删需 `git checkout -- .idea/` 恢复）。

## 项目结构要点
- `config.yml`：订阅生成模板（proxies 留空，由 fetch.py 注入）。
- `fetch.py`：抓取源、合并节点、生成 `list.yml`(Clash) / `list.meta.yml`(Meta) / `snippets/*`。
- `serve.py`：面板后端（纯标准库 HTTP），端口 8088；提供 `/` 面板、`/api/status` JSON、`/api/update` 触发 fetch、`/list.meta.yml` 等订阅分发。
- `web/dashboard.html`：深色单页面板（统计卡片 + 订阅链接复制 + 客户端下载 + 地区分布 + 在线更新 + 源抓取详情）。
- `list.meta.yml`：生成的 Meta 订阅；Verge 侧使用 profiles 目录副本。
- 项目有前端：`web/dashboard.html` + `serve.py` 后端，启动方式 `.venv/Scripts/python.exe serve.py`，访问 `http://127.0.0.1:8088`。

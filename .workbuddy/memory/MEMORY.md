# AutoMergePublicNodes 项目长期约定

## 运行 fetch.py 的前提
- **必须存在 `local_proxy.conf`**，内容为 `http://127.0.0.1:7897`（指向 Clash Verge 代理端口）。
- 直连 GitHub raw 会超时导致 0 节点；走 7897 代理才能正常抓取。
- Verge 实际代理端口是 **7897**（config.yml 里 `mixed-port: 7890` 只是订阅生成模板，非运行时端口）。
- 依赖环境：项目内 `.venv/`（Python 3.13 managed），需装 PyYAML / requests / requests-file（requests-file 来自 github.com，需 github 可达）。无 venv 时先 `python -m venv .venv && pip install -r requirements.txt`。

## 配置红线（违反会导致 Verge 加载失败）
- `config.yml` 及生成的 `list.meta.yml` / `list.yml` **不能含 `global-client-fingerprint`**：新版 mihomo 已移除顶层该字段，加载报 "global-client-fingerprint configuration is removed"。fetch.py 只读取不写回此字段，模板无则产物无。
- 生成的订阅里 `✅ 手动选择` 等分组通过 `*id001` 锚点引用全部节点；若节点数为 0 则该锚点为空数组，Verge 报 "use or proxies missing"。

## 版本与远程
- 远程：`master/master` = 提交 `d656da0`（两个 "q" 提交代码主体一致，仅差 `.idea/`/记忆等）。
- 远程在 gitee，当前网络 `git fetch` 认证失败（terminal prompts disabled），但本地 `remotes/master/master` 引用即最新。
- 还原到远程：`git reset --hard master/master` + `git clean -fdx`（注意 `.idea/` 下 7 个文件是 git 跟踪的，误删需 `git checkout -- .idea/` 恢复）。

## 项目结构要点
- `config.yml`：订阅生成模板（proxies 留空，由 fetch.py 注入）。
- `fetch.py`：抓取源、合并节点、生成 `list.yml`(Clash) / `list.meta.yml`(Meta) / `snippets/*`。
- `list.meta.yml`：Verge 实际加载的订阅（serve.py 通过 `http://127.0.0.1:8088/list.meta.yml` 提供）。

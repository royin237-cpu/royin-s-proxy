# 简历项目描述 — Royin Proxy 公益节点聚合平台

> 本文档基于对项目代码的实际分析，提取二次开发贡献点，整理为简历可直接使用的项目描述。

---

## 一、项目信息

| 项 | 内容 |
|----|------|
| **项目名称** | Royin Proxy — 公益代理节点聚合与自动分发平台 |
| **项目类型** | 开源二次开发（基于 [peasoft/NoMoreWalls](https://github.com/peasoft/NoMoreWalls)，MIT/Anti-996 协议） |
| **GitHub** | https://github.com/royin237-cpu/royin-s-proxy |
| **在线 Demo** | https://royin237-cpu.github.io/royin-s-proxy/ |
| **技术栈** | Python 3 / 原生 HTML+CSS+JS / GitHub Actions CI/CD / GitHub Pages |
| **角色** | 独立二次开发者 |

---

## 二、简历项目描述（精简版，适合 1-2 条 bullet）

> **Royin Proxy — 公益代理节点聚合平台**（Python / 前端 / DevOps）
>
> - 基于开源项目二次开发，设计并实现了**可视化数据面板**（原生 HTML/CSS/JS，深色/浅色双主题，响应式布局）、**本地动态后端 API**（Python 标准库 HTTP 服务，线程安全异步任务）和**GitHub Pages 零成本静态部署方案**，将原本仅生成配置文件的脚本工具升级为完整的可视化服务平台。
> - 在节点抓取核心流程中新增 **TCP 存活预检**（150 线程并发连通测试，安全阈值防误杀）和 **mihomo 云端真实测速**（启动临时代理实例，RESTful API 并发延迟测试），将无效节点从最终订阅中过滤；实现**地区交替重排算法**优化 fallback 分组探测效率；针对 iOS 内存限制开发**移动端轻量订阅生成器**。

---

## 三、简历项目描述（详细版，适合项目栏重点展示）

### Royin Proxy — 公益代理节点聚合与自动分发平台

**技术栈：** Python 3, 原生 HTML/CSS/JavaScript, GitHub Actions, GitHub Pages, mihomo (Clash Meta 内核)

**项目背景：** 原项目仅是一个定时抓取公共代理节点、生成 Clash/V2Ray 配置文件的 Python 脚本，无可视化界面、无部署方案、无节点质量检测。在此基础上进行二次开发，将其升级为完整的可视化服务平台。

**主要工作：**

1. **可视化数据面板（前端）**
   - 使用原生 HTML/CSS/JavaScript（无框架依赖）开发单页 Dashboard
   - 实现深色/浅色双主题切换（CSS 变量 + localStorage 持久化）、响应式布局（移动端适配）
   - 功能模块：节点总数/覆盖地区/数据源统计卡片、地区分布网格、订阅链接一键复制（Clipboard API + 降级方案）、客户端下载导航、60 秒自动刷新

2. **本地动态后端（Python 后端）**
   - 使用 Python 标准库 `http.server` 实现单文件 HTTP 服务（端口 8088），零第三方依赖
   - 设计 RESTful API：`/api/status`（节点统计 JSON）、`/api/update`（触发后台抓取）、`/api/update/status`（异步任务进度查询）
   - 线程安全的异步任务机制：全局状态字典 + daemon 线程 + subprocess 超时控制
   - 订阅文件分发（Meta/Clash/V2Ray 三格式 + 配置片段 + CSV 统计）

3. **GitHub Pages 零成本静态部署方案**
   - 设计前后端解耦架构：`gen_status.py` 将动态后端的数据逻辑提取为静态 `status.json`，前端改为 `fetch` 静态 JSON
   - GitHub Actions 定时抓取 → 生成订阅文件 + status.json → git commit 回传 → GitHub Pages 自动部署
   - 全程零服务器成本（Actions 2000 分钟/月免费 + Pages 免费）
   - 编写完整部署文档（DEPLOY.md）

4. **节点质量检测系统（Python 核心增强）**
   - **TCP 存活预检**：对去重后的 (server, port) 地址做并发 TCP 连通测试（150 线程，2.5s 超时），剔除端口不可达的死节点；设 85% 安全阈值，防止网络异常时误杀大量节点
   - **云端真实测速**：在 GitHub Actions runner 上启动临时 mihomo 实例，通过 RESTful API（`/proxies/{name}/delay`）对全部节点并发 generate_204 延迟测试（4s 超时），剔除"端口通但不能代理上网"的无效节点
   - **REALITY 公钥预过滤**：对 trojan-reality 节点的公钥做 base64 合法性校验，防止非法公钥导致 mihomo 整份订阅校验失败

5. **订阅优化算法**
   - **地区交替重排**：fallback 分组中按地区打散节点顺序（每轮每地区取 1 个），确保所有地区尽快各有一个可用节点被探测到，避免同地区节点连续排列导致探测延迟
   - **移动端轻量订阅**（`gen_mobile.py`）：针对 iOS NetworkExtension 内存限制，每地区取少量存活节点 + 极简规则，生成约几十 KB 的轻量订阅，解决完整版订阅导致手机客户端 VPN 崩溃问题

6. **mihomo 内核兼容性修复**
   - 适配新版 mihomo 移除/更名的字段（`global-client-fingerprint` 移除、`fingerprint` → `client-fingerprint`）
   - REALITY 节点强制 `tls: true`、hysteria2 `obfs: none` 清理、ssr obfs 必带 password 等校验
   - 0 节点兜底（`['DIRECT']`），避免空 proxies 数组导致 mihomo 加载失败

---

## 四、面试可能被问到的问题 & 回答要点

### Q1: 你在这个项目里做了什么？和原项目有什么区别？

> 原项目只是一个 Python 脚本，定时抓取公开代理节点源，生成 Clash 和 V2Ray 的配置文件。我在此基础上做了三件事：
> 1. 把它从一个脚本变成了一个**有界面的服务平台**——开发了可视化面板和后端 API，并设计了 GitHub Pages 零成本部署方案；
> 2. 增加了**节点质量检测**——TCP 存活预检和云端 mihomo 真实测速，把无效节点过滤掉，提升用户体验；
> 3. 做了**订阅优化**——地区交替重排让 fallback 探测更快，移动端轻量订阅解决手机崩溃问题。

### Q2: 为什么用原生 HTML 而不是 Vue/React？

> 这个项目的面板本质是数据展示页（统计卡片 + 列表），交互简单，用原生 JS + CSS 变量完全够用。不引入框架的好处是：GitHub Pages 静态部署无构建步骤，HTML 文件直接放仓库根目录即可，部署链路最短，维护成本最低。

### Q3: TCP 预检和 mihomo 测速有什么区别？

> TCP 预检只测端口是否开放（`socket.create_connection`），速度快但无法检测"端口通但不能代理上网"的情况（比如服务端协议过期、被封）。mihomo 测速是启动一个真实的代理内核实例，通过它的 RESTful API 对每个节点发 generate_204 请求测延迟，能检测出协议层面的无效节点。两层过滤，先快后准。

### Q4: 85% 安全阈值是怎么来的？

> 如果一轮预检剔除的死节点超过总数 85%，很可能是当前网络环境异常（比如 GitHub Actions runner 网络波动），而不是节点真的都死了。这时候放弃本轮剔除，保留上一轮的结果，避免把好节点误杀光。这是一个防御性设计。

### Q5: 地区交替重排解决了什么问题？

> Clash 的 fallback 分组会按列表顺序逐个探测节点，选第一个可用的。如果同地区节点连续排列（比如 100 个日本节点排在一起），那么日本节点探测完之前，其他地区一个都不会被选中。交替重排后，第一轮就探测到每个地区各一个节点，所有地区很快都有可用的 fallback。

### Q6: 这个项目有什么技术亮点？

> 1. **零成本架构**：GitHub Actions + Pages，无服务器，永久免费运行；
> 2. **两层质量检测**：TCP 预检（快）+ mihomo 真实测速（准），工程上先快后准的分层过滤思路；
> 3. **前后端解耦**：同一套数据逻辑，动态后端（serve.py）和静态部署（gen_status.py → status.json）两套方案，适配本地开发和云端部署两种场景。

---

## 五、简历撰写建议

1. **诚实标注**：在项目描述中注明"基于开源项目二次开发"，不要把原项目的功能（节点抓取、多格式生成、分流规则）算作自己的。你的贡献是面板、后端、部署方案、质量检测、订阅优化。

2. **量化数据**：如果有数据可以补充（如"聚合 40+ 个节点源"、"每小时自动更新"、"筛选后保留 N 个可用节点"），量化会让描述更有说服力。

3. **准备 Demo 链接**：面试官可能会点开你的 GitHub Pages 链接，确保 `https://royin237-cpu.github.io/royin-s-proxy/` 能正常访问。

4. **准备代码讲解**：面试官可能会问具体代码实现，重点准备：
   - `serve.py` 的异步任务机制（线程 + 全局状态 + subprocess）
   - `fetch.py` 的 `precheck_alive()` 和 `mihomo_speedtest()` 两个函数
   - `interleave_by_region()` 重排算法
   - `gen_status.py` 的前后端解耦思路

5. **不要过度包装**：这个项目的技术深度在于工程实践（CI/CD、零成本架构、分层过滤、兼容性修复），不是算法突破或架构创新。面试时实事求是地讲工程思路和解决问题的过程，比吹"高并发分布式系统"更可信。

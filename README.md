# Royin Proxy

聚合全网免费公共节点，每小时自动更新，生成 Clash / Meta / V2Ray 三格式开箱即用的订阅链接，并附带可视化节点数据面板。

> **来源说明**：本项目基于 [peasoft/NoMoreWalls](https://github.com/peasoft/NoMoreWalls)（及其 fork [chengaopan/AutoMergePublicNodes](https://github.com/chengaopan/AutoMergePublicNodes)）二次开发，沿用 [Anti 996 License](LICENSE.md)，感谢原作者的开源贡献。

## 功能特性

- **自动聚合节点**：GitHub Actions 每小时执行抓取任务，聚合 40+ 个公开节点源，自动去重合并
- **多格式订阅**：同时生成 Clash Meta（`list.meta.yml`）、Clash（`list.yml`）、V2Ray Base64（`list.txt`）三种订阅文件
- **内置分流规则**：Meta 订阅自带分流规则，自动识别被墙域名与国内直连域名
- **可视化面板**：深色单页 Dashboard，展示总节点数、地区分布、各源抓取结果，可在线查看
- **零成本部署**：GitHub Actions + GitHub Pages + raw 链接分发，无需服务器，永久免费

## 在线访问

- 面板（开启 GitHub Pages 后）：`https://royin237-cpu.github.io/royin-s-proxy/`
- Meta 订阅：`https://raw.githubusercontent.com/royin237-cpu/royin-s-proxy/master/list.meta.yml`
- Clash 订阅：`https://raw.githubusercontent.com/royin237-cpu/royin-s-proxy/master/list.yml`
- V2Ray 订阅：`https://raw.githubusercontent.com/royin237-cpu/royin-s-proxy/master/list.txt`
- JsDelivr CDN 加速（可选）：`https://cdn.jsdelivr.net/gh/royin237-cpu/royin-s-proxy@master/list.meta.yml`

## 本地运行

1. 克隆仓库（完整历史较大，建议 `--depth=1`）：
   ```bash
   git clone https://github.com/royin237-cpu/royin-s-proxy.git --depth=1
   ```
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 运行抓取，生成订阅文件：
   ```bash
   python fetch.py
   ```
   如需通过本地代理抓取，在 `local_proxy.conf` 中写入代理地址（如 `http://127.0.0.1:7890`）；直连可用时无需该文件。
4. 启动本地动态面板（可选）：
   ```bash
   python serve.py
   ```
   访问 `http://127.0.0.1:8088`。

## 在线部署（GitHub Pages）

详见 [DEPLOY.md](DEPLOY.md)：GitHub Actions 定时抓取并 commit 回仓库，GitHub Pages 托管纯前端面板，全程零成本。

## 项目结构

| 文件 | 说明 |
|------|------|
| `fetch.py` | 抓取核心脚本：拉取各源、合并去重节点、生成订阅文件 |
| `gen_status.py` | 生成面板统计数据 `web/status.json` |
| `serve.py` | 本地动态面板后端（纯标准库） |
| `web/dashboard.html` | 前端面板 |
| `config.yml` | 订阅生成模板（分流规则、分组配置） |
| `sources.list` | 节点源清单 |
| `snippets/` | 按地区/协议拆分的配置片段 |
| `.github/workflows/fetch.yml` | 每小时定时抓取 + commit 回传 |

## 免责声明

订阅节点均来自互联网公开渠道，仅供学习、研究与交流使用，请勿用于任何违法用途。任何违法行为由使用者自行承担相应法律责任。

## License

[Anti 996 License](LICENSE.md)（继承自原项目）

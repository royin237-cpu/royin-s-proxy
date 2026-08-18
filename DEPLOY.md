# 部署说明 — GitHub Pages 纯静态方案

## 架构

```
GitHub Actions (每小时自动执行)
  ├─ fetch.py        → 抓取节点，生成 list.meta.yml / list.yml / list.txt
  ├─ gen_status.py   → 读取结果，生成 web/status.json
  └─ git commit & push → 所有文件回传仓库

GitHub Pages (静态托管)
  └─ web/dashboard.html → 面板前端
     └─ fetch('status.json') → 读取统计数据展示

raw.githubusercontent.com (订阅分发)
  └─ list.meta.yml / list.yml / list.txt → 订阅链接
```

**零成本**：GitHub Actions（2000 分钟/月免费）、GitHub Pages（免费）、raw.githubusercontent.com（免费）。

## 部署步骤

### 1. 确保仓库已推送到 GitHub

[royin237-cpu/royin-s-proxy](https://github.com/royin237-cpu/royin-s-proxy)

### 2. 开启 GitHub Pages

1. 进入仓库 → **Settings** → **Pages**
2. **Source** 选择 **Deploy from a branch**
3. **Branch** 选择 `master`，文件夹选 `/web`
4. 点击 **Save**
5. 等待 1-2 分钟，访问 `https://royin237-cpu.github.io/royin-s-proxy/`

### 3. 验证

- 面板页面：`https://royin237-cpu.github.io/royin-s-proxy/`
- 状态 JSON：`https://royin237-cpu.github.io/royin-s-proxy/status.json`
- 订阅链接（指向 raw.githubusercontent.com）：
  - Meta: `https://raw.githubusercontent.com/royin237-cpu/royin-s-proxy/master/list.meta.yml`
  - Clash: `https://raw.githubusercontent.com/royin237-cpu/royin-s-proxy/master/list.yml`
  - V2Ray: `https://raw.githubusercontent.com/royin237-cpu/royin-s-proxy/master/list.txt`

### 4. 订阅链接加速（可选）

面板中的订阅链接默认指向 `raw.githubusercontent.com`，国内可能无法直接访问。可在 `dashboard.html` 中修改 `getSubUrl()` 函数，改用 JsDelivr CDN：

```javascript
function getSubUrl(filename) {
  if (window.location.origin.includes('github.io')) {
    return `https://cdn.jsdelivr.net/gh/${REPO_OWNER}/${REPO_NAME}/${REPO_BRANCH}/${filename}`;
  }
  return window.location.origin + '/' + filename;
}
```

## 仓库信息

`dashboard.html` 中的仓库变量已配置为当前仓库，无需修改：

```javascript
let REPO_OWNER = 'royin237-cpu';
let REPO_NAME = 'royin-s-proxy';
let REPO_BRANCH = 'master';
```

## 本地预览

```bash
# 生成 status.json
python gen_status.py

# 在 web/ 目录下启动静态服务
cd web
python -m http.server 8080
# 访问 http://127.0.0.1:8080/dashboard.html
```

## 面试展示要点

1. **架构设计**：CI/CD 自动化（GitHub Actions 定时抓取 → 生成数据 → 自动部署）
2. **前端开发**：纯原生 HTML/CSS/JS，无框架依赖，深色主题，响应式布局
3. **数据可视化**：统计卡片、地区分布、源抓取详情
4. **工程实践**：静态 JSON 数据解耦前后端，GitHub Pages 零成本部署
5. **Python 脚本**：fetch.py 节点抓取合并 + gen_status.py 数据生成

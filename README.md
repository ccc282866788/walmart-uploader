# Walmart Marketplace 上品工具（钢化膜 / 镜头膜专用）

可视化上架沃尔玛商品的前端 + 后端工具，支持：
- 手机钢化膜、镜头膜等 Phone Accessories 类目
- 5 张主图 + 变体 + 5 点特征
- AI 标题 / 描述 / 关键词优化
- 严格匹配沃尔玛官方 API Payload 格式

## 架构

```
浏览器(前端)  ──►  GitHub Pages (静态网页, 免费)
                    │  通过 fetch 调用后端
                    ▼
            Render / Railway (后端, 24h 常驻, 免费额度)
                    │  服务端持有密钥, 调用沃尔玛 API
                    ▼
            Walmart Marketplace API
```

> ⚠️ GitHub Pages **只能托管静态网页**，跑不了 Python 后端。
> 所以网页在 Pages，后端连同一个 GitHub 仓库部署到 Render（常驻运行）。

## 本地运行

```bash
pip install -r requirements.txt
cp .env.example .env        # 填入你的 WALMART_CLIENT_ID / WALMART_CLIENT_SECRET
python app.py               # 访问 http://localhost:10000
```

（已为你生成 `.env`，本地可直接用。`.env` 已被 .gitignore 忽略，不会上传到 GitHub。）

## 部署到 GitHub（网页 + 后端都能跑）

### 1) 把代码推到 GitHub

```bash
git init
git add .
git commit -m "Walmart uploader"
gh auth login              # 浏览器登录你的 GitHub
gh repo create walmart-uploader --public -s . --push
```
（没有 gh 也可以用 GitHub Desktop / 网页上传）

### 2) 部署后端到 Render（常驻运行）

1. 打开 https://render.com → 注册（可用 GitHub 登录）
2. New → **Blueprint** → 连接刚创建的仓库
3. Render 会自动读取 `render.yaml`，创建一个免费 Web 服务
4. 在服务的 **Environment** 里设置：
   - `WALMART_CLIENT_ID` = 你的 Client ID
   - `WALMART_CLIENT_SECRET` = 你的 Client Secret（保密）
   - （可选）`WALMART_PROXY` = 代理地址
5. 部署完成后记下后端地址，例如 `https://walmart-uploader.onrender.com`

### 3) 让前端指向你的后端

编辑 `templates/index.html`，找到文件顶部的 `BACKEND_URL`：

```js
const BACKEND_URL = (function () {
  if (location.hostname.endsWith('github.io')) {
    return "https://walmart-uploader.onrender.com"; // ← 改成第 2 步拿到的后端地址
  }
  return "";
})();
```

把 `https://walmart-uploader.onrender.com` 换成你自己的后端地址，然后 `git push`。

### 4) 开启 GitHub Pages（部署前端）

1. 仓库 **Settings → Pages → Build and deployment → Source 选 "GitHub Actions"**
2. 推送代码后，Actions 会自动把前端发布到 `https://你的用户名.github.io/walmart-uploader/`
3. 打开这个网址即可使用。后端地址会被自动识别并调用。

## 安全性说明

- **Client Secret 只存在于后端环境变量**，绝不写进前端 HTML 或代码。
- 前端输入框留空时，后端自动使用服务器上的环境变量凭证。
- `.env` 已被 `.gitignore` 忽略，推送时不会上传。
- 若仓库设为 **公开**，请勿在前端硬编码任何密钥。

## 文件结构

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 后端（Token / Feed / 库存 / 价格 / 类目 / AI 优化接口） |
| `walmart_sdk.py` | 沃尔玛 API SDK（构造官方 Payload） |
| `ai_optimizer.py` | AI 标题 / 描述 / 关键词优化引擎 |
| `templates/index.html` | 前端界面（纯静态，可上 GitHub Pages） |
| `render.yaml` | Render 后端部署配置 |
| `Dockerfile` | 容器化部署（自托管 / 任意云平台） |
| `.github/workflows/pages.yml` | 自动把前端发布到 GitHub Pages |

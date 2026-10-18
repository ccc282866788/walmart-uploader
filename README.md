# Walmart Marketplace 上品工具（钢化膜 / 镜头膜专用）

可视化上架沃尔玛商品的前端 + 后端工具，支持：
- 手机钢化膜、镜头膜等 Phone Accessories 类目
- 5 张主图 + 变体 + 5 点特征
- AI 标题 / 描述 / 关键词优化
- 严格匹配沃尔玛官方 API Payload 格式

## 架构

后端是 FastAPI（持有密钥、调用沃尔玛 API），前端是纯静态网页。两种部署形态：

**方案 A（推荐，免信用卡）：整体托管到 Hugging Face Spaces**
```
手机/电脑浏览器 ──►  https://你的名-walmart-uploader.hf.space
                        │  前端 + 后端同源一体（Docker 运行 app.py）
                        │  密钥存 Space Secrets，海外机房直连 Walmart（免代理）
                        ▼
                 Walmart Marketplace API
```

**方案 B（需信用卡）：GitHub Pages 前端 + Render 后端**
```
浏览器 ──► GitHub Pages(静态) ──fetch──► Render(后端, 常驻) ──► Walmart API
```

> GitHub Pages 只能托管静态网页，跑不了 Python 后端；Render 等需信用卡验证。

## 本地运行

```bash
pip install -r requirements.txt
cp .env.example .env        # 填入 WALMART_CLIENT_ID / WALMART_CLIENT_SECRET
python app.py               # 访问 http://localhost:10000
```

（本地已生成 `.env`，可直接用。`.env` 已被 `.gitignore` 忽略，不会上传。）

---

## 方案 A：部署到 Hugging Face Spaces（免信用卡，推荐）

HF Spaces 完全免费、无需信用卡，支持 Docker + FastAPI，自带公网 https 地址，手机浏览器直接打开即用。后端放在海外机房，直连 Walmart **连代理都不用配**。

### 1) 拿到代码
代码已在 GitHub：`https://github.com/ccc282866788/walmart-uploader`
（如需本地改代码：`git clone` 后 `git push` 更新。）

### 2) 新建 Space
1. 打开 https://huggingface.co/spaces → 右上角 **New Space**
2. Space name：`walmart-uploader`
3. **SDK 选 `Docker`**（关键，否则不会用我们的 Dockerfile）
4. 可见性选 **Public** 或 **Private** 均可
5. 点 **Create Space**

### 3) 填入密钥（不进代码）
Space 页面 → **Settings → Secrets** → 添加两项：
- `WALMART_CLIENT_ID` = 你的 Client ID
- `WALMART_CLIENT_SECRET` = 你的 Client Secret（保密）

> 密钥只存在 Space Secrets 里，永不进代码、不进 GitHub。

### 4) 连接 GitHub 仓库自动部署
Space 页面 → **Settings → Repository** → 连接 GitHub 仓库 `ccc282866788/walmart-uploader`（分支 `main`）。
连接后 HF 会用仓库里的 `Dockerfile` 构建并运行，访问地址即：
`https://ccc282866788-walmart-uploader.hf.space`

（也可本地用 `huggingface_hub` CLI 推送，效果相同。）

### 5) 使用
手机或电脑浏览器打开上面的 `.hf.space` 地址即可。免费版 Space 长时间无访问会**休眠**，首次打开会有 10~20 秒冷启动，页面顶部会有提示，稍候即可正常使用。

---

## 方案 B：GitHub Pages 前端 + Render 后端（需信用卡）

1. 仓库 **Settings → Pages → Source 选 "Deploy from a branch" → main / (root)**，保存。
2. 打开 https://render.com 注册（需绑定信用卡），New → **Blueprint** → 连接仓库，自动读取 `render.yaml`。
3. 在 Render 服务的 **Environment** 设置 `WALMART_CLIENT_ID` / `WALMART_CLIENT_SECRET`。
4. 部署完拿到后端地址，把 `templates/index.html` 顶部 `BACKEND_URL` 里的 `return ""` 改成该地址，`git push`。
5. 前端在 `https://你的用户名.github.io/walmart-uploader/` 上线。

## 方案 C：自有服务器 / VPS（Docker）

```bash
docker build -t walmart-uploader .
docker run -d -p 10000:7860 \
  -e WALMART_CLIENT_ID=你的ID \
  -e WALMART_CLIENT_SECRET=你的密钥 \
  walmart-uploader
# 访问 http://服务器IP:10000
```

---

## 方案 D：手机零信用卡本地运行（推荐日常用）

云端平台（Render / Hugging Face / Vercel）普遍要信用卡或支付方式验证，可绕开：让工具在你自己的设备上跑，手机直接访问——零成本、零信用卡、密钥留在本地。后端已监听 `0.0.0.0:8765` 并做了 PWA（手机“添加到主屏幕”即全屏 App）。

**D1. 电脑跑后端 + 手机同 WiFi（最快，今天就能用）**
1. 电脑：`pip install -r requirements.txt` → `python app.py`
2. 查电脑局域网 IP（如 `192.168.1.20`）
3. 手机连同一 WiFi，浏览器打开 `http://192.168.1.20:8765`
4. 浏览器菜单“添加到主屏幕”，得到 App 图标，全屏打开

**D2. 安卓手机 Termux 本地独立运行（无需电脑/云）**
1. 手机装 Termux（F-Droid / Google Play，免费）
2. `pkg install python git` → `pip install -r requirements.txt`
3. 把项目传到 Termux（或 `git clone`），`python app.py`
4. 手机浏览器打开 `http://localhost:8765` → 添加到主屏幕

**D3. 任意网络访问（电脑常开 + Cloudflare Tunnel，免费无卡）**
- 电脑跑后端，安装 `cloudflared`，执行 `cloudflared tunnel --url http://localhost:8765` 得到公网 https 地址，手机任意网络可开。

> 国内调用 Walmart API 需在网页“代理”字段填可用代理地址（后端已支持）。

---

## 安全性说明

- **Client Secret 只存在于后端环境变量 / Space Secrets**，绝不写进前端 HTML 或代码。
- 前端输入框留空时，后端自动使用服务器上的环境变量凭证。
- `.env` 已被 `.gitignore` 忽略，推送时不会上传。
- 公开仓库请勿在前端硬编码任何密钥。

## 文件结构

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 后端（Token / Feed / 库存 / 价格 / 类目 / AI 优化接口） |
| `walmart_sdk.py` | 沃尔玛 API SDK（构造官方 Payload） |
| `ai_optimizer.py` | AI 标题 / 描述 / 关键词优化引擎 |
| `templates/index.html` | 前端界面（纯静态，可上 GitHub Pages / HF Spaces） |
| `Dockerfile` | 容器化部署（HF Spaces / Render / 任意云平台均适用，监听 7860） |
| `render.yaml` | Render 后端部署配置（方案 B 用） |
| `.env.example` | 密钥环境变量示例 |

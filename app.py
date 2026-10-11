#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
Walmart Marketplace API 上品工具 — 后端服务
提供真实 API 调用 + Demo 模拟模式
"""

import os
import sys
import json
import time
import uuid
import base64
import asyncio
import random
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# ════════════════════════════════════════════════════════════
# 配置
# ════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROD_URL = "https://marketplace.walmartapis.com"
SANDBOX_URL = "https://sandbox.walmartapis.com"

# 全局状态
state = {
    "credentials": {
        "client_id": "",
        "client_secret": "",
        "channel_type": "",
        "sandbox": False,  # 默认 Production 环境
    },
    "token": None,
    "token_expires": 0,
    "feed_id": None,
    "feed_status_history": [],
    "current_sku": None,
    "demo_mode": True,  # 默认 Demo 模式
    # AI 优化配置
    "ai_api_key": "",
    "ai_base_url": "https://api.openai.com/v1",
    "ai_model": "gpt-4o-mini",
    "ai_mode": "auto",  # auto | builtin | llm
    # 代理配置 (国内用户需要)
    "proxy": "",  # 如 http://127.0.0.1:7890
}

app = FastAPI(title="Walmart Uploader")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# ════════════════════════════════════════════════════════════
# CORS — 允许 GitHub Pages 等前端跨域调用本后端
# ════════════════════════════════════════════════════════════
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
] or ["*"]  # 默认放行所有来源；生产环境可在环境变量里限定你的 GitHub Pages 域名
# 本项目用请求体/Header 传递令牌，不走浏览器 Cookie 凭证，故 credentials 关闭（避免与 "*" 冲突）
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════
def make_correlation_id() -> str:
    return str(uuid.uuid4())


def get_base_url() -> str:
    return SANDBOX_URL if state["credentials"]["sandbox"] else PROD_URL


def make_basic_auth() -> str:
    cid = state["credentials"]["client_id"]
    secret = state["credentials"]["client_secret"]
    raw = f"{cid}:{secret}".encode("utf-8")
    return f"Basic {base64.b64encode(raw).decode('utf-8')}"


def make_headers(access_token: bool = False) -> dict:
    headers = {
        "WM_SVC.NAME": "Walmart Marketplace",
        "WM_QOS.CORRELATION_ID": make_correlation_id(),
        "WM_GLOBAL_VERSION": "3.1",
        "WM_MARKET": "us",
        "accept": "application/json",
    }
    ct = state["credentials"]["channel_type"]
    if ct:
        headers["WM_CONSUMER.CHANNEL.TYPE"] = ct
    if access_token and state["token"]:
        headers["WM_SEC.ACCESS_TOKEN"] = state["token"]
    return headers


def log(msg: str, level: str = "info"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [{level.upper()}] {msg}")


# ════════════════════════════════════════════════════════════
# Demo 模式模拟数据
# ════════════════════════════════════════════════════════════
DEMO_TOKEN = "eyJraWQiOiIzZjVhYTFmNS1hYWE5LTQzMzAtYjEwYy0wMDcxZGMwMDFkMWIiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZW1vLXNlbGxlciIsImV4cCI6OTAwLCJpYXQiOjE3MDF9.demo"
DEMO_FEED_ID = "F129C19240844B97A3C6AD8F1A2C4997@AU8BAQA"
DEMO_FEED_STAGES = ["RECEIVED", "INPROGRESS", "INPROGRESS", "PROCESSED"]

demo_feed_call_count = 0


def demo_get_token():
    return {
        "access_token": DEMO_TOKEN,
        "token_type": "Bearer",
        "expires_in": 900,
    }


def demo_submit_feed(payload):
    global demo_feed_call_count
    demo_feed_call_count = 0
    return {"feedId": DEMO_FEED_ID}


def demo_feed_status(feed_id):
    global demo_feed_call_count
    idx = min(demo_feed_call_count, len(DEMO_FEED_STAGES) - 1)
    status = DEMO_FEED_STAGES[idx]
    demo_feed_call_count += 1

    items_total = 1
    items_succeeded = 1 if status == "PROCESSED" else 0
    items_failed = 0

    return {
        "feedId": feed_id,
        "feedStatus": status,
        "itemsReceived": items_total,
        "itemsProcessing": items_total if status == "INPROGRESS" else 0,
        "itemsProcessed": items_total if status == "PROCESSED" else 0,
        "itemsSucceeded": items_succeeded,
        "itemsFailed": items_failed,
        "ingestionDate": int(time.time() * 1000),
    }


def demo_get_item(sku):
    return {
        "sku": sku,
        "mart": "WALMART_US",
        "productName": "Wireless Bluetooth Headphones (Demo)",
        "brand": "MyBrand",
        "price": {"currency": "USD", "amount": 29.99},
        "publishedStatus": "PUBLISHED",
        "lifecycleStatus": "ACTIVE",
        "wpid": "0TSMMC1ZF383",
        "upc": "123456789012",
        "gtin": "00012345678905",
    }


def demo_update_inventory(sku, quantity):
    return {
        "sku": sku,
        "quantity": {"unit": "EACH", "amount": quantity},
        "fulfillmentCenterId": "FC01",
        "status": "SUCCESS",
    }


def demo_update_price(sku, price):
    return {
        "sku": sku,
        "pricing": {"currentPrice": {"currency": "USD", "amount": price}},
        "status": "SUCCESS",
    }


# ════════════════════════════════════════════════════════════
# API 路由
# ════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/state")
async def get_state():
    return JSONResponse({
        "demo_mode": state["demo_mode"],
        "sandbox": state["credentials"]["sandbox"],
        "has_token": state["token"] is not None,
        "token_expires": state["token_expires"],
        "feed_id": state["feed_id"],
        "current_sku": state["current_sku"],
        "feed_history": state["feed_status_history"],
    })


@app.post("/api/settings")
async def save_settings(request: Request):
    data = await request.json()
    state["credentials"]["client_id"] = data.get("client_id", "")
    state["credentials"]["client_secret"] = data.get("client_secret", "")
    state["credentials"]["channel_type"] = data.get("channel_type", "")
    state["credentials"]["sandbox"] = data.get("sandbox", True)
    state["demo_mode"] = data.get("demo_mode", True)
    state["proxy"] = data.get("proxy", "")

    # 切换模式时清除 token
    state["token"] = None
    state["token_expires"] = 0

    log(f"Settings saved | demo={state['demo_mode']} sandbox={state['credentials']['sandbox']} proxy={'有' if state['proxy'] else '无'}")
    return JSONResponse({"ok": True, "demo_mode": state["demo_mode"]})


@app.post("/api/auth/token")
async def get_token(request: Request):
    """获取 Walmart Access Token — 按官方示例: Basic Auth + grant_type"""
    body = await request.json()

    # 优先用请求体里的凭证；为空则回退到后端环境变量（密钥只在服务器端，不进前端/代码）
    client_id = (body.get("client_id", "") or os.getenv("WALMART_CLIENT_ID", "")).strip()
    client_secret = (body.get("client_secret", "") or os.getenv("WALMART_CLIENT_SECRET", "")).strip()
    sandbox = body.get("sandbox", False)
    if sandbox is False and os.getenv("WALMART_SANDBOX", "").lower() in ("1", "true", "yes"):
        sandbox = True

    # Demo 模式
    if body.get("demo_mode", True):
        resp = demo_get_token()
        state["token"] = resp["access_token"]
        state["token_expires"] = time.time() + resp["expires_in"]
        log("Demo: Token acquired")
        return JSONResponse({"ok": True, "data": resp, "demo": True})

    # 校验凭证
    if not client_id or not client_secret:
        raise HTTPException(400, "缺少 Client ID 或 Client Secret（请在前端填写，或在后端配置 WALMART_CLIENT_ID / WALMART_CLIENT_SECRET 环境变量）")

    # 同步到 state
    state["credentials"]["client_id"] = client_id
    state["credentials"]["client_secret"] = client_secret
    state["credentials"]["sandbox"] = sandbox

    # 代理（请求体优先，回退到环境变量 WALMART_PROXY，方便国内/部署环境统一配置）
    proxy = (body.get("proxy", "") or os.getenv("WALMART_PROXY", "")).strip()
    state["proxy"] = proxy

    # Base64 编码 Client ID:Client Secret
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    basic_auth = f"Basic {base64.b64encode(raw).decode('utf-8')}"

    # 生产环境 URL（官方文档: https://marketplace.walmartapis.com/v3/token）
    base = "https://sandbox.walmartapis.com" if sandbox else "https://marketplace.walmartapis.com"
    url = f"{base}/v3/token"

    # Token 端点只需 3 个 Header（官方示例格式）
    headers = {
        "Authorization": basic_auth,
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    log(f"Token request → {url} (sandbox={sandbox}, proxy={'有' if proxy else '无'})")

    # 代理配置（国内用户需要科学上网）
    proxy_url = proxy if proxy else None

    try:
        async with httpx.AsyncClient(timeout=10, proxy=proxy_url) as client:
            resp = await client.post(url, headers=headers,
                                     data="grant_type=client_credentials")
    except httpx.ConnectTimeout:
        raise HTTPException(504, "连接 Walmart API 超时(10秒)。你可能需要配置代理 — 在设置页填写代理地址。")
    except httpx.ConnectError as e:
        raise HTTPException(502, f"无法连接 Walmart API。请检查网络或配置代理。\n错误: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(500, f"请求异常: {str(e)[:200]}")

    if resp.status_code != 200:
        log(f"Token API error: {resp.status_code} {resp.text[:200]}", "error")
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text[:300]}")

    data = resp.json()
    state["token"] = data["access_token"]
    state["token_expires"] = time.time() + data.get("expires_in", 900)
    log(f"Token acquired, expires in {data.get('expires_in', 900)}s")
    return JSONResponse({"ok": True, "data": data, "demo": False})


@app.post("/api/feed/submit")
async def submit_feed(request: Request):
    data = await request.json()
    payload = data.get("payload")
    sku = data.get("sku", "")
    state["current_sku"] = sku

    if not payload:
        raise HTTPException(400, "缺少 Feed payload")

    if state["demo_mode"]:
        resp = demo_submit_feed(payload)
        state["feed_id"] = resp["feedId"]
        state["feed_status_history"] = []
        log(f"Demo: Feed submitted, feedId={resp['feedId']}, sku={sku}")
        return JSONResponse({"ok": True, "data": resp, "demo": True})

    # 真实 API
    if not state["token"]:
        raise HTTPException(401, "请先获取 Access Token")

    url = f"{get_base_url()}/v3/feeds?feedType=MP_ITEM"
    headers = make_headers(access_token=True)
    headers["Content-Type"] = "application/json"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code not in (200, 201):
        log(f"Feed submit error: {resp.status_code} {resp.text}", "error")
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")

    data = resp.json()
    state["feed_id"] = data.get("feedId")
    state["feed_status_history"] = []
    log(f"Real: Feed submitted, feedId={data.get('feedId')}")
    return JSONResponse({"ok": True, "data": data, "demo": False})


@app.get("/api/feed/status")
async def feed_status():
    feed_id = state["feed_id"]
    if not feed_id:
        raise HTTPException(400, "没有已提交的 Feed，请先提交商品")

    if state["demo_mode"]:
        data = demo_feed_status(feed_id)
        state["feed_status_history"].append({
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "status": data["feedStatus"],
            "succeeded": data["itemsSucceeded"],
            "failed": data["itemsFailed"],
        })
        log(f"Demo: Feed status={data['feedStatus']}")
        return JSONResponse({"ok": True, "data": data, "demo": True, "history": state["feed_status_history"]})

    # 真实 API
    if not state["token"]:
        raise HTTPException(401, "Token 已过期，请重新获取")

    url = f"{get_base_url()}/v3/feeds/{feed_id}"
    headers = make_headers(access_token=True)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params={"includeDetails": "true"})

    if resp.status_code != 200:
        log(f"Feed status error: {resp.status_code} {resp.text}", "error")
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")

    data = resp.json()
    state["feed_status_history"].append({
        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "status": data.get("feedStatus", "UNKNOWN"),
        "succeeded": data.get("itemsSucceeded", 0),
        "failed": data.get("itemsFailed", 0),
    })
    log(f"Real: Feed status={data.get('feedStatus')}")
    return JSONResponse({"ok": True, "data": data, "demo": False, "history": state["feed_status_history"]})


@app.get("/api/item/{sku}")
async def get_item(sku: str):
    if state["demo_mode"]:
        data = demo_get_item(sku)
        log(f"Demo: Get item {sku} -> {data['publishedStatus']}")
        return JSONResponse({"ok": True, "data": data, "demo": True})

    if not state["token"]:
        raise HTTPException(401, "Token 已过期，请重新获取")

    url = f"{get_base_url()}/v3/items/{sku}"
    headers = make_headers(access_token=True)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")

    data = resp.json()
    log(f"Real: Get item {sku}")
    return JSONResponse({"ok": True, "data": data, "demo": False})


@app.post("/api/inventory")
async def update_inventory(request: Request):
    data = await request.json()
    sku = data.get("sku", "")
    quantity = data.get("quantity", 0)
    fc_id = data.get("fulfillment_center_id", "FC01")

    if not sku:
        raise HTTPException(400, "缺少 SKU")

    if state["demo_mode"]:
        resp = demo_update_inventory(sku, quantity)
        log(f"Demo: Inventory updated sku={sku} qty={quantity}")
        return JSONResponse({"ok": True, "data": resp, "demo": True})

    if not state["token"]:
        raise HTTPException(401, "Token 已过期")

    url = f"{get_base_url()}/v3/inventory?sku={sku}"
    headers = make_headers(access_token=True)
    headers["Content-Type"] = "application/json"
    payload = {
        "sku": sku,
        "quantity": {"unit": "EACH", "amount": int(quantity)},
        "fulfillmentCenterId": fc_id,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=headers, json=payload)

    if resp.status_code not in (200, 201):
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")

    log(f"Real: Inventory updated sku={sku} qty={quantity}")
    return JSONResponse({"ok": True, "data": resp.json(), "demo": False})


@app.post("/api/price")
async def update_price(request: Request):
    data = await request.json()
    sku = data.get("sku", "")
    price = data.get("price", 0)
    currency = data.get("currency", "USD")

    if not sku:
        raise HTTPException(400, "缺少 SKU")

    if state["demo_mode"]:
        resp = demo_update_price(sku, float(price))
        log(f"Demo: Price updated sku={sku} price={price}")
        return JSONResponse({"ok": True, "data": resp, "demo": True})

    if not state["token"]:
        raise HTTPException(401, "Token 已过期")

    url = f"{get_base_url()}/v3/price?sku={sku}"
    headers = make_headers(access_token=True)
    headers["Content-Type"] = "application/json"
    payload = {
        "sku": sku,
        "pricing": {"currentPrice": {"currency": currency, "amount": float(price)}},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=headers, json=payload)

    if resp.status_code not in (200, 201):
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")

    log(f"Real: Price updated sku={sku} price={price}")
    return JSONResponse({"ok": True, "data": resp.json(), "demo": False})


# ═══ AI 优化设置 ═══
@app.post("/api/settings/ai")
async def save_ai_settings(request: Request):
    data = await request.json()
    state["ai_api_key"] = (data.get("ai_api_key") or "").strip()
    state["ai_base_url"] = (data.get("ai_base_url") or "https://api.openai.com/v1").strip()
    state["ai_model"] = (data.get("ai_model") or "gpt-4o-mini").strip()
    state["ai_mode"] = data.get("ai_mode", "auto")
    configured = bool(state["ai_api_key"])
    log(f"AI settings saved: configured={configured} mode={state['ai_mode']} model={state['ai_model']}")
    return JSONResponse({
        "ok": True,
        "ai_configured": configured,
        "ai_mode": state["ai_mode"],
        "ai_model": state["ai_model"],
        "ai_base_url": state["ai_base_url"],
    })


@app.get("/api/settings/ai")
async def get_ai_settings():
    configured = bool(state.get("ai_api_key", "").strip())
    return JSONResponse({
        "ok": True,
        "ai_configured": configured,
        "ai_mode": state.get("ai_mode", "auto"),
        "ai_model": state.get("ai_model", "gpt-4o-mini"),
        "ai_base_url": state.get("ai_base_url", "https://api.openai.com/v1"),
    })


# ═══ AI 内容优化 ═══
@app.post("/api/ai/optimize")
async def ai_optimize(request: Request):
    data = await request.json()
    fields = data.get("fields", [])
    context = data.get("context", {})
    mode = data.get("mode", "auto")

    valid_fields = {"title", "short_desc", "long_desc", "key_features"}
    if not fields or not set(fields).issubset(valid_fields):
        raise HTTPException(400, f"无效字段, 可选: {valid_fields}")

    has_key = bool(state.get("ai_api_key", "").strip())
    if mode == "auto":
        use_llm = has_key
    elif mode == "llm":
        if not has_key:
            raise HTTPException(400, "LLM 模式需要 API Key, 请在设置页配置")
        use_llm = True
    else:
        use_llm = False

    try:
        if use_llm:
            from ai_optimizer import llm_optimize
            ai_cfg = {
                "ai_api_key": state["ai_api_key"],
                "ai_base_url": state.get("ai_base_url", "https://api.openai.com/v1"),
                "ai_model": state.get("ai_model", "gpt-4o-mini"),
            }
            result = await llm_optimize(fields, context, ai_cfg)
            mode_used = "llm"
        else:
            from ai_optimizer import AIOptimizer
            opt = AIOptimizer(context.get("category", "Electronics"))
            result = opt.optimize(fields, context)
            mode_used = "builtin"
    except RuntimeError as e:
        log(f"AI optimize error: {e}", "error")
        return JSONResponse({"ok": False, "error": str(e), "code": "LLM_CALL_FAILED"},
                          status_code=400)
    except Exception as e:
        log(f"AI optimize error: {e}", "error")
        return JSONResponse({"ok": False, "error": str(e), "code": "INTERNAL_ERROR"},
                          status_code=500)

    log(f"AI optimize fields={fields} mode={mode_used}")
    return JSONResponse({
        "ok": True,
        "mode_used": mode_used,
        "results": result.get("results", {}),
        "notes": result.get("notes", []),
    })


# ═══ WFS 库存查询 (新版端点) ═══
@app.get("/api/wfs/inventory")
async def get_wfs_inventory(sku: str = None, gtin: str = None,
                            limit: int = 300, offset: int = 0):
    if state["demo_mode"]:
        inv = {
            "sku": sku or "TEST-SKU-001",
            "gtin": "00012345678905",
            "inventory": {
                "fulfillmentCenterId": "FC01",
                "quantity": {"unit": "EACH", "amount": 85},
                "inventoryStatus": "IN_STOCK",
            },
            "lifecycleStatus": "ACTIVE",
            "publishedStatus": "PUBLISHED",
        }
        log(f"Demo: WFS inventory query sku={sku}")
        return JSONResponse({"ok": True, "data": inv, "demo": True})

    if not state["token"]:
        raise HTTPException(401, "Token 已过期")
    url = f"{get_base_url()}/v3/fulfillment/inventory-details"
    params = {"limit": str(limit), "offset": str(offset)}
    if sku: params["sku"] = sku
    if gtin: params["gtin"] = gtin
    headers = make_headers(access_token=True)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")
    log(f"Real: WFS inventory query")
    return JSONResponse({"ok": True, "data": resp.json(), "demo": False})


# ═══ Walmart 官方类目表查询 (Taxonomy API) ═══
@app.get("/api/taxonomy")
async def get_taxonomy():
    """GET /v3/items/taxonomy — 获取 Walmart 官方产品类型全量列表"""
    if state["demo_mode"]:
        # 返回手机相关类目示例
        taxonomy = {
            "category": "Electronics and photography",
            "productTypeGroups": [{
                "productTypeGroup": "Phone accessories",
                "productTypes": [
                    {"productType": "Skins for Cell Phones and Phone Grips", "description": "手机贴膜/皮肤/指环"},
                    {"productType": "Cell Phone Parts", "description": "手机零件（含钢化膜/镜头膜）"},
                    {"productType": "Cell Phone Cases", "description": "手机壳"},
                    {"productType": "Cell Phone Radiation Guards", "description": "防辐射贴"},
                    {"productType": "Car Mounts", "description": "车载支架"},
                    {"productType": "Headsets", "description": "耳机"},
                    {"productType": "Phone Grips", "description": "手机支架/指环"},
                ]
            }]
        }
        log("Demo: Taxonomy query")
        return JSONResponse({"ok": True, "data": taxonomy, "demo": True})

    if not state["token"]:
        raise HTTPException(401, "Token 已过期，请重新获取")
    url = f"{get_base_url()}/v3/items/taxonomy"
    headers = make_headers(access_token=True)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")
    log("Real: Taxonomy query")
    return JSONResponse({"ok": True, "data": resp.json(), "demo": False})


# ═══ 目录搜索 (检查商品是否已存在) ═══
@app.post("/api/catalog/search")
async def catalog_search(request: Request):
    data = await request.json()
    query = data.get("query", "").strip()
    if not query:
        raise HTTPException(400, "请输入搜索关键词")

    if state["demo_mode"]:
        results = {
            "query": query,
            "items": [{
                "gtin": "00012345678905",
                "productName": f"{query} (Catalog Match)",
                "brand": "ExistingBrand",
                "price": {"currency": "USD", "amount": 24.99},
                "mainImageUrl": "https://i5.walmartimages.com/asr/example.jpg",
            }],
        }
        log(f"Demo: Catalog search '{query}'")
        return JSONResponse({"ok": True, "data": results, "demo": True})

    if not state["token"]:
        raise HTTPException(401, "Token 已过期")
    url = f"{get_base_url()}/v3/items/catalog/search"
    headers = make_headers(access_token=True)
    headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json={"query": query})
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")
    log(f"Real: Catalog search '{query}'")
    return JSONResponse({"ok": True, "data": resp.json(), "demo": False})


# ═══ v4 商品完整详情 ═══
@app.get("/api/item/v4/{product_id}")
async def get_item_v4(product_id: str, product_id_type: str = "GTIN",
                      full_details: bool = True):
    if state["demo_mode"]:
        data = {
            "itemResponse": {
                "gtin": "00012345678905",
                "sku": product_id,
                "productName": "Wireless Bluetooth Headphones",
                "brand": "MyBrand",
                "mainImageUrl": "https://example.com/product.jpg",
                "publishedStatus": "PUBLISHED",
                "price": {"amount": 29.99, "currency": "USD"},
                "siteDates": {"siteStartDate": "2025-11-14T15:11:33.19Z"},
                "walmartOrderableAttributes": {"shipMethod": "STANDARD"},
            }
        }
        log(f"Demo: v4 item {product_id}")
        return JSONResponse({"ok": True, "data": data, "demo": True})

    if not state["token"]:
        raise HTTPException(401, "Token 已过期")
    url = f"{get_base_url()}/v4/items/{product_id}"
    headers = make_headers(access_token=True)
    params = {"productIdType": product_id_type,
              "includeFullItemDetails": "YES" if full_details else "NO"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Walmart API Error: {resp.text}")
    log(f"Real: v4 item {product_id}")
    return JSONResponse({"ok": True, "data": resp.json(), "demo": False})


@app.post("/api/feed/build")
async def build_feed(request: Request):
    """根据表单输入构建 Feed JSON — 匹配 Walmart 最新 API Payload 结构"""
    data = await request.json()

    # ── 基础字段 ──
    sku = data.get("sku", "").strip()
    product_name = data.get("product_name", "").strip()
    brand = data.get("brand", "").strip()
    price = float(data.get("price", 0))
    upc = data.get("upc", "").strip()
    gtin = data.get("gtin", "").strip()
    main_image = data.get("main_image", "").strip()
    short_desc = data.get("short_desc", "").strip()
    long_desc = data.get("long_desc", "").strip()
    condition = data.get("condition", "New")
    category = data.get("category", "Electronics")
    product_type = data.get("product_type", "").strip()  # Walmart 产品类型
    quantity = int(data.get("quantity", 0))
    fc_id = data.get("fulfillment_center_id", "FC01")
    spec_version = data.get("spec_version", "5.0.20260205-21_38_48-api")
    business_unit = data.get("business_unit", "WALMART_US")

    # ── 包裹尺寸 & 重量 ──
    pkg_width = data.get("pkg_width")
    pkg_height = data.get("pkg_height")
    pkg_depth = data.get("pkg_depth")
    pkg_weight = data.get("pkg_weight")

    # ── 原产地 ──
    country_of_origin = data.get("country_of_origin", "").strip()

    # ── 合规字段 ──
    material = data.get("material", "").strip()
    warranty_url = data.get("warranty_url", "").strip()
    asin = data.get("asin", "").strip()
    release_date = data.get("release_date", "").strip()

    # ── 5 张图片：主图 + 4 张副图 ──
    additional_images = [img.strip() for img in data.get("additional_images", []) if img and img.strip()]

    # ── 五点特征 (Key Features) ──
    key_features_raw = data.get("key_features", "")
    if isinstance(key_features_raw, list):
        key_features = [f.strip() for f in key_features_raw if f and f.strip()]
    elif isinstance(key_features_raw, str):
        key_features = [f.strip() for f in key_features_raw.split("\n") if f.strip()]
    else:
        key_features = []
    # 补齐到 5 条（不足 5 条会给出提示但允许提交）
    while len(key_features) < 5:
        key_features.append("")

    # ── 变体数据 ──
    variants = data.get("variants", [])
    has_variants = bool(variants)

    # 变体组 ID
    variant_group_id = data.get("variant_group_id", "").strip()
    if has_variants and not variant_group_id:
        variant_group_id = f"VG-{sku}"

    if not sku or not product_name or not brand:
        raise HTTPException(400, "SKU、商品名称、品牌为必填项")

    if not main_image:
        raise HTTPException(400, "主图 URL 为必填项（Walmart 要求至少 1 张主图）")

    # ═══ 构造图片列表 ═══
    all_images = [main_image] + additional_images[:4]  # 最多 5 张

    # ═══ 构造 Visible 公共属性 (按官方实际 Payload) ═══
    def build_visible(cat, v_name, v_brand, v_condition, v_short, v_long,
                      v_main_img, v_addl_imgs, v_features):
        vis_key = product_type if product_type else cat
        vis = {
            vis_key: {
                "brand": v_brand,
                "productName": v_name,
            }
        }
        if v_condition:
            vis[vis_key]["condition"] = v_condition
        if v_main_img:
            vis[vis_key]["mainImageUrl"] = v_main_img
        if v_short:
            vis[vis_key]["shortDescription"] = v_short
        if v_long:
            vis[vis_key]["longDescription"] = v_long
        # 副图 — 官方字段名 productSecondaryImageURL
        addl = [img for img in v_addl_imgs if img]
        if addl:
            vis[vis_key]["productSecondaryImageURL"] = addl
        # 五点特征
        features = [f for f in v_features if f]
        if features:
            vis[vis_key]["keyFeatures"] = features
        # 组装尺寸
        if pkg_width:
            vis[vis_key]["assembledProductWidth"] = {"measure": float(pkg_width), "unit": "in"}
        if pkg_height:
            vis[vis_key]["assembledProductHeight"] = {"measure": float(pkg_height), "unit": "in"}
        if pkg_depth:
            vis[vis_key]["assembledProductLength"] = {"measure": float(pkg_depth), "unit": "in"}
        if pkg_weight:
            vis[vis_key]["assembledProductWeight"] = {"measure": float(pkg_weight), "unit": "lb"}
        # 合规字段 — 匹配官方实际 Payload
        vis[vis_key]["warrantyText"] = "No"
        vis[vis_key]["has_written_warranty"] = "No"
        vis[vis_key]["isProp65WarningRequired"] = "No"
        vis[vis_key]["isCollectible"] = "No"
        vis[vis_key]["smallPartsWarnings"] = ["0 - No warning applicable"]
        vis[vis_key]["state_chemical_disclosure"] = "None"
        vis[vis_key]["netContent"] = {"productNetContentMeasure": 1, "productNetContentUnit": "Each"}
        # 可选合规字段
        if warranty_url:
            vis[vis_key]["warrantyURL"] = warranty_url
        if material:
            vis[vis_key]["material"] = [material]
        # Prop65 警告文本
        vis[vis_key]["prop65WarningText"] = ("California residents: This product can expose you to chemicals "
            "including diethylhexyl phthalate or lead, which are known to the State of California "
            "to cause cancer and birth defects or other reproductive harm. For more information "
            "go to www.P65Warnings.ca.gov.")
        return vis

    # ═══ 构造 Orderable (按官方实际 Payload) ═══
    def build_orderable(v_sku, v_price, v_upc, v_gtin, v_qty, v_fc, v_vg_id, v_vg_attrs):
        od = {
            "specProductType": product_type if product_type else category,
        }
        # 商品标识
        if v_gtin:
            od["productIdentifiers"] = {"productId": v_gtin, "productIdType": "GTIN"}
        elif v_upc:
            od["productIdentifiers"] = {"productId": v_upc, "productIdType": "UPC"}
        # SKU + 价格
        if v_sku:
            od["sku"] = v_sku
        if v_price:
            od["price"] = v_price
        # 运输重量
        if pkg_weight:
            od["ShippingWeight"] = float(pkg_weight)
        # 库存
        if v_qty and int(v_qty) > 0:
            od["inventory"] = {
                "inventoryQuantity": int(v_qty),
                "fulfillmentCenterId": v_fc,
            }
        # 包裹尺寸
        if pkg_width:
            od["productPackageDimensionsWidth"] = float(pkg_width)
        if pkg_height:
            od["productPackageDimensionsHeight"] = float(pkg_height)
        if pkg_depth:
            od["productPackageDimensionsDepth"] = float(pkg_depth)
        if pkg_weight:
            od["productPackageWeight"] = float(pkg_weight)
        # 原产地
        if country_of_origin:
            od["countryOfOriginSubstantialTransformation"] = country_of_origin
        # 合规字段 — 匹配官方实际 Payload
        od["batteryTechnologyType"] = "Does Not Contain a Battery"
        od["electronicsIndicator"] = "No"
        od["chemicalAerosolPesticide"] = "No"
        # 发布日期
        if release_date:
            od["releaseDate"] = release_date
        # 外部产品标识 (ASIN 等)
        if asin:
            od["externalProductIdentifier"] = [{
                "externalProductIdType": "ASIN",
                "externalProductId": asin,
            }]
        # 变体组
        if v_vg_id:
            od["variantGroupId"] = v_vg_id
            if v_vg_attrs:
                od["variantAttributes"] = v_vg_attrs
        return od

    # ═══ 组装 MPItem 列表 ═══
    mp_items = []

    if has_variants:
        # ── 有变体模式：每个变体生成一个 MPItem ──
        for v in variants:
            v_sku = v.get("sku", "").strip()
            v_price = float(v.get("price", price))
            v_upc = v.get("upc", "").strip()
            v_gtin = v.get("gtin", "").strip()
            v_qty = int(v.get("quantity", quantity))
            v_color = v.get("color", "").strip()
            v_size = v.get("size", "").strip()
            v_image = v.get("image", "").strip()

            # 变体属性
            v_attrs = {}
            if v_color:
                v_attrs["color"] = v_color
            if v_size:
                v_attrs["size"] = v_size

            # 变体图片：优先用变体自己的图，否则用公共图
            v_main = v_image if v_image else main_image
            # 变体的副图继承公共副图
            od = build_orderable(v_sku, v_price, v_upc, v_gtin, v_qty, fc_id,
                                 variant_group_id, v_attrs)
            vis = build_visible(category, product_name, brand, condition,
                                short_desc, long_desc, v_main, additional_images, key_features)

            mp_items.append({"Orderable": od, "Visible": vis})

        log(f"Feed built with {len(mp_items)} variants, group={variant_group_id}")

    else:
        # ── 无变体模式：单个 MPItem ──
        od = build_orderable(sku, price, upc, gtin, quantity, fc_id, None, None)
        vis = build_visible(category, product_name, brand, condition,
                            short_desc, long_desc, main_image, additional_images, key_features)
        mp_items.append({"Orderable": od, "Visible": vis})
        log(f"Feed built for SKU={sku}, images={len(all_images)}, features={len([f for f in key_features if f])}")

    # ═══ 组装最终 Feed (匹配官方实际 Payload: items 包装格式) ═══
    feed = {
        "items": [
            {
                "feedType": "MP_ITEM",
                "version": spec_version,
                "productType": product_type if product_type else category,
                "itemSpecPayload": {
                    "MPItemFeedHeader": {
                        "locale": "en",
                        "version": spec_version,
                        "businessUnit": business_unit,
                    },
                    "MPItem": mp_items,
                },
            }
        ]
    }

    # 返回额外信息供前端展示
    return JSONResponse({
        "ok": True,
        "feed": feed,
        "meta": {
            "item_count": len(mp_items),
            "image_count": len(all_images),
            "feature_count": len([f for f in key_features if f]),
            "has_variants": has_variants,
            "variant_group_id": variant_group_id if has_variants else None,
        }
    })


# ════════════════════════════════════════════════════════════
# 启动
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  Walmart Marketplace API 上品工具")
    print("  访问地址: http://localhost:8765")
    print("  Demo 模式: 已启用 (无需真实凭证即可操作)")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8765)

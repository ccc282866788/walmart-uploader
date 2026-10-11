#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
Walmart Marketplace API — 完整 SDK 封装
基于 https://developer.walmart.com/us-marketplace/reference/walmart-multichannel-solutions
覆盖全部 API 端点：认证 / 商品管理 / Feed / 库存 / 价格 / 多渠道方案(MCS) / 订单

用法:
    from walmart_sdk import WalmartClient
    client = WalmartClient(client_id="...", client_secret="...", channel_type="...")
    token = client.get_token()
    feed_id = client.submit_item_feed(feed_payload)
"""

import base64
import json
import time
import uuid
import httpx
from typing import Optional


class WalmartClient:
    """Walmart Marketplace API 完整客户端封装"""

    PROD_URL = "https://marketplace.walmartapis.com"
    SANDBOX_URL = "https://sandbox.walmartapis.com"

    def __init__(self, client_id: str, client_secret: str,
                 channel_type: str = "", sandbox: bool = True):
        self.client_id = client_id
        self.client_secret = client_secret
        self.channel_type = channel_type
        self.base_url = self.SANDBOX_URL if sandbox else self.PROD_URL
        self._token: Optional[str] = None
        self._token_expires: float = 0

    # ════════════════════════════════════════════════════════
    # 内部工具
    # ════════════════════════════════════════════════════════
    def _basic_auth(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        return f"Basic {base64.b64encode(raw).decode('utf-8')}"

    def _corr_id(self) -> str:
        return str(uuid.uuid4())

    def _base_headers(self, with_token: bool = False) -> dict:
        h = {
            "WM_SVC.NAME": "Walmart Marketplace",
            "WM_QOS.CORRELATION_ID": self._corr_id(),
            "WM_GLOBAL_VERSION": "3.1",
            "WM_MARKET": "us",
            "accept": "application/json",
        }
        if self.channel_type:
            h["WM_CONSUMER.CHANNEL.TYPE"] = self.channel_type
        if with_token and self._token:
            h["WM_SEC.ACCESS_TOKEN"] = self._token
        return h

    def _request(self, method: str, path: str, *,
                 params: dict = None, json_body=None, data=None,
                 files=None, extra_headers: dict = None) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = self._base_headers(with_token=True)
        if extra_headers:
            headers.update(extra_headers)
        with httpx.Client(timeout=60) as c:
            return c.request(method, url, params=params, json=json_body,
                             data=data, files=files, headers=headers)

    # ════════════════════════════════════════════════════════
    # 1. 认证 — POST /v3/token
    # ════════════════════════════════════════════════════════
    def get_token(self) -> dict:
        """获取 Access Token (OAuth 2.0 client_credentials, 15分钟有效)"""
        if self._token and time.time() < self._token_expires - 60:
            return {"access_token": self._token, "cached": True}

        # Token 端点只需 accept + content-type + Basic Auth
        # 不要加 WM_SVC.NAME / WM_QOS.CORRELATION_ID, Akamai 会拒绝!
        headers = {
            "Authorization": self._basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
            "accept": "application/json",
        }

        with httpx.Client(timeout=30) as c:
            resp = c.post(f"{self.base_url}/v3/token", headers=headers,
                          data={"grant_type": "client_credentials"})
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 900)
        return data

    # ════════════════════════════════════════════════════════
    # 2. 商品管理 — Feed 提交 / 状态 / 查询 / 下架
    # ════════════════════════════════════════════════════════

    # POST /v3/feeds?feedType=MP_ITEM — 批量上架
    def submit_item_feed(self, feed_payload: dict, feed_type: str = "MP_ITEM") -> dict:
        """提交商品 Feed, 返回 feedId"""
        resp = self._request("POST", f"/v3/feeds",
                            params={"feedType": feed_type},
                            json_body=feed_payload,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # POST /v3/feeds — 文件上传方式
    def submit_feed_file(self, file_path: str, feed_type: str = "MP_ITEM") -> dict:
        """通过文件上传方式提交 Feed"""
        with open(file_path, "rb") as f:
            resp = self._request("POST", "/v3/feeds",
                                params={"feedType": feed_type},
                                files={"file": (file_path, f.read())},
                                extra_headers={"Content-Type": "multipart/form-data"})
        resp.raise_for_status()
        return resp.json()

    # GET /v3/feeds/{feedId} — 查询 Feed 状态
    def get_feed_status(self, feed_id: str, include_details: bool = True) -> dict:
        """轮询 Feed 处理状态"""
        resp = self._request("GET", f"/v3/feeds/{feed_id}",
                            params={"includeDetails": str(include_details).lower()})
        resp.raise_for_status()
        return resp.json()

    def wait_for_feed(self, feed_id: str, interval: int = 15,
                      timeout: int = 7200) -> dict:
        """阻塞等待 Feed 处理完成"""
        start = time.time()
        while time.time() - start < timeout:
            r = self.get_feed_status(feed_id)
            status = r.get("feedStatus", "")
            if status in ("PROCESSED", "ERROR"):
                return r
            time.sleep(interval)
        raise TimeoutError(f"Feed {feed_id} 超时")

    # GET /v3/feeds — 获取所有 Feed 列表
    def get_all_feeds(self, limit: int = 50, offset: int = 0) -> dict:
        """获取 Feed 列表"""
        resp = self._request("GET", "/v3/feeds",
                            params={"limit": str(limit), "offset": str(offset)})
        resp.raise_for_status()
        return resp.json()

    # GET /v3/feeds/{feedId}/report — 下载错误报告
    def get_feed_report(self, feed_id: str) -> dict:
        """获取 Feed 处理详情/错误报告"""
        resp = self._request("GET", f"/v3/feeds/{feed_id}",
                            params={"includeDetails": "true"})
        resp.raise_for_status()
        return resp.json()

    # GET /v3/items — 获取所有商品
    def get_all_items(self, next_cursor: str = "*", limit: int = 20,
                      published_status: str = None,
                      lifecycle_status: str = None) -> dict:
        """分页获取所有商品, 支持 nextCursor 游标分页"""
        params = {"nextCursor": next_cursor, "limit": str(limit)}
        if published_status:
            params["publishedStatus"] = published_status
        if lifecycle_status:
            params["lifecycleStatus"] = lifecycle_status
        resp = self._request("GET", "/v3/items", params=params)
        resp.raise_for_status()
        return resp.json()

    # GET /v3/items/{sku} — 查询单个商品 (v3)
    def get_item(self, sku: str) -> dict:
        """按 SKU 查询单个商品"""
        resp = self._request("GET", f"/v3/items/{sku}")
        resp.raise_for_status()
        return resp.json()

    # GET /v4/items/{productId} — 查询商品完整详情 (v4)
    def get_item_details(self, product_id: str,
                         product_id_type: str = "GTIN",
                         full_details: bool = True) -> dict:
        """v4 端点: 查询商品完整详情 (含 walmartOrderableAttributes, itemConfigurations)"""
        params = {"productIdType": product_id_type,
                  "includeFullItemDetails": "YES" if full_details else "NO"}
        resp = self._request("GET", f"/v4/items/{product_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    # DELETE /v3/items/{sku} — 下架商品
    def retire_item(self, sku: str) -> dict:
        """按 SKU 下架商品"""
        resp = self._request("DELETE", f"/v3/items/{sku}")
        resp.raise_for_status()
        return resp.json()

    # POST /v3/items/catalog/search — 目录搜索
    def catalog_search(self, query: str) -> dict:
        """搜索 Walmart 目录中已有的商品 (用于 MP_ITEM_MATCH)"""
        resp = self._request("POST", "/v3/items/catalog/search",
                            json_body={"query": query})
        resp.raise_for_status()
        return resp.json()

    # GET /v3/items/taxonomy — 获取商品类目树
    def get_taxonomy(self) -> dict:
        """获取 Walmart 产品类型/类目树"""
        resp = self._request("GET", "/v3/items/taxonomy")
        resp.raise_for_status()
        return resp.json()

    # GET /v3/items/count — 按状态统计商品数量
    def get_items_count(self, status: str = None) -> dict:
        """按 publishedStatus 统计商品数量"""
        params = {}
        if status:
            params["publishedStatus"] = status
        resp = self._request("GET", "/v3/items/count", params=params)
        resp.raise_for_status()
        return resp.json()

    # ════════════════════════════════════════════════════════
    # 3. 库存管理
    # ════════════════════════════════════════════════════════

    # PUT /v3/inventory?sku={sku} — 更新单 SKU 库存
    def update_inventory(self, sku: str, quantity: int,
                         fulfillment_center_id: str = "FC01",
                         unit: str = "EACH") -> dict:
        """更新单个 SKU 库存"""
        body = {
            "sku": sku,
            "quantity": {"unit": unit, "amount": quantity},
            "fulfillmentCenterId": fulfillment_center_id,
        }
        resp = self._request("PUT", "/v3/inventory",
                            params={"sku": sku}, json_body=body,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # GET /v3/fulfillment/inventory — WFS 库存 (旧版, 2026弃用)
    def get_wfs_inventory_legacy(self, sku: str = None,
                                 limit: int = 300, offset: int = 0) -> dict:
        """查询 WFS 仓库存 (旧版端点)"""
        params = {"limit": str(limit), "offset": str(offset)}
        if sku:
            params["sku"] = sku
        resp = self._request("GET", "/v3/fulfillment/inventory", params=params)
        resp.raise_for_status()
        return resp.json()

    # GET /v3/fulfillment/inventory-details — WFS 库存 (新版, 推荐使用)
    def get_wfs_inventory(self, sku: str = None, gtin: str = None,
                          limit: int = 300, offset: int = 0) -> dict:
        """查询 WFS 仓库存 (新版端点, 实时库存数据)"""
        params = {"limit": str(limit), "offset": str(offset)}
        if sku:
            params["sku"] = sku
        if gtin:
            params["gtin"] = gtin
        resp = self._request("GET", "/v3/fulfillment/inventory-details", params=params)
        resp.raise_for_status()
        return resp.json()

    # ════════════════════════════════════════════════════════
    # 4. 价格管理
    # ════════════════════════════════════════════════════════

    # PUT /v3/price?sku={sku} — 更新单 SKU 价格
    def update_price(self, sku: str, price: float, currency: str = "USD") -> dict:
        """更新单个 SKU 价格"""
        body = {
            "sku": sku,
            "pricing": {"currentPrice": {"currency": currency, "amount": price}},
        }
        resp = self._request("PUT", "/v3/price",
                            params={"sku": sku}, json_body=body,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # ════════════════════════════════════════════════════════
    # 5. 多渠道方案 (MCS) — Walmart Fulfillment Services
    # ════════════════════════════════════════════════════════

    # POST /v3/fulfillment/orders-fulfillments/channel-details — 创建销售渠道
    def create_mcs_channel(self, channel_name: str,
                           carrier_preferences: str = "packageA",
                           ship_from: dict = None,
                           return_address: dict = None) -> dict:
        """创建 MCS 多渠道销售渠道 (Amazon, eBay, Shein, Temu 等)"""
        mcs_details = {"carrierPreferences": carrier_preferences}
        if channel_name:
            mcs_details["salesChannelName"] = channel_name
        if ship_from:
            mcs_details["shipFromAddress"] = ship_from
        if return_address:
            mcs_details["returnAddress"] = return_address

        body = {"payload": {"mcsDetails": [mcs_details]}}
        resp = self._request("POST", "/v3/fulfillment/orders-fulfillments/channel-details",
                            json_body=body,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # GET /v3/fulfillment/orders-fulfillments/channel-details — 查询销售渠道
    def get_mcs_channels(self) -> dict:
        """获取已创建的 MCS 销售渠道列表"""
        resp = self._request("GET", "/v3/fulfillment/orders-fulfillments/channel-details")
        resp.raise_for_status()
        return resp.json()

    # PUT /v3/fulfillment/orders-fulfillments/channel-details — 更新销售渠道
    def update_mcs_channel(self, channel_id: str, mcs_details: dict) -> dict:
        """更新已有 MCS 销售渠道配置"""
        body = {"payload": {"mcsDetails": [mcs_details]}}
        resp = self._request("PUT", "/v3/fulfillment/orders-fulfillments/channel-details",
                            json_body=body,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # POST /v3/fulfillment/orders-fulfillments — 创建客户订单 (WFS 履约)
    def create_customer_order(self, order_payload: dict) -> dict:
        """创建 MCS 客户订单, WFS 代发货"""
        resp = self._request("POST", "/v3/fulfillment/orders-fulfillments",
                            json_body=order_payload,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # GET /v3/fulfillment/orders-fulfillments — 查询履约订单状态
    def get_fulfillment_order_status(self, limit: int = 50,
                                      purchase_order_no: str = None) -> dict:
        """查询 MCS 履约订单状态 (processing/shipped/canceled)"""
        params = {"limit": str(limit)}
        if purchase_order_no:
            params["purchaseOrderNo"] = purchase_order_no
        resp = self._request("GET", "/v3/fulfillment/orders-fulfillments", params=params)
        resp.raise_for_status()
        return resp.json()

    # POST /v3/fulfillment/orders-fulfillments/cancel — 取消客户订单
    def cancel_customer_order(self, order_id: str, reason: str = "") -> dict:
        """取消 MCS 客户订单 (发货前)"""
        body = {"purchaseOrderNo": order_id, "cancelReason": reason}
        resp = self._request("POST", "/v3/fulfillment/orders-fulfillments/cancel",
                            json_body=body,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # POST /v3/fulfillment/orders-fulfillments/promises — 获取配送承诺(预估到货日)
    def fetch_delivery_promise(self, promise_payload: dict) -> dict:
        """获取配送预估 (到货日期/运输时间)"""
        resp = self._request("POST", "/v3/fulfillment/orders-fulfillments/promises",
                            json_body=promise_payload,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # POST /v3/fulfillment/orders-fulfillments/returns — 创建退货订单
    def create_return_order(self, return_payload: dict) -> dict:
        """创建 MCS 退货订单"""
        resp = self._request("POST", "/v3/fulfillment/orders-fulfillments/returns",
                            json_body=return_payload,
                            extra_headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()

    # GET /v3/fulfillment/orders-fulfillments/returns — 查询退货状态
    def get_return_order_status(self, return_order_id: str = None,
                                limit: int = 50) -> dict:
        """查询 MCS 退货订单状态"""
        params = {"limit": str(limit)}
        if return_order_id:
            params["returnOrderId"] = return_order_id
        resp = self._request("GET", "/v3/fulfillment/orders-fulfillments/returns",
                            params=params)
        resp.raise_for_status()
        return resp.json()

    # ════════════════════════════════════════════════════════
    # 6. Feed 构建器 — 快速生成 Spec 5.0 Feed JSON
    # ════════════════════════════════════════════════════════

    @staticmethod
    def build_item_feed(
        sku: str,
        product_name: str,
        brand: str,
        price: float,
        *,
        upc: str = "",
        gtin: str = "",
        main_image: str = "",
        additional_images: list = None,  # 最多 4 张副图
        short_desc: str = "",
        long_desc: str = "",
        condition: str = "New",
        category: str = "Electronics",
        product_type: str = "",  # Walmart 官方 Taxonomy 产品类型名
        key_features: list = None,  # 五点特征, 5 条
        quantity: int = 0,
        fulfillment_center_id: str = "FC01",
        spec_version: str = "5.0.20260205-21_38_48-api",
        business_unit: str = "WALMART_US",
        # 包裹尺寸 (英寸/磅)
        pkg_width: float = None,
        pkg_height: float = None,
        pkg_depth: float = None,
        pkg_weight: float = None,
        # 原产地
        country_of_origin: str = "",
        # 材质
        material: str = "",
        # 变体
        variants: list = None,
        variant_group_id: str = "",
        # 外部标识
        asin: str = "",
        release_date: str = "",
    ) -> dict:
        """
        构建 MP_ITEM Feed JSON — 匹配 Walmart 最新 API Payload 结构
        输出: {items: [{feedType, version, productType, itemSpecPayload: {MPItemFeedHeader, MPItem}}]}
        """
        pt = product_type if product_type else category  # Visible key / specProductType

        # ── 五点特征 ──
        kf = key_features or []
        while len(kf) < 5:
            kf.append("")

        # ── 商品标识 ──
        product_identifiers = {}
        if gtin:
            product_identifiers = {"productId": gtin, "productIdType": "GTIN"}
        elif upc:
            product_identifiers = {"productId": upc, "productIdType": "UPC"}

        # ── 图片 ──
        addl_imgs = [img for img in (additional_images or []) if img][:4]

        # ── 构造 Visible ──
        def make_visible(v_main_img=None):
            v_img = v_main_img or main_image
            vis = {pt: {
                "brand": brand,
                "productName": product_name,
            }}
            if condition:
                vis[pt]["condition"] = condition
            if v_img:
                vis[pt]["mainImageUrl"] = v_img
            if short_desc:
                vis[pt]["shortDescription"] = short_desc
            if long_desc:
                vis[pt]["longDescription"] = long_desc
            if addl_imgs:
                vis[pt]["productSecondaryImageURL"] = addl_imgs
            features = [f for f in kf if f]
            if features:
                vis[pt]["keyFeatures"] = features
            # 组装尺寸
            if pkg_width is not None:
                vis[pt]["assembledProductWidth"] = {"measure": pkg_width, "unit": "in"}
            if pkg_height is not None:
                vis[pt]["assembledProductHeight"] = {"measure": pkg_height, "unit": "in"}
            if pkg_depth is not None:
                vis[pt]["assembledProductLength"] = {"measure": pkg_depth, "unit": "in"}
            if pkg_weight is not None:
                vis[pt]["assembledProductWeight"] = {"measure": pkg_weight, "unit": "lb"}
            # 合规字段 — 匹配官方实际 Payload
            vis[pt]["warrantyText"] = "No"
            vis[pt]["has_written_warranty"] = "No"
            vis[pt]["isProp65WarningRequired"] = "No"
            vis[pt]["isCollectible"] = "No"
            vis[pt]["smallPartsWarnings"] = ["0 - No warning applicable"]
            vis[pt]["state_chemical_disclosure"] = "None"
            vis[pt]["netContent"] = {"productNetContentMeasure": 1, "productNetContentUnit": "Each"}
            if material:
                vis[pt]["material"] = [material]
            vis[pt]["prop65WarningText"] = (
                "California residents: This product can expose you to chemicals "
                "including diethylhexyl phthalate or lead, which are known to the State of California "
                "to cause cancer and birth defects or other reproductive harm. For more information "
                "go to www.P65Warnings.ca.gov."
            )
            return vis

        # ── 构造 Orderable ──
        def make_orderable(v_sku, v_price, v_upc="", v_gtin="",
                           v_qty=0, v_vg_id=None, v_vg_attrs=None):
            od = {
                "specProductType": pt,
            }
            v_pi = {}
            if v_gtin:
                v_pi = {"productId": v_gtin, "productIdType": "GTIN"}
            elif v_upc:
                v_pi = {"productId": v_upc, "productIdType": "UPC"}
            elif product_identifiers:
                v_pi = product_identifiers
            if v_pi:
                od["productIdentifiers"] = v_pi
            if v_sku:
                od["sku"] = v_sku
            if v_price:
                od["price"] = v_price
            # 运输重量
            if pkg_weight is not None:
                od["ShippingWeight"] = pkg_weight
            # 库存
            if v_qty and int(v_qty) > 0:
                od["inventory"] = {
                    "inventoryQuantity": int(v_qty),
                    "fulfillmentCenterId": fulfillment_center_id,
                }
            # 包裹尺寸
            if pkg_width is not None:
                od["productPackageDimensionsWidth"] = pkg_width
            if pkg_height is not None:
                od["productPackageDimensionsHeight"] = pkg_height
            if pkg_depth is not None:
                od["productPackageDimensionsDepth"] = pkg_depth
            if pkg_weight is not None:
                od["productPackageWeight"] = pkg_weight
            # 原产地
            if country_of_origin:
                od["countryOfOriginSubstantialTransformation"] = country_of_origin
            # 合规字段 — 匹配官方实际 Payload
            od["batteryTechnologyType"] = "Does Not Contain a Battery"
            od["electronicsIndicator"] = "No"
            od["chemicalAerosolPesticide"] = "No"
            # 外部标识 (ASIN)
            if asin:
                od["externalProductIdentifier"] = [{
                    "externalProductIdType": "ASIN",
                    "externalProductId": asin,
                }]
            # 发布日期
            if release_date:
                od["releaseDate"] = release_date
            # 变体
            if v_vg_id:
                od["variantGroupId"] = v_vg_id
                if v_vg_attrs:
                    od["variantAttributes"] = v_vg_attrs
            return od

        # ── 组装 MPItem ──
        mp_items = []
        if variants:
            vg_id = variant_group_id or f"VG-{sku}"
            for v in variants:
                v_attrs = {}
                if v.get("color"):
                    v_attrs["color"] = v["color"]
                if v.get("size"):
                    v_attrs["size"] = v["size"]
                v_img = v.get("image", "")
                od = make_orderable(
                    v["sku"], float(v.get("price", price)),
                    v.get("upc", ""), v.get("gtin", ""),
                    int(v.get("quantity", quantity)),
                    vg_id, v_attrs
                )
                vis = make_visible(v_img or main_image)
                mp_items.append({"Orderable": od, "Visible": vis})
        else:
            od = make_orderable(sku, price, upc, gtin, quantity)
            vis = make_visible()
            mp_items.append({"Orderable": od, "Visible": vis})

        # ── items 包装格式 (匹配官方实际 Payload) ──
        return {
            "items": [
                {
                    "feedType": "MP_ITEM",
                    "version": spec_version,
                    "productType": pt,
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


# ════════════════════════════════════════════════════════════════════════
# 完整使用示例 — 端到端上品流程
# ════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # ── 初始化 ──
    client = WalmartClient(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
        channel_type="YOUR_CHANNEL_TYPE",
        sandbox=True,  # 先在 sandbox 测试
    )

    # ── 1. 认证 ──
    token = client.get_token()
    print(f"[1] Token: {token['access_token'][:30]}...")

    # ── 2. 查询 WFS 库存 (检查现有库存) ──
    wfs_inv = client.get_wfs_inventory(sku="TEST-SKU-001")
    print(f"[2] WFS Inventory: {wfs_inv}")

    # ── 3. 目录搜索 (检查商品是否已存在) ──
    # catalog = client.catalog_search("Wireless Bluetooth Headphones")
    # print(f"[3] Catalog: {catalog}")

    # ── 4. 构建 Feed (钢化膜示例 — items 包装格式) ──
    feed = WalmartClient.build_item_feed(
        sku="SP-IP15PM-01",
        product_name="iPhone 15 Pro Max Tempered Glass Screen Protector",
        brand="ScreenGuard",
        price=9.99,
        gtin="00670212404900",
        main_image="https://example.com/img1.jpg",
        additional_images=[
            "https://example.com/img2.jpg",
            "https://example.com/img3.jpg",
            "https://example.com/img4.jpg",
            "https://example.com/img5.jpg",
        ],
        short_desc="Premium tempered glass screen protector with 9H hardness",
        long_desc="Protect your iPhone with premium tempered glass...",
        condition="New",
        category="Phone Accessories",
        product_type="Skins for Cell Phones and Phone Grips",  # 官方 Taxonomy
        material="Tempered Glass",
        key_features=[
            "9H Hardness military grade tempered glass, scratch and shatter resistant",
            "Oleophobic coating, anti-fingerprint and smudge-resistant",
            "Bubble-free installation with alignment frame",
            "Ultra-thin design maintains original touch sensitivity and HD clarity",
            "Case-friendly edge-to-edge full coverage for iPhone 15 Pro Max",
        ],
        quantity=100,
        fulfillment_center_id="FC01",
        pkg_width=3.0,
        pkg_height=6.0,
        pkg_depth=0.15,
        pkg_weight=0.05,
        country_of_origin="CN",
    )
    print(f"[4] Feed format: {list(feed.keys())}")  # 应输出 ['items']

    # ── 5. 提交 Feed ──
    result = client.submit_item_feed(feed)
    feed_id = result["feedId"]
    print(f"[5] Feed submitted: {feed_id}")

    # ── 6. 轮询状态 ──
    status = client.wait_for_feed(feed_id, interval=15, timeout=3600)
    print(f"[6] Feed status: {status.get('feedStatus')}")
    print(f"    Succeeded: {status.get('itemsSucceeded')}, Failed: {status.get('itemsFailed')}")

    # ── 7. 查询商品 ──
    item = client.get_item("TEST-SKU-001")
    print(f"[7] Item: {item.get('publishedStatus', 'N/A')}")

    # ── 8. v4 完整详情 ──
    # item_full = client.get_item_details("00012345678905", "GTIN")
    # print(f"[8] Full details: {item_full}")

    # ── 9. 设置库存 ──
    inv = client.update_inventory("TEST-SKU-001", 100, "FC01")
    print(f"[9] Inventory updated")

    # ── 10. 设置价格 ──
    pr = client.update_price("TEST-SKU-001", 29.99)
    print(f"[10] Price updated")

    # ═══ MCS 多渠道示例 (需要 WFS 商品) ═══
    # ── 11. 创建 MCS 销售渠道 ──
    # channel = client.create_mcs_channel(
    #     channel_name="My Website",
    #     ship_from={"name": "Warehouse", "address1": "123 Main St",
    #                 "city": "Bentonville", "state": "AR", "postalCode": "72712",
    #                 "country": "US"},
    # )
    # print(f"[11] MCS Channel: {channel}")

    # ── 12. 获取配送预估 ──
    # promise = client.fetch_delivery_promise({
    #     "sku": "TEST-SKU-001",
    #     "quantity": 1,
    #     "shipToPostalCode": "10001",
    # })
    # print(f"[12] Delivery promise: {promise}")

    # ── 13. 创建客户订单 (WFS 代发) ──
    # order = client.create_customer_order({
    #     "purchaseOrderNo": "PO-001",
    #     "shipToAddress": {...},
    #     "lineItems": [{"sku": "TEST-SKU-001", "quantity": 1}],
    # })
    # print(f"[13] Order created: {order}")

    print("\n✅ 流程完成!")

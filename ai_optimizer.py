#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
Walmart 商品内容 AI 优化引擎
- 内置模式: 基于 Walmart 最佳实践规则，零外部依赖
- LLM 模式: 调用 OpenAI 兼容 API 生成更自然内容
"""

import re
import json
import httpx
from typing import Optional

# ════════════════════════════════════════════════════════════
# 1. 类目关键词字典
# ════════════════════════════════════════════════════════════
CATEGORY_KEYWORDS = {
    "Electronics": {
        "product_types": ["Headphones","Speaker","Keyboard","Mouse","Charger","Cable","Webcam","Earbuds","Monitor","Headset","Microphone","Router"],
        "features": ["Bluetooth","Wireless","USB-C","Rechargeable","Noise Cancelling","Fast Charging","LED","Digital","Waterproof","HD","4K","Smart"],
        "specs": ["Battery","Wattage","Voltage","Resolution","mAh","GHz","dB","Hours"],
        "colors": ["Black","White","Blue","Red","Silver","Gray","Gold"],
        "modifiers": ["Premium","Portable","Compact","Ultra-Light","Professional"],
        "use_cases": ["travel","work","gaming","everyday listening","office use"],
    },
    "Home": {
        "product_types": ["Pillow","Blanket","Cookware","Knife Set","Storage Bin","Lamp","Rug","Towel","Organizer","Shelf","Curtain","Mug"],
        "features": ["Non-Slip","Machine Washable","Stainless Steel","BPA-Free","Heat Resistant","Waterproof","Eco-Friendly","Anti-Slip","Durable"],
        "specs": ["Thread Count","Capacity","Diameter","Wattage","Dimensions","Pieces"],
        "colors": ["Beige","Charcoal","Navy","Sage Green","Ivory","White","Brown"],
        "modifiers": ["Modern","Minimalist","Eco-Friendly","Heavy Duty","Premium"],
        "use_cases": ["daily use","home decor","kitchen","bedroom","bathroom"],
    },
    "Clothing": {
        "product_types": ["T-Shirt","Hoodie","Jeans","Dress","Jacket","Socks","Leggings","Polo","Sweater","Shorts"],
        "features": ["Cotton Blend","Moisture Wicking","Stretch","Quick-Dry","UV Protection","Breathable","Fleece","Ribbed"],
        "specs": ["Size","Fabric Weight","Thread Count"," inseam"],
        "colors": ["Heather Gray","Olive","Burgundy","Black","White","Navy"],
        "modifiers": ["Casual","Athletic","Premium","Everyday","Slim Fit"],
        "use_cases": ["casual wear","workout","everyday use","layering"],
    },
    "Toys": {
        "product_types": ["Building Blocks","Action Figure","Puzzle","Board Game","Doll","Play Set","RC Car","Stuffed Animal"],
        "features": ["Educational","STEM","Non-Toxic","BPA-Free","Age-Appropriate","Interactive","Collectible"],
        "specs": ["Recommended Age","Piece Count","Dimensions"],
        "colors": ["Multi-color","Primary","Rainbow"],
        "modifiers": ["Interactive","Collectible","Premium","Fun"],
        "use_cases": ["learning","playtime","gift","collecting"],
    },
    "Sports": {
        "product_types": ["Yoga Mat","Dumbbell","Water Bottle","Resistance Band","Jump Rope","Foam Roller","Kettlebell"],
        "features": ["Eco-Friendly TPE","Anti-Slip","Sweat-Proof","Lightweight","Non-Toxic","Durable"],
        "specs": ["Weight","Length","Thickness","Capacity"],
        "colors": ["Black","Teal","Magenta","Blue","Green"],
        "modifiers": ["Pro Grade","Portable","Heavy Duty"],
        "use_cases": ["home gym","yoga","fitness","outdoor"],
    },
    "Beauty": {
        "product_types": ["Serum","Cream","Shampoo","Brush Set","Mirror","Cleanser","Lotion","Mask"],
        "features": ["Vegan","Cruelty-Free","Hypoallergenic","Fragrance-Free","SPF","Organic","Natural"],
        "specs": ["Volume","Shade","Count"],
        "colors": ["Clear","Natural","Pink"],
        "modifiers": ["Glow","Hydrating","Anti-Aging"],
        "use_cases": ["daily skincare","beauty routine","travel"],
    },
    "Grocery": {
        "product_types": ["Coffee","Snack","Spice","Oil","Tea","Sauce","Cereal","Nuts"],
        "features": ["Organic","Non-GMO","Gluten-Free","Sugar-Free","Single-Origin","Artisan","Natural"],
        "specs": ["Net Weight","Count","Servings"],
        "colors": ["Natural","Golden","Brown"],
        "modifiers": ["Artisan","Premium","Gourmet"],
        "use_cases": ["daily consumption","cooking","gifting"],
    },
    # ═══ 手机配件（钢化膜 / 镜头膜）═══
    "Phone Accessories": {
        "product_types": [
            "Tempered Glass Screen Protector","Screen Protector","Privacy Screen Protector",
            "Camera Lens Protector","Lens Protector","Rear Camera Protector",
            "Full Coverage Screen Protector","Edge-to-Edge Screen Protector",
            "Matte Screen Protector","HD Clear Screen Protector",
        ],
        "features": [
            "9H Hardness","Anti-Scratch","Shatterproof","Oleophobic Coating",
            "Anti-Fingerprint","Bubble-Free Installation","Case-Friendly",
            "Ultra Clear","HD Transparent","Matte Anti-Glare","Privacy Anti-Spy",
            "Blue Light Filter","Eye Protection","No Flash Interference",
            "Night Shot Compatible","Aluminum Alloy Frame","Full Adhesive",
            "High Sensitivity","Touch Friendly","Dust-Free",
        ],
        "specs": [
            "0.33mm","0.26mm","0.15mm","9H","2.5D Curved Edge","3D Curved Edge",
            "6-Layer","4-Pack","2-Pack","3-Pack","Ultra-Thin",
        ],
        "colors": ["Clear","Black","HD Clear","Matte","Privacy"],
        "modifiers": [
            "Premium","Ultra-Thin","Military Grade","High Definition",
            "Full Coverage","Edge-to-Edge","Pro Grade","MilitaryShield",
        ],
        "use_cases": [
            "daily phone protection","scratch protection","drop protection",
            "privacy protection","screen protection","camera protection",
        ],
        # 手机型号关键词（用于标题和关键词扩展）
        "phone_models": [
            "iPhone 15 Pro Max","iPhone 15 Pro","iPhone 15 Plus","iPhone 15",
            "iPhone 14 Pro Max","iPhone 14 Pro","iPhone 14 Plus","iPhone 14",
            "iPhone 13 Pro Max","iPhone 13 Pro","iPhone 13","iPhone 12 Pro Max",
            "iPhone SE","Samsung Galaxy S23 Ultra","Samsung Galaxy S23",
            "Samsung Galaxy S22 Ultra","Samsung Galaxy S21","Google Pixel 7 Pro",
            "Google Pixel 7","Google Pixel 6 Pro",
        ],
        # Walmart 高搜索量关键词
        "search_keywords": [
            "tempered glass screen protector","phone screen protector",
            "9H screen protector","privacy screen protector",
            "camera lens protector","anti scratch screen protector",
            "shatterproof screen protector","bubble free screen protector",
            "case friendly screen protector","full coverage screen protector",
            "HD clear screen protector","oleophobic coating",
            "iPhone screen protector","Samsung screen protector",
            "phone lens protector","rear camera protector",
        ],
    },
}

DEFAULT_CATEGORY = {
    "product_types": [],
    "features": ["Premium","Quality","Durable"],
    "specs": [],
    "colors": ["Black","White"],
    "modifiers": ["Premium"],
    "use_cases": ["everyday use"],
}

# ════════════════════════════════════════════════════════════
# 2. 停用词
# ════════════════════════════════════════════════════════════
STOP_WORDS = {"the","a","an","and","with","for","of","to","in","on","at","by","or","is","it","this","that","from","your","our"}

# ════════════════════════════════════════════════════════════
# 3. 内置优化引擎
# ════════════════════════════════════════════════════════════
class AIOptimizer:
    """基于 Walmart 最佳实践的商品内容优化引擎"""

    MAX_TITLE = 75
    MIN_TITLE = 50
    MAX_DESC = 1000
    MAX_KF = 120

    def __init__(self, category: str = "Electronics"):
        self.category = category if category in CATEGORY_KEYWORDS else "Electronics"
        self.kw = CATEGORY_KEYWORDS.get(self.category, DEFAULT_CATEGORY)

    def optimize(self, fields: list, context: dict) -> dict:
        """主入口: 根据指定 fields 优化对应内容"""
        results = {}
        notes = []
        if "title" in fields:
            r = self._opt_title(context)
            results["title"] = r
            notes.append(f"Title length {len(r['optimized'])} chars (target 50-75)")
            notes.append(f"Keywords extracted: {len(r.get('keywords', []))}")
        if "short_desc" in fields:
            r = self._opt_short_desc(context)
            results["short_desc"] = r
            notes.append(f"Short description {len(r['optimized'])} chars (max 1000)")
        if "long_desc" in fields:
            r = self._opt_long_desc(context)
            results["long_desc"] = r
            notes.append(f"Long description {len(r['optimized'])} chars")
        if "key_features" in fields:
            r = self._opt_key_features(context)
            results["key_features"] = r
            notes.append(f"Key features: {len(r['optimized'])} bullets generated")
        return {"results": results, "notes": notes}

    # ──────────────────────────────────────────────
    # 标题优化: [Brand] [PhoneModel] [ProductType] [KeyFeature] [Spec]
    #           或 [Brand] [ProductType] [KeyFeature] [Spec] [Color]
    # ──────────────────────────────────────────────
    def _opt_title(self, ctx: dict) -> dict:
        original = ctx.get("title", "")
        brand = ctx.get("brand", "")
        category = ctx.get("category", self.category)

        # 识别产品类型
        ptype = self._extract_product_type(original)
        # 提取关键特征
        key_feat = self._extract_key_feature(ctx)
        # 提取规格
        spec = self._extract_spec(original, ctx)
        # 提取颜色
        color = self._extract_color(original + " " + ctx.get("long_desc", ""))

        # 组装 — 手机配件类目特殊处理: 加入手机型号
        if self.category == "Phone Accessories":
            phone_model = self._extract_phone_model(original + " " + ctx.get("long_desc", ""))
            # 优先级: Brand > PhoneModel > ProductType > KeyFeat > Spec
            parts = [p for p in [brand, phone_model, ptype, key_feat, spec] if p]
            title = " ".join(parts)

            # 长度不足时补充 modifier
            if len(title) < self.MIN_TITLE:
                mod = self.kw["modifiers"][0] if self.kw["modifiers"] else "Premium"
                title = f"{brand} {phone_model} {mod} {ptype}"
                if key_feat:
                    title += f" {key_feat}"
                if len(title) < self.MIN_TITLE:
                    title += f" {spec}" if spec else ""
                    if len(title) < self.MIN_TITLE and self.kw["use_cases"]:
                        title += f" for {self.kw['use_cases'][0]}"
        else:
            # 通用类目
            parts = [p for p in [brand, ptype, key_feat, spec, color] if p]
            title = " ".join(parts)

            if len(title) < self.MIN_TITLE:
                mod = self.kw["modifiers"][0] if self.kw["modifiers"] else "Premium"
                title = f"{brand} {mod} {ptype}"
                if key_feat:
                    title += f" {key_feat}"
                if color:
                    title += f" {color}"
                if len(title) < self.MIN_TITLE and self.kw["use_cases"]:
                    title += f" for {self.kw['use_cases'][0]}"

        # 长度裁剪
        if len(title) > self.MAX_TITLE:
            # 先去 spec
            if spec:
                title_no_spec = " ".join(p for p in title.split() if p not in spec.split())
                if len(title_no_spec) >= self.MIN_TITLE:
                    title = title_no_spec
            if len(title) > self.MAX_TITLE:
                title = title[:self.MAX_TITLE].rsplit(" ", 1)[0]

        # 首字母大写 — 但保留 iPhone/Samsung 等已有大小写的词
        title_words = []
        for w in title.split():
            wl = w.lower()
            # 保留特殊品牌词的大小写
            if wl == "iphone": title_words.append("iPhone")
            elif wl == "samsung": title_words.append("Samsung")
            elif wl == "galaxy": title_words.append("Galaxy")
            elif wl == "google": title_words.append("Google")
            elif wl == "pixel": title_words.append("Pixel")
            # 已有混合大小写 (如 iPhone, USB-C) 或全大写 (如 9H, HD) 或含数字 → 保留
            elif (any(c.isupper() for c in w[1:]) if len(w) > 1 else False) or w.isupper() or any(c.isdigit() for c in w):
                title_words.append(w)
            else:
                title_words.append(w.capitalize())
        title = " ".join(title_words)

        keywords = self._extract_keywords(title)
        return {"original": original, "optimized": title, "keywords": keywords}

    def _extract_phone_model(self, text: str) -> str:
        """从文本中识别手机型号"""
        text_lower = text.lower()
        for model in self.kw.get("phone_models", []):
            if model.lower() in text_lower:
                return model
        return ""

    # ──────────────────────────────────────────────
    # 短描述优化
    # ──────────────────────────────────────────────
    def _opt_short_desc(self, ctx: dict) -> dict:
        original = ctx.get("short_desc", "")
        brand = ctx.get("brand", "")
        ptype = self._extract_product_type(ctx.get("title", ""))
        key_feat = self._extract_key_feature(ctx)
        use_case = self.kw["use_cases"][0] if self.kw["use_cases"] else "everyday use"

        # 模板: 以产品类型开头 (SEO), 包含品牌和核心特征
        desc = f"{ptype} by {brand}"
        if key_feat:
            desc += f" featuring {key_feat}"
        use_case_str = use_case if isinstance(use_case, str) else use_case[0]
        desc += f". Perfect for {use_case_str}."
        # 补充类目特征词
        if self.kw["features"]:
            desc += f" {self.kw['features'][0]} design ensures quality and reliability."

        if len(desc) > self.MAX_DESC:
            desc = desc[:self.MAX_DESC].rsplit(" ", 1)[0] + "."
        return {"original": original, "optimized": desc}

    # ──────────────────────────────────────────────
    # 长描述优化 (结构化)
    # ──────────────────────────────────────────────
    def _opt_long_desc(self, ctx: dict) -> dict:
        original = ctx.get("long_desc", "")
        brand = ctx.get("brand", "")
        ptype = self._extract_product_type(ctx.get("title", ""))
        key_feat = self._extract_key_feature(ctx)
        features = self._get_all_features(ctx)
        use_case = self.kw["use_cases"][0] if self.kw["use_cases"] else "everyday use"

        # 结构: 段落1 (简介) + 段落2 (核心优势) + 列表 + 段落3 (应用场景)
        parts = []
        parts.append(f"The {brand} {ptype} delivers {key_feat.lower() if key_feat else 'exceptional performance'}.")

        if features:
            parts.append("Key Benefits:")
            for f in features[:5]:
                parts.append(f"  - {f}")

        parts.append(f"Perfect for {use_case}.")
        parts.append(f"Backed by {brand} quality guarantee.")

        desc = "\n".join(parts)
        if len(desc) > self.MAX_DESC:
            desc = desc[:self.MAX_DESC]
        return {"original": original, "optimized": desc}

    # ──────────────────────────────────────────────
    # 五点特征生成
    # ──────────────────────────────────────────────
    def _opt_key_features(self, ctx: dict) -> dict:
        original = ctx.get("key_features", [])
        if isinstance(original, str):
            original = [original]
        brand = ctx.get("brand", "")
        title = ctx.get("title", "")
        ptype = self._extract_product_type(title)
        features = self._get_all_features(ctx)
        spec = self._extract_spec(title, ctx)
        color = self._extract_color(title + " " + ctx.get("long_desc", ""))

        # ═══ 手机配件 (钢化膜/镜头膜) 专用五点特征 ═══
        if self.category == "Phone Accessories":
            is_lens = "lens" in ptype.lower() or "camera" in ptype.lower()
            bullets = self._gen_phone_protector_features(ctx, is_lens)
            bullets = [self._truncate(b, self.MAX_KF) for b in bullets]
            return {"original": original, "optimized": bullets}

        # ═══ 通用类目五点特征 ═══
        bullets = []
        # 1. 核心功能
        f1 = features[0] if features else (self.kw["features"][0] if self.kw["features"] else "Premium quality")
        bullets.append(f"{f1} for superior performance and reliability")
        # 2. 规格/续航
        if spec:
            bullets.append(f"{spec} ensures extended usage and consistent results")
        else:
            s = self.kw["specs"][0] if self.kw["specs"] else "Quality"
            bullets.append(f"{s} designed for long-lasting durability")
        # 3. 连接/兼容
        if "Bluetooth" in str(features) or "Wireless" in str(features):
            bullets.append("Wireless connectivity with seamless device pairing")
        elif self.kw["features"]:
            f3 = self.kw["features"][1] if len(self.kw["features"]) > 1 else self.kw["features"][0]
            bullets.append(f"{f3} technology for enhanced user experience")
        # 4. 设计/舒适
        mod = self.kw["modifiers"][0] if self.kw["modifiers"] else "Ergonomic"
        if color:
            bullets.append(f"{mod} design in {color}, built for comfort and style")
        else:
            bullets.append(f"{mod} design, built for comfort and portability")
        # 5. 品牌/品质
        use_case = self.kw["use_cases"][0] if self.kw["use_cases"] else "everyday use"
        bullets.append(f"{brand} guaranteed quality, perfect for {use_case}")

        bullets = [self._truncate(b, self.MAX_KF) for b in bullets]
        return {"original": original, "optimized": bullets}

    def _gen_phone_protector_features(self, ctx: dict, is_lens: bool = False) -> list:
        """生成钢化膜/镜头膜专用五点特征"""
        brand = ctx.get("brand", "")
        phone_model = self._extract_phone_model(ctx.get("title", "") + " " + ctx.get("long_desc", ""))
        spec = self._extract_spec(ctx.get("title", ""), ctx)
        title_lower = ctx.get("title", "").lower()
        features = ctx.get("key_features", [])

        if is_lens:
            # ═══ 镜头膜五点特征 ═══
            b1 = "9H Hardness tempered glass protects camera lens from scratches and drops"
            b2 = "No flash interference - maintains original photo and video quality"
            b3 = "Night Shot compatible design, no halo effect on night mode photos"
            if spec:
                b4 = f"{spec} ultra-thin design, seamless fit without affecting camera performance"
            else:
                b4 = "Ultra-thin seamless fit, does not affect camera performance or phone case fit"
            b5 = f"{brand} premium quality lens protector"
            if phone_model:
                b5 += f" for {phone_model}"
            b5 += ", easy installation with included alignment tool"
        else:
            # ═══ 钢化膜五点特征 ═══
            # 检测是否有特定特征关键词
            has_privacy = "privacy" in title_lower
            has_matte = "matte" in title_lower
            has_blue_light = "blue light" in title_lower

            b1 = "9H Hardness military grade tempered glass, scratch and shatter resistant"
            if has_privacy:
                b2 = "Privacy anti-spy technology, screen only visible from front, hidden from sides"
            elif has_matte:
                b2 = "Matte anti-glare finish, reduces fingerprints and reflections for clear viewing"
            elif has_blue_light:
                b2 = "Blue light filter and eye protection, reduces eye strain from extended screen time"
            else:
                b2 = "Oleophobic coating, anti-fingerprint and smudge-resistant, easy to clean"

            b3 = "Bubble-free installation with alignment frame, easy to apply in seconds"
            if spec:
                b4 = f"{spec} ultra-thin design maintains original touch sensitivity and HD clarity"
            else:
                b4 = "Ultra-thin design maintains original touch sensitivity and HD clarity"

            b5 = f"Case-friendly edge-to-edge full coverage"
            if phone_model:
                b5 += f" designed for {phone_model}"
            b5 += f". {brand} quality guaranteed"

        return [b1, b2, b3, b4, b5]

    # ──────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────
    def _extract_product_type(self, text: str) -> str:
        """从标题中识别产品类型"""
        text_lower = text.lower()
        for pt in self.kw["product_types"]:
            if pt.lower() in text_lower:
                return pt
        # 如果没命中，取标题前 2 个实义词
        words = [w for w in text.split() if w.lower() not in STOP_WORDS and len(w) > 2]
        return " ".join(words[:2]) if words else "Product"

    def _extract_key_feature(self, ctx: dict) -> str:
        """提取核心特征"""
        kfs = ctx.get("key_features", [])
        if kfs and isinstance(kfs, list) and kfs:
            first = kfs[0]
            if isinstance(first, str) and first.strip():
                # 取前 3 个词
                words = first.split()
                return " ".join(words[:4])
        # 从类目特征词中找
        if self.kw["features"]:
            for f in self.kw["features"]:
                if f.lower() in ctx.get("title", "").lower():
                    return f
            return self.kw["features"][0]
        return ""

    def _extract_spec(self, title: str, ctx: dict) -> str:
        """从标题/描述中提取规格信息"""
        text = title + " " + ctx.get("long_desc", "") + " " + ctx.get("short_desc", "")
        # 匹配 数字+单位
        patterns = [
            r"(\d+[\.\d]*)\s*[-]?\s*hour", r"(\d+[\.\d]*)\s*[-]?\s*min",
            r"(\d+[\.\d]*)\s*[-]?\s*mAh", r"(\d+[\.\d]*)\s*[-]?\s*W",
            r"(\d+[\.\d]*)\s*[-]?\s*inch", r"(\d+[\.\d]*)\s*[-]?\s*lb",
            r"(\d+[\.\d]*)\s*[-]?\s*oz", r"Bluetooth\s+([\d\.]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(1) if m.lastindex else m.group(0)
                unit = re.search(r"(hour|min|mAh|W|inch|lb|oz)", text[m.start():m.end()+10], re.IGNORECASE)
                if unit:
                    return f"{val}-{unit.group(1)}"
                return val
        return ""

    def _extract_color(self, text: str) -> str:
        """从文本中提取颜色"""
        text_lower = text.lower()
        for color in self.kw["colors"]:
            if color.lower() in text_lower:
                return color
        return ""

    def _get_all_features(self, ctx: dict) -> list:
        """获取所有特征词"""
        feats = []
        kfs = ctx.get("key_features", [])
        if isinstance(kfs, list):
            feats = [f for f in kfs if isinstance(f, str) and f.strip()]
        # 从标题中匹配类目特征词
        title_lower = ctx.get("title", "").lower()
        for f in self.kw["features"]:
            if f.lower() in title_lower and f not in feats:
                feats.append(f)
        return feats if feats else self.kw["features"][:3]

    def _extract_keywords(self, text: str) -> list:
        """从文本中提取关键词"""
        words = re.split(r"[\s,/\-]+", text.lower())
        keywords = []
        for w in words:
            if len(w) < 2 or w in STOP_WORDS:
                continue
            # 与类目字典交集
            all_kw = (self.kw["product_types"] + self.kw["features"] +
                     self.kw["specs"] + self.kw["colors"] + self.kw["modifiers"])
            for dk in all_kw:
                if w == dk.lower() and w not in keywords:
                    keywords.append(w)
        # 补充类目关键词
        for f in self.kw["features"][:3]:
            if f.lower() not in keywords:
                keywords.append(f.lower())
        # 手机配件: 补充高搜索量关键词和手机型号
        if self.category == "Phone Accessories":
            # 加入 search_keywords
            for sk in self.kw.get("search_keywords", [])[:3]:
                if sk.lower() not in keywords:
                    keywords.append(sk.lower())
            # 加入手机型号
            phone_model = self._extract_phone_model(text)
            if phone_model and phone_model.lower() not in keywords:
                keywords.append(phone_model.lower())
        return keywords[:10]

    def _extract_spec(self, title: str, ctx: dict) -> str:
        """从标题/描述中提取规格信息"""
        text = title + " " + ctx.get("long_desc", "") + " " + ctx.get("short_desc", "")
        # 通用: 数字+单位
        patterns = [
            r"(\d+[\.\d]*)\s*[-]?\s*hour", r"(\d+[\.\d]*)\s*[-]?\s*min",
            r"(\d+[\.\d]*)\s*[-]?\s*mAh", r"(\d+[\.\d]*)\s*[-]?\s*W",
            r"(\d+[\.\d]*)\s*[-]?\s*inch", r"(\d+[\.\d]*)\s*[-]?\s*lb",
            r"(\d+[\.\d]*)\s*[-]?\s*oz", r"Bluetooth\s+([\d\.]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(1) if m.lastindex else m.group(0)
                unit = re.search(r"(hour|min|mAh|W|inch|lb|oz)", text[m.start():m.end()+10], re.IGNORECASE)
                if unit:
                    return f"{val}-{unit.group(1)}"
                return val
        # 手机配件: 厚度 (0.33mm 等) 和 9H
        if self.category == "Phone Accessories":
            m = re.search(r"(\d+[\.\d]*)\s*mm", text, re.IGNORECASE)
            if m:
                return f"{m.group(1)}mm"
            if "9H" in text.upper():
                return "9H"
            if re.search(r"\d-pack|\d pack", text, re.IGNORECASE):
                m = re.search(r"(\d+)\s*[-]?\s*pack", text, re.IGNORECASE)
                if m:
                    return f"{m.group(1)}-Pack"
        return ""

    def _truncate(self, s: str, n: int) -> str:
        if len(s) <= n:
            return s
        return s[:n].rsplit(" ", 1)[0]


# ════════════════════════════════════════════════════════════
# 4. LLM 调用 (OpenAI 兼容)
# ════════════════════════════════════════════════════════════
LLM_SYSTEM_PROMPT = """You are a Walmart Marketplace product content optimizer.
Apply Walmart best practices strictly:
- Title: [Brand] [Product Type] [Key Feature] [Spec] [Color], 50-75 chars
- Short description: SEO-optimized, lead keyword in first 30 chars, max 1000 chars
- Long description: structured with features and benefits, max 1000 chars
- Key features: exactly 5 benefit-focused bullet points, each under 100 chars
Always respond in English (Walmart US marketplace).
Respond ONLY with valid JSON, no markdown fences, no explanation.
JSON format:
{"title":{"optimized":"","keywords":["",""]},"short_desc":{"optimized":""},"long_desc":{"optimized":""},"key_features":{"optimized":["","","","",""]}}
Only include fields that were requested."""


async def llm_optimize(fields: list, context: dict, ai_config: dict) -> dict:
    """调用 OpenAI 兼容 API 进行 LLM 优化"""
    user_prompt = _build_llm_prompt(fields, context)

    payload = {
        "model": ai_config.get("ai_model", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }
    # 部分 API 支持 response_format
    if "deepseek" not in ai_config.get("ai_base_url", "").lower():
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {ai_config['ai_api_key']}",
        "Content-Type": "application/json",
    }
    url = ai_config.get("ai_base_url", "https://api.openai.com/v1").rstrip("/") + "/chat/completions"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        raise RuntimeError(f"LLM API {resp.status_code}: {resp.text[:300]}")

    content = resp.json()["choices"][0]["message"]["content"]
    # 清理可能的 markdown fence
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    data = json.loads(content)
    return _normalize_llm_output(data, fields, context)


def _build_llm_prompt(fields: list, context: dict) -> str:
    """构建 LLM 用户 prompt"""
    field_names = {
        "title": "Title (product name)",
        "short_desc": "Short description",
        "long_desc": "Long description",
        "key_features": "5 Key Features (bullet points)",
    }
    fields_str = ", ".join(field_names.get(f, f) for f in fields)
    context_json = json.dumps({
        "current_title": context.get("title", ""),
        "brand": context.get("brand", ""),
        "category": context.get("category", "Electronics"),
        "current_short_desc": context.get("short_desc", ""),
        "current_long_desc": context.get("long_desc", ""),
        "current_key_features": context.get("key_features", []),
        "price": context.get("price", ""),
    }, ensure_ascii=False, indent=2)
    return f"Optimize the following fields: {fields_str}\n\nProduct context:\n{context_json}\n\nReturn JSON with optimized content for each requested field."


def _normalize_llm_output(data: dict, fields: list, context: dict) -> dict:
    """归一化 LLM 输出, 确保格式一致"""
    results = {}
    notes = []

    if "title" in fields:
        t = data.get("title", {})
        if isinstance(t, str):
            t = {"optimized": t, "keywords": []}
        results["title"] = {
            "original": context.get("title", ""),
            "optimized": t.get("optimized", ""),
            "keywords": t.get("keywords", []),
        }
        notes.append(f"LLM title: {len(results['title']['optimized'])} chars")

    if "short_desc" in fields:
        s = data.get("short_desc", {})
        if isinstance(s, str):
            s = {"optimized": s}
        results["short_desc"] = {
            "original": context.get("short_desc", ""),
            "optimized": s.get("optimized", ""),
        }

    if "long_desc" in fields:
        l = data.get("long_desc", {})
        if isinstance(l, str):
            l = {"optimized": l}
        results["long_desc"] = {
            "original": context.get("long_desc", ""),
            "optimized": l.get("optimized", ""),
        }

    if "key_features" in fields:
        k = data.get("key_features", {})
        if isinstance(k, list):
            k = {"optimized": k}
        opt = k.get("optimized", [])
        # 强制 5 条
        while len(opt) < 5:
            opt.append("Premium quality guaranteed")
        opt = opt[:5]
        results["key_features"] = {
            "original": context.get("key_features", []),
            "optimized": opt,
        }

    return {"results": results, "notes": notes}


# ════════════════════════════════════════════════════════════
# 5. 测试入口
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ctx = {
        "title": "Wireless Bluetooth Headphones",
        "brand": "MyBrand",
        "category": "Electronics",
        "price": "29.99",
        "short_desc": "Great headphones",
        "long_desc": "Some description",
        "key_features": ["Active noise cancellation", "30-hour battery", "Bluetooth 5.2", "Memory foam", "Built-in mic"],
    }
    opt = AIOptimizer("Electronics")
    result = opt.optimize(["title", "short_desc", "long_desc", "key_features"], ctx)
    print(json.dumps(result, indent=2, ensure_ascii=False))

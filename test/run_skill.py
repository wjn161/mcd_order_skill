#!/usr/bin/env python3
"""
麦当劳点餐 Skill 本地执行脚本
直接调用真实 MCP 服务（https://mcp.mcd.cn）+ order_helper.py

用法：
  export MCD_MCP_TOKEN=your_token
  python3 test/run_skill.py

脚本会交互式地带着你走完一次完整点餐流程：
  选地址 → 查菜单 → 选菜 → 计算价格 → 确认 → 下单
也可以单独查询营养/活动。
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "mcd_order" / "scripts" / "order_helper.py"
MCP_URL = "https://mcp.mcd.cn"


# ── 工具函数 ─────────────────────────────────────────────────────────────────

def get_token():
    return os.environ.get("MCD_MCP_TOKEN", "").strip()


def _parse_mcp_text(text: str):
    """
    MCP 服务返回的 content[0].text 是 Markdown 说明 + 真实 JSON（可能后面还有文本）。
    找到 JSON 起始位置后，用 JSONDecoder.raw_decode 只解析第一个完整对象。
    """
    decoder = json.JSONDecoder()
    for start_char, search in [('{"success":', '{"success":'), ('[{', '[{'), ('{', '{')]:
        idx = text.find(search)
        if idx == -1:
            continue
        try:
            obj, _ = decoder.raw_decode(text, idx)
            return obj
        except json.JSONDecodeError:
            continue
    # last fallback
    return json.loads(text.strip())


def mcp_call_raw(tool_name: str, arguments: dict = None) -> str:
    """向 MCP 服务发起工具调用，直接返回 content[0].text 原始字符串（不解析 JSON）"""
    token = get_token()
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }).encode()
    req = urllib.request.Request(
        MCP_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            envelope = json.loads(resp.read())
        if "error" in envelope:
            raise RuntimeError(f"MCP 错误：{envelope['error']}")
        return envelope["result"]["content"][0]["text"]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("\n[错误] Token 无效或已过期，请重新设置 MCD_MCP_TOKEN")
        elif e.code == 429:
            print("\n[错误] 请求过于频繁，请稍等 30 秒后重试")
        else:
            print(f"\n[错误] HTTP {e.code}：{e.reason}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n[错误] 无法连接 MCP 服务：{e.reason}")
        sys.exit(1)


def _get_time_slot(hour: int) -> str:
    """根据小时数返回时段名称"""
    if 6 <= hour <= 10:
        return "breakfast"
    if 11 <= hour <= 16:
        return "lunch"
    if 17 <= hour <= 21:
        return "dinner"
    return "dinner"


def mcp_call(tool_name: str, arguments: dict = None) -> dict:
    """向真实 MCP 服务发起工具调用，返回解析后的业务数据"""
    token = get_token()
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }).encode()
    req = urllib.request.Request(
        MCP_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            envelope = json.loads(resp.read())
        if "error" in envelope:
            raise RuntimeError(f"MCP 错误：{envelope['error']}")
        text = envelope["result"]["content"][0]["text"]
        return _parse_mcp_text(text)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("\n[错误] Token 无效或已过期，请重新设置 MCD_MCP_TOKEN")
        elif e.code == 429:
            print("\n[错误] 请求过于频繁，请稍等 30 秒后重试")
        else:
            print(f"\n[错误] HTTP {e.code}：{e.reason}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n[错误] 无法连接 MCP 服务：{e.reason}")
        sys.exit(1)


def run_helper(*args) -> str:
    """运行 order_helper.py，返回 stdout"""
    env = os.environ.copy()
    env["MCD_MCP_TOKEN"] = get_token()
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0 and result.stderr:
        print(f"[脚本错误] {result.stderr}", file=sys.stderr)
    return result.stdout.strip()


def ask(prompt: str) -> str:
    """带提示的用户输入"""
    try:
        return input(f"\n{prompt} > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        sys.exit(0)


def choose(prompt: str, options: list, label_fn=None) -> int:
    """让用户从列表中选一项，返回索引"""
    print(f"\n{prompt}")
    for i, item in enumerate(options):
        label = label_fn(item) if label_fn else str(item)
        print(f"  {i + 1}. {label}")
    while True:
        raw = ask(f"请输入序号（1-{len(options)}）")
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"  请输入 1 到 {len(options)} 之间的数字")


def hr(char="─", width=48):
    print(char * width)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def step_check_config():
    """Step 0：检查配置"""
    print("\n🍔  麦当劳点餐助手（本地执行模式）")
    hr("=")
    out = run_helper("check-config")
    data = json.loads(out)
    if not data["ok"]:
        print("\n[提示] MCD_MCP_TOKEN 未配置，获取步骤如下：\n")
        for step in data["steps"]:
            print(f"  {step}")
        print()
        sys.exit(0)
    print("✓ Token 已配置，连接麦当劳 MCP 服务...")


def step_choose_address() -> dict:
    """Step 1：选择配送地址"""
    print("\n【Step 1】查询配送地址...")
    resp = mcp_call("delivery-query-addresses")
    # 真实接口：resp["data"]["addresses"]
    addresses = resp.get("data", {}).get("addresses", resp) if isinstance(resp, dict) else resp

    if not addresses:
        print("  暂无已保存地址，请输入新地址：")
        name = ask("收件人姓名")
        phone = ask("手机号")
        detail = ask("详细地址（省市区+街道门牌）")
        new_resp = mcp_call("delivery-create-address", {
            "contactName": name, "phone": phone, "fullAddress": detail
        })
        addr_id = new_resp.get("data", {}).get("addressId", "")
        print(f"  ✓ 地址已保存（ID: {addr_id}）")
        return {"addressId": addr_id, "contactName": name, "phone": phone, "fullAddress": detail}

    def fmt_addr(a):
        store = f"  [{a.get('storeName','')}]" if a.get("storeName") else ""
        return f"{a.get('fullAddress', a.get('detail',''))}  {a.get('contactName', a.get('name',''))} {a.get('phone','')}{store}"

    idx = choose("请选择配送地址：", addresses, fmt_addr)
    return addresses[idx]


def step_browse_menu(address: dict) -> list:
    """Step 2：查看菜单，让用户选菜"""
    store_code = address.get("storeCode", "")
    print(f"\n【Step 2】查询菜单（门店：{address.get('storeName', store_code)}）...")
    resp = mcp_call("query-meals", {"storeCode": store_code})
    data = resp.get("data", resp) if isinstance(resp, dict) else resp

    categories = data.get("categories", [])
    meals_map = data.get("meals", {})  # code -> {name, currentPrice, ...}

    # 展示菜单（跳过分类名重复的，合并展示）
    all_items = []
    seen_cats = set()
    for cat in categories:
        cat_name = cat["name"]
        is_first = cat_name not in seen_cats
        seen_cats.add(cat_name)
        if is_first:
            print(f"\n  ── {cat_name} ──")
        for m in cat["meals"]:
            code = m["code"]
            info = meals_map.get(code, {})
            name = info.get("name", code)
            price = info.get("currentPrice", "?")
            tags = "/".join(t for t in m.get("tags", []) if t) or ""
            tag_str = f"  [{tags}]" if tags else ""
            idx = len(all_items) + 1
            print(f"    {idx:3}. {name:<28} ¥{price}{tag_str}")
            all_items.append({"code": code, "name": name, "price": price, "quantity": 1})

    # 选菜
    print()
    cart = []
    print("  输入序号添加菜品，输入 0 完成选择")
    while True:
        raw = ask(f"选择菜品（序号 1-{len(all_items)}，0=完成）")
        if raw == "0":
            if not cart:
                print("  购物车为空，请至少选一件商品")
                continue
            break
        if raw.isdigit() and 1 <= int(raw) <= len(all_items):
            item = dict(all_items[int(raw) - 1])
            qty_raw = ask(f"  {item['name']} 数量")
            item["quantity"] = int(qty_raw) if qty_raw.isdigit() and int(qty_raw) > 0 else 1
            cart.append(item)
            print(f"  ✓ 已添加：{item['name']} × {item['quantity']}")
        else:
            print(f"  请输入 0 到 {len(all_items)} 之间的数字")

    print("\n  购物车：")
    for item in cart:
        try:
            subtotal = float(item['price']) * item['quantity']
            print(f"    · {item['name']} × {item['quantity']}  ¥{subtotal:.2f}")
        except (ValueError, TypeError):
            print(f"    · {item['name']} × {item['quantity']}")
    return cart


def step_calculate_price(cart: list, address: dict) -> dict:
    """Step 3：计算价格（价格单位：分）"""
    print("\n【Step 3】计算订单金额...")
    items = [{"productCode": item["code"], "quantity": item["quantity"]} for item in cart]

    price_resp = mcp_call("calculate-price", {
        "storeCode": address.get("storeCode", ""),
        "beCode": address.get("beCode", ""),
        "items": items,
    })
    return price_resp.get("data", price_resp) if isinstance(price_resp, dict) else {}


def step_confirm(cart: list, price: dict, address: dict) -> bool:
    """Step 4：展示订单摘要，等待用户确认（价格单位：分 → 转换为元）"""
    print("\n【Step 4】订单确认\n")

    # 展示商品清单（来自 price.productList 或 cart）
    product_list = price.get("productList", [])
    if product_list:
        print("  购物清单：")
        for p in product_list:
            subtotal = p.get("subtotal", 0) / 100
            print(f"    · {p['productName']} × {p['quantity']}  ¥{subtotal:.2f}")
    else:
        print("  购物清单：")
        for item in cart:
            print(f"    · {item['name']} × {item['quantity']}")

    # 价格明细（分 → 元）
    def fen(v): return f"¥{int(v)/100:.2f}" if v is not None else "?"
    print(f"\n  价格明细：")
    print(f"    商品金额：{fen(price.get('productOriginalPrice'))}")
    if price.get("productOriginalPrice") != price.get("productPrice"):
        print(f"    商品折后：{fen(price.get('productPrice'))}")
    print(f"    配送费：  {fen(price.get('deliveryPrice'))}")
    if price.get("packingPrice"):
        print(f"    打包费：  {fen(price.get('packingPrice'))}")
    print(f"    ────────────────────")
    print(f"    实付金额：{fen(price.get('price'))}")

    print(f"\n  配送至：{address.get('fullAddress', '')}  {address.get('contactName', '')} {address.get('phone', '')}")

    ans = ask("\n确认下单？（y=确认 / n=取消）").lower()
    return ans in ("y", "yes", "是", "确认")


def step_create_order(address: dict, cart: list):
    """Step 5：创建订单，成功后生成支付二维码"""
    print("\n【Step 5】提交订单...")
    items = [{"productCode": item["code"], "quantity": item["quantity"]} for item in cart]

    order_resp = mcp_call("create-order", {
        "addressId": address.get("addressId", ""),
        "storeCode": address.get("storeCode", ""),
        "beCode": address.get("beCode", ""),
        "items": items,
    })
    order = order_resp.get("data", order_resp) if isinstance(order_resp, dict) else {}
    order_id = order.get("orderId") or order.get("order_id", "")
    pay_url = order.get("payUrl") or order.get("payment_url", "")

    if not order_resp.get("success"):
        print(f"\n⚠️  下单失败：{order_resp.get('message', '未知错误')}（code: {order_resp.get('code')}）\n")
        return

    print(f"\n✅ 订单创建成功！订单号：{order_id}")

    if not pay_url:
        print("  （未返回支付链接）")
        return

    # 生成支付二维码
    print("  生成支付二维码...")
    qr_out = run_helper("gen-pay-qr", "--pay-url", pay_url)
    try:
        qr_data = json.loads(qr_out)
    except (json.JSONDecodeError, ValueError):
        print(f"  支付链接：{pay_url}")
        return

    if not qr_data.get("ok"):
        print(f"  支付链接：{qr_data.get('pay_url', pay_url)}")
        print(f"  [提示] {qr_data.get('error', '二维码生成失败')}")
        return

    print(f"  支付地址：{qr_data['pay_url']}")

    if qr_data.get("mode") == "image":
        qr_path = qr_data["qr_path"]
        print(f"  二维码已保存：{qr_path}")
        # macOS 自动打开图片
        import subprocess as _sp
        _sp.run(["open", qr_path], check=False)
        print("  （二维码图片已在系统查看器中打开，请扫码支付）")
    else:
        # ASCII 二维码直接打印
        print("\n  请扫描以下二维码支付：\n")
        print(qr_data.get("ascii_qr", ""))


def step_choose_meal_mode() -> list | None:
    """步骤 0：选择点餐模式，返回预设购物车或 None（自由选菜）"""
    print("\n【步骤 0】选择点餐模式")
    print("  1. 默认套餐（按时段自动选）")
    print("  2. 按热量搭配（从菜单智能组合）")
    print("  3. 自由选菜")
    while True:
        raw = ask("请选择（1/2/3）")
        if raw in ("1", "2", "3"):
            break
        print("  请输入 1、2 或 3")

    if raw == "3":
        return None

    # 获取当前时段
    print("\n  获取当前时间...")
    now_resp = mcp_call("now-time-info")
    now_data = now_resp.get("data", {}) if isinstance(now_resp, dict) else {}
    hour = int(now_data.get("hour", 12))
    slot = _get_time_slot(hour)
    slot_label = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}.get(slot, slot)
    print(f"  当前时间：{now_data.get('formatted', '')}，时段：{slot_label}")

    if raw == "1":
        # 默认套餐
        out = run_helper("load-default-meal", "--time-slot", slot)
        data = json.loads(out)
        if not data.get("ok"):
            print(f"  [警告] {data.get('error', '加载失败')}，降级为自由选菜")
            return None
        cart = data["cart"]
        print(f"\n  默认{data['label']}套餐：")
        for item in cart:
            print(f"    · {item['name']} × {item['quantity']}")
        ans = ask("\n  确认使用此套餐？（y=确认 / n=自由选菜）").lower()
        if ans in ("y", "yes", "是", "确认"):
            return cart
        return None

    else:
        # 热量搭配
        print("\n  静默读取门店信息...")
        addr_resp = mcp_call("delivery-query-addresses")
        addresses = addr_resp.get("data", {}).get("addresses", []) if isinstance(addr_resp, dict) else []
        if not addresses:
            print("  [警告] 无法获取地址，降级为自由选菜")
            return None
        first_addr = addresses[0]
        store_code = first_addr.get("storeCode", "")

        print(f"  查询菜单（门店：{first_addr.get('storeName', store_code)}）...")
        menu_resp = mcp_call("query-meals", {"storeCode": store_code})
        menu_data = menu_resp.get("data", menu_resp) if isinstance(menu_resp, dict) else {}

        print("  获取营养数据...")
        nutrition_text = mcp_call_raw("list-nutrition-foods", {})

        print("  计算热量搭配...")
        out = run_helper(
            "calorie-pairing",
            "--menu", json.dumps(menu_data),
            "--nutrition-text", nutrition_text,
            "--time-slot", slot,
        )
        data = json.loads(out)
        if not data.get("ok"):
            print(f"  [提示] {data.get('error', '搭配失败')}，降级为自由选菜")
            return None

        print(f"\n{data['display']}")
        ans = ask("\n  确认使用此搭配？（y=确认 / n=自由选菜）").lower()
        if ans in ("y", "yes", "是", "确认"):
            return data["cart"]
        return None


def _enrich_cart_prices(cart: list, address: dict) -> list:
    """补全购物车中 price=0 的条目，从 query-meals 中查询实际价格"""
    if all(item.get("price", 0) != 0 for item in cart):
        return cart

    store_code = address.get("storeCode", "")
    resp = mcp_call("query-meals", {"storeCode": store_code})
    data = resp.get("data", resp) if isinstance(resp, dict) else {}
    meals_map = data.get("meals", {})

    enriched = []
    for item in cart:
        code = item.get("productCode", item.get("code", ""))
        if item.get("price", 0) == 0 and code in meals_map:
            item = dict(item)
            item["price"] = meals_map[code].get("currentPrice", 0)
        # 确保 cart 中用 "code" 字段（step_browse_menu 的约定）
        if "code" not in item and "productCode" in item:
            item = dict(item)
            item["code"] = item["productCode"]
        enriched.append(item)
    return enriched


def flow_order():
    """完整点餐流程"""
    preset_cart = step_choose_meal_mode()
    address = step_choose_address()
    if preset_cart is not None:
        cart = _enrich_cart_prices(preset_cart, address)
    else:
        cart = step_browse_menu(address)
    price = step_calculate_price(cart, address)
    confirmed = step_confirm(cart, price, address)
    if confirmed:
        step_create_order(address, cart)
    else:
        print("\n  已取消下单。")


def flow_nutrition():
    """营养查询：list-nutrition-foods 返回 Markdown，直接打印"""
    keyword = ask("请输入餐品名称（如：巨无霸、薯条）")
    print(f"\n查询「{keyword}」的营养信息...\n")
    resp = mcp_call("list-nutrition-foods", {"keyword": keyword})
    # list-nutrition-foods 可能返回 Markdown 文本或结构数据
    if isinstance(resp, dict):
        foods = resp.get("data", {})
        if isinstance(foods, list):
            for f in foods:
                print(f"  {f.get('name', '')}")
                print(f"    热量：{f.get('calories', f.get('calorie', ''))} kcal")
                print(f"    蛋白质：{f.get('protein','')}g  脂肪：{f.get('fat','')}g  碳水：{f.get('carbohydrate', f.get('carbs',''))}g")
                print()
        else:
            # 无法解析结构，提示用户直接在 OpenClaw 中查询
            print("  （营养数据格式为富文本，建议在 OpenClaw 中通过 LLM 呈现）")
            print(f"  原始返回：{json.dumps(resp, ensure_ascii=False)[:300]}")
    else:
        print(f"  {resp}")


def flow_campaign():
    """活动查询：campaign-calendar 返回 Markdown，直接打印"""
    print("\n查询当前活动...\n")
    now_resp = mcp_call("now-time-info")
    now_data = now_resp.get("data", {}) if isinstance(now_resp, dict) else {}
    date = now_data.get("date", "")
    year, month = (int(x) for x in date.split("-")[:2]) if date else (2026, 3)
    print(f"  当前时间：{now_data.get('formatted', date)}\n")

    camp_resp = mcp_call("campaign-calendar", {"year": year, "month": month})
    # campaign-calendar 可能返回 Markdown
    if isinstance(camp_resp, dict):
        campaigns = camp_resp.get("data", {})
        if isinstance(campaigns, list):
            for c in campaigns:
                print(f"  · {c.get('name', c.get('title', ''))}")
                print(f"    {c.get('description', '')}")
                print()
        else:
            print("  （活动数据格式为富文本，建议在 OpenClaw 中通过 LLM 呈现）")
            print(f"  返回内容：{json.dumps(camp_resp, ensure_ascii=False)[:400]}")
    else:
        print(f"  {camp_resp}")


def flow_track():
    """订单跟踪"""
    order_id = ask("请输入订单号")
    print(f"\n查询订单 {order_id}...\n")
    order = mcp_call("query-order", {"order_id": order_id})
    status_text = order.get("status_text", order.get("status", "未知"))
    print(f"  状态：{status_text}")
    if order.get("rider_name"):
        print(f"  骑手：{order['rider_name']}  {order.get('rider_phone','')}")
    if order.get("rider_location"):
        print(f"  位置：{order['rider_location']}")
    if order.get("estimated_arrival_minutes"):
        print(f"  预计到达：{order['estimated_arrival_minutes']} 分钟后")
    print()


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    step_check_config()

    MENUS = [
        ("帮我点麦当劳（完整点餐流程）", flow_order),
        ("查询营养信息（热量/蛋白质等）", flow_nutrition),
        ("查看当前活动和优惠", flow_campaign),
        ("查询订单状态", flow_track),
        ("退出", None),
    ]

    while True:
        print("\n请选择操作：")
        for i, (label, _) in enumerate(MENUS):
            print(f"  {i + 1}. {label}")
        raw = ask("输入序号")
        if not raw.isdigit() or not (1 <= int(raw) <= len(MENUS)):
            continue
        idx = int(raw) - 1
        label, fn = MENUS[idx]
        if fn is None:
            print("再见！")
            break
        try:
            fn()
        except KeyboardInterrupt:
            print("\n已中断，返回主菜单")


if __name__ == "__main__":
    main()

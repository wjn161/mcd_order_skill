# 🍔 mcd_order — 麦当劳点餐 Skill

通过麦当劳官方 MCP 服务（`https://mcp.mcd.cn`）在 OpenClaw 中完成麦乐送点餐全流程。

---

## 功能一览

| 功能 | 触发方式示例 |
|------|-------------|
| 🛒 点外卖 | "帮我点麦当劳"、"我想吃麦当劳" |
| 📦 订单跟踪 | "我的订单到哪了"、"查订单 xxx" |
| 🥗 营养查询 | "麦辣鸡腿堡多少卡路里"、"薯条热量" |
| 📅 活动日历 | "麦当劳最近有什么活动"、"有没有优惠" |

**三种点餐模式**，每次下单前可选择：

- **🎯 默认套餐** — 按当前时段（早/午/晚）自动推荐固定搭配，一键确认
- **⚖️ 按热量搭配** — 读取菜单和营养数据，自动组合符合当餐热量目标的搭配
- **🔍 自由选菜** — 浏览完整菜单，手动挑选

---

## 安装

### 方法一：让 OpenClaw 自动安装（推荐）

直接把下方这句话发给 OpenClaw：

```
请帮我安装这个 skill：https://github.com/wjn161/mdc_order_skills
```

OpenClaw 会自动 clone 仓库、配置 skill 目录，完成后提示你填写 Token。

### 方法二：手动安装

```bash
git clone https://github.com/wjn161/mdc_order_skills ~/.openclaw/skills/mcd_order
```

---

## 配置

### 第一步：获取 MCD_MCP_TOKEN

1. 访问 [open.mcd.cn](https://open.mcd.cn) 并登录麦当劳账户
2. 进入「开发者控制台」→「我的应用」
3. 创建或选择已有应用，进入「API 密钥」页面
4. 点击「激活」，复制生成的 Token

### 第二步：配置 openclaw.json

编辑 `~/.openclaw/openclaw.json`，添加以下两段：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer YOUR_MCD_MCP_TOKEN"
      }
    }
  },
  "skills": {
    "entries": {
      "mcd_order": {
        "enabled": true,
        "env": {
          "MCD_MCP_TOKEN": "YOUR_MCD_MCP_TOKEN"
        }
      }
    }
  }
}
```

将两处 `YOUR_MCD_MCP_TOKEN` 替换为第一步获取的 Token。

---

## 验证安装

配置完成后，发送以下消息给 OpenClaw 验证：

```
帮我点麦当劳
```

你也可以向 OpenClaw 请求自动完成配置检查：

```
请运行 mcd_order 的配置检查，确认 Token 和 MCP 连接是否正常
```

---

## 点餐流程说明

```
选择点餐模式
    │
    ├─ 默认套餐 → 自动按时段加载套餐 → 确认 ─────────────┐
    ├─ 按热量搭配 → 拉取菜单+营养数据 → 自动组合 → 确认 ──┤
    └─ 自由选菜 → 查询菜单 → 手动选菜 ───────────────────┘
                                                         │
                                              选择配送地址
                                                         │
                                               计算价格明细
                                                         │
                                              确认订单 → 下单
```

**热量目标参考**（`config.json` 可自定义）：

| 时段 | 触发时间 | 热量目标 |
|------|---------|---------|
| 早餐 | 06:00–10:59 | 400–650 kcal |
| 午餐 | 11:00–16:59 | 700–950 kcal |
| 晚餐 | 17:00–05:59 | 550–800 kcal |

---

## 自定义默认套餐

编辑 `config.json`，修改 `default_meals` 中的 `productCode`（商品编号可在麦当劳 App 或 MCP `query-meals` 接口中查询）：

```json
{
  "default_meals": {
    "lunch": {
      "label": "午餐",
      "items": [
        {"productCode": "9900012776", "name": "爆脆精选单人餐", "quantity": 1},
        {"productCode": "903071",     "name": "无糖可口可乐中杯", "quantity": 1}
      ]
    }
  }
}
```

---

## 依赖

| 依赖 | 说明 |
|------|------|
| `python3` | 运行辅助脚本 |
| `qrcode[pil]` | 生成支付二维码图片（PNG） |
| `MCD_MCP_TOKEN` | 麦当劳开放平台 API Token |

安装 Python 依赖：

```bash
pip3 install "qrcode[pil]"
```

---

## 文件结构

```
mcd_order/
├── SKILL.md              # Skill 入口（OpenClaw 读取）
├── README.md             # 本文件
├── config.json           # 默认套餐 + 热量目标配置
└── scripts/
    └── order_helper.py   # 辅助脚本（时段判断、热量搭配、格式化确认单）
```

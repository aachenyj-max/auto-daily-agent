# step2_intent_data_availability.md

> 第二步改造文档：任务识别与数据可用性前置  
> 版本：V0.1  
> 日期：2026-07-09  
> 对应产品阶段：V0.2 可信报告闭环版  
> 关联文档：`product_loop.md`

---

## 1. 本步骤目标

本步骤的目标不是让系统“更聪明”，而是让系统在生成报告前先做到三件事：

1. **知道用户想要什么类型的报告；**
2. **知道生成这份报告需要哪些关键条件；**
3. **知道当前数据是否足够支撑这份报告。**

最终要实现的产品效果是：

```text
用户输入自然语言
  ↓
系统解析成结构化任务
  ↓
系统判断是否缺少必要信息
  ↓
系统判断数据源是否支持
  ↓
只有在任务明确且数据可用时才生成报告
```

本步骤完成后，系统不应该再出现以下情况：

- 用户输入一个不支持的品牌，系统仍然生成一份看似完成的报告；
- 品牌缺少 `brand_id`，系统仍然继续往下跑；
- 用户说“我要买车”，系统没有追问预算就直接生成泛泛建议；
- 车型名称没有匹配成功，系统仍然强行生成对比报告；
- LLM 或规则解析失败时，系统悄悄降级但不告诉用户。

---

## 2. 本步骤涉及模块

建议优先检查和改造以下模块。

| 模块 | 改造重点 |
|---|---|
| `intent_parser.py` | 将用户输入解析成稳定的结构化任务对象 |
| `agent_runner.py` / `workflow_runner.py` | 在执行链中明确 `inspect_request` 与 `inspect_data` 的责任 |
| `brands.json` | 补全品牌支持状态、`brand_id`、别名和启用状态 |
| `processor.py` 输出数据 | 提供品牌、车型、价格、销量、排名等可检查字段 |
| `frontend` | 根据 `run / ask / refuse / data_missing` 展示不同反馈 |
| `managed_reports/index.json` | 记录数据状态、生成模式和失败原因 |

本阶段不优先改造：

- enriched 配置数据深度匹配；
- 多数据源交叉验证；
- 云端部署；
- 多用户权限；
- 复杂对话记忆。

---

## 3. 核心设计原则

### 3.1 先判断，再生成

报告生成前必须完成两层判断：

1. **任务是否明确；**
2. **数据是否可用。**

只有同时满足，才能进入报告生成。

```text
任务明确 + 数据可用 → run
任务不明确 → ask
任务超出边界 → refuse
任务合理但数据不支持 → data_missing
```

### 3.2 不用“编造”弥补数据缺口

当品牌、车型或关键字段缺失时，系统应该明确告诉用户缺失原因，而不是用市场大盘、模型常识或模板话术生成一份看似完整的报告。

### 3.3 失败也要结构化

即使不能生成报告，也应该返回结构化结果，供前端展示、日志记录和后续调试使用。

### 3.4 规则优先，LLM 辅助

任务识别可以使用 LLM，但不能完全依赖 LLM。

建议采用：

```text
规则预处理 → LLM 解析 → 规则校验 → 结构化输出
```

LLM 可以帮助理解自然语言，但最终是否执行必须由规则和数据状态共同决定。

---

## 4. 标准任务对象设计

所有用户请求都应该先被解析成统一的 `ReportTask`。

建议结构如下：

```json
{
  "action": "run",
  "report_type": "brand",
  "brand": "比亚迪",
  "series": [],
  "budget": null,
  "body_type": null,
  "energy_type": null,
  "usage_scenario": null,
  "date": "latest",
  "missing_slots": [],
  "confidence": 0.92,
  "reason": "用户明确要求生成比亚迪品牌日报"
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | string | 当前请求下一步动作 |
| `report_type` | string | 报告类型 |
| `brand` | string/null | 品牌任务的目标品牌 |
| `series` | array | 车型任务或对比任务的目标车型 |
| `budget` | string/null | 预算条件 |
| `body_type` | string/null | 车身类型，例如 SUV、轿车、MPV |
| `energy_type` | string/null | 能源类型，例如纯电、插混、增程、燃油 |
| `usage_scenario` | string/null | 用车场景，例如家用、通勤、商务 |
| `date` | string | 默认 `latest` |
| `missing_slots` | array | 缺失的关键字段 |
| `confidence` | number | 解析置信度，范围 0-1 |
| `reason` | string | 给开发者和前端看的解释 |

---

## 5. action 定义

### 5.1 `run`

表示任务明确，并且数据检查通过，可以进入报告生成。

示例：

```json
{
  "action": "run",
  "report_type": "brand",
  "brand": "比亚迪",
  "missing_slots": [],
  "reason": "品牌存在且数据可用"
}
```

### 5.2 `ask`

表示用户意图合理，但缺少关键条件，需要追问。

示例：

```json
{
  "action": "ask",
  "report_type": "filtered",
  "missing_slots": ["budget"],
  "reason": "购买建议任务缺少预算条件",
  "question": "你的预算大概是多少？例如 20 万以内、15-25 万、30 万左右。"
}
```

### 5.3 `refuse`

表示请求超出产品边界，或者不是汽车市场情报任务。

示例：

```json
{
  "action": "refuse",
  "report_type": null,
  "reason": "当前产品只支持汽车市场情报报告，不支持开放闲聊或非汽车任务"
}
```

### 5.4 `data_missing`

表示用户任务合理，但数据源当前不支持，或者数据字段不足。

示例：

```json
{
  "action": "data_missing",
  "report_type": "brand",
  "brand": "特斯拉",
  "reason": "品牌未接入 brands.json，无法生成可信品牌报告",
  "suggestions": [
    "查看已支持品牌列表",
    "生成整体市场报告",
    "先为该品牌补充 brand_id 和别名"
  ]
}
```

---

## 6. report_type 判断规则

V0.2 阶段优先稳定三类任务：

1. `brand`：品牌日报；
2. `compare`：车型对比；
3. `filtered`：筛选购买建议。

其他类型可以保留，但不要作为主路径。

| report_type | 触发条件 | 必要信息 |
|---|---|---|
| `brand` | 用户提到品牌 + 表现/日报/销量/市场 | `brand` |
| `compare` | 用户提到两个及以上车型，或出现“对比 / 比较 / vs / 哪个更好” | `series.length >= 2` |
| `filtered` | 用户提到预算、用途、车身类型、能源类型或“推荐” | 至少应有 `budget`，其他可选 |
| `series` | 用户只关注单个车型 | `series.length == 1`，暂不主推 |
| `market` | 用户询问整体市场 | 可无品牌和车型，暂不主推 |
| `followup` | 用户基于已有报告继续追问 | `parent_report_id` |

---

## 7. 三类主任务的 slot 规则

### 7.1 品牌日报 `brand`

必要字段：

```json
{
  "report_type": "brand",
  "brand": "比亚迪"
}
```

判断规则：

| 条件 | 动作 |
|---|---|
| 品牌存在且 `brand_id` 有效 | `run` |
| 品牌存在但 `brand_id` 为空 | `data_missing` |
| 品牌不在 `brands.json` | `data_missing` |
| 用户只说“看看这个品牌”但没有品牌名 | `ask` |

示例追问：

```text
你想查看哪个品牌？例如比亚迪、小米、理想、蔚来。
```

---

### 7.2 车型对比 `compare`

必要字段：

```json
{
  "report_type": "compare",
  "series": ["小米 SU7", "小米 YU7"]
}
```

判断规则：

| 条件 | 动作 |
|---|---|
| 匹配到 2 个及以上车型 | `run` |
| 只匹配到 1 个车型 | `ask` |
| 车型都无法匹配 | `data_missing` 或 `ask` |
| 车型对应品牌数据缺失 | `data_missing` |

示例追问：

```text
你想把小米 SU7 和哪款车对比？可以输入另一款车型名称。
```

---

### 7.3 筛选购买建议 `filtered`

必要字段：

```json
{
  "report_type": "filtered",
  "budget": "20万以内"
}
```

推荐字段：

```json
{
  "body_type": "SUV",
  "energy_type": "新能源",
  "usage_scenario": "家用"
}
```

判断规则：

| 条件 | 动作 |
|---|---|
| 有预算 | `run` |
| 无预算，但有明确车型范围 | `ask` |
| 只有“我要买车” | `ask` |
| 筛选后无车型结果 | `data_missing` |

示例追问：

```text
你的预算大概是多少？例如 20 万以内、15-25 万、30 万左右。
```

---

## 8. 品牌支持状态设计

建议重构 `brands.json`，不要只保存品牌名和 `brand_id`，而是保存品牌状态。

推荐结构：

```json
[
  {
    "name": "比亚迪",
    "brand_id": "15",
    "aliases": ["BYD", "byd"],
    "enabled": true,
    "support_status": "supported",
    "notes": "主路径支持"
  },
  {
    "name": "问界",
    "brand_id": null,
    "aliases": ["AITO", "aito"],
    "enabled": false,
    "support_status": "missing_brand_id",
    "notes": "品牌已列入关注范围，但缺少 brand_id，暂不能抓取"
  },
  {
    "name": "特斯拉",
    "brand_id": null,
    "aliases": ["Tesla", "tesla"],
    "enabled": false,
    "support_status": "not_connected",
    "notes": "尚未接入数据源"
  }
]
```

`support_status` 建议使用以下枚举：

| 状态 | 含义 | 是否允许生成品牌报告 |
|---|---|---|
| `supported` | 已接入，`brand_id` 有效 | 是 |
| `missing_brand_id` | 品牌在关注范围内，但无法抓取 | 否 |
| `not_connected` | 品牌未接入 | 否 |
| `disabled` | 暂时禁用 | 否 |

---

## 9. 数据可用性对象设计

在 `inspect_data` 阶段，每个任务都应该产出一个 `DataAvailability` 对象。

建议结构：

```json
{
  "data_status": "available",
  "reason": "品牌数据存在，包含价格、销量和排名字段",
  "latest_data_date": "2026-07-09",
  "required_fields": ["brand", "series", "price", "sales", "rank"],
  "available_fields": ["brand", "series", "price", "sales", "rank"],
  "missing_fields": [],
  "matched_entities": {
    "brand": "比亚迪",
    "series": []
  },
  "unsupported_entities": [],
  "can_generate": true
}
```

### 9.1 data_status 枚举

| data_status | 含义 | can_generate |
|---|---|---|
| `available` | 必要数据完整 | true |
| `partial` | 核心数据可用，但补充数据缺失 | true |
| `missing` | 必要数据缺失 | false |
| `unsupported` | 品牌或车型不在支持范围 | false |
| `stale` | 只有旧数据可用 | 可配置 |
| `error` | 检查过程出错 | false |

### 9.2 不同任务的必要数据

| 任务 | 必要数据 | 可选数据 |
|---|---|---|
| 品牌日报 | 品牌、车型、价格、销量或排名 | enriched 配置、评测摘要 |
| 车型对比 | 至少两个车型的价格、销量或排名 | 参数配置、口碑、评测 |
| 筛选建议 | 价格区间、车型、品牌、能源类型或车身类型 | 配置、口碑、评测 |

---

## 10. inspect_request 责任边界

`inspect_request` 只负责判断用户请求本身是否合理，不负责检查数据文件。

输入：

```text
用户原始自然语言
```

输出：

```json
{
  "task": {
    "action": "run",
    "report_type": "brand",
    "brand": "比亚迪",
    "series": [],
    "missing_slots": []
  },
  "request_status": "clear",
  "request_reason": "用户明确指定品牌日报"
}
```

`request_status` 建议枚举：

| 状态 | 含义 |
|---|---|
| `clear` | 请求明确 |
| `ambiguous` | 请求模糊，需要确认 |
| `missing_slots` | 缺少关键字段 |
| `out_of_scope` | 超出产品边界 |

---

## 11. inspect_data 责任边界

`inspect_data` 只负责判断当前数据是否支持该任务。

输入：

```json
{
  "report_type": "brand",
  "brand": "比亚迪",
  "series": [],
  "budget": null
}
```

输出：

```json
{
  "data_status": "available",
  "can_generate": true,
  "reason": "品牌已接入，最新 processed 数据存在"
}
```

`inspect_data` 不应该改写用户意图，只能补充数据状态。

---

## 12. 最终决策合并规则

最终是否执行报告生成，由 `ReportTask` 和 `DataAvailability` 合并决定。

伪代码：

```python
if request_status == "out_of_scope":
    action = "refuse"
elif missing_slots:
    action = "ask"
elif data_status in ["unsupported", "missing", "error"]:
    action = "data_missing"
elif data_status in ["available", "partial"]:
    action = "run"
else:
    action = "ask"
```

最终返回给前端：

```json
{
  "action": "run",
  "task": {...},
  "data_availability": {...},
  "message": "数据可用，正在生成报告。"
}
```

---

## 13. 前端展示规则

前端不应该只显示“正在生成”，而应该根据 `action` 显示不同状态。

### 13.1 run

```text
已识别为：品牌日报
目标品牌：比亚迪
数据状态：可用
正在生成报告……
```

### 13.2 ask

```text
我还需要一个信息：你的预算大概是多少？
例如：20 万以内、15-25 万、30 万左右。
```

### 13.3 data_missing

```text
当前无法生成可信报告。
原因：特斯拉尚未接入数据源。
你可以：
1. 查看已支持品牌列表
2. 生成整体市场报告
3. 先补充该品牌数据源配置
```

### 13.4 refuse

```text
当前产品只支持汽车市场情报报告，暂不支持该类请求。
你可以输入：生成比亚迪日报 / 小米 SU7 和小米 YU7 对比 / 20 万以内新能源 SUV 推荐。
```

---

## 14. 日志与索引记录

建议在每次任务执行时记录以下字段，便于调试和复盘。

```json
{
  "request_id": "...",
  "user_input": "生成比亚迪日报",
  "parsed_task": {...},
  "request_status": "clear",
  "data_availability": {...},
  "final_action": "run",
  "created_at": "2026-07-09T00:00:00",
  "generation_started": true,
  "generation_mode": "llm"
}
```

如果没有生成报告，也应记录：

```json
{
  "user_input": "特斯拉日报",
  "final_action": "data_missing",
  "reason": "品牌未接入数据源",
  "generation_started": false
}
```

---

## 15. 典型测试用例

完成本步骤后，至少用以下输入测试。

| 用户输入 | 预期 report_type | 预期 action | 说明 |
|---|---|---|---|
| 生成比亚迪日报 | brand | run | 品牌支持且数据可用 |
| 小米今天表现怎么样 | brand | run | 品牌日报意图 |
| 理想品牌日报 | brand | run | 品牌支持 |
| 问界日报 | brand | data_missing | 品牌存在但缺少 brand_id |
| 保时捷销量如何 | brand | data_missing | 品牌存在但缺少 brand_id |
| 特斯拉今天怎么样 | brand | data_missing | 品牌未接入 |
| 小米 SU7 和小米 YU7 对比 | compare | run | 两个车型可匹配 |
| 小米 SU7 对比一下 | compare | ask | 缺少第二个车型 |
| 蔚来 ES6 和小鹏 G6 哪个好 | compare | run 或 data_missing | 取决于当前数据是否包含车型 |
| 20 万以内新能源 SUV 推荐 | filtered | run | 预算存在 |
| 我要买车 | filtered | ask | 缺少预算和偏好 |
| 推荐一辆 SUV | filtered | ask | 缺少预算 |
| 今天吃什么 | null | refuse | 非汽车任务 |
| 帮我写一首诗 | null | refuse | 非产品边界 |

---

## 16. 验收标准

本步骤完成后，应满足以下标准。

### 16.1 任务解析

| 指标 | 目标 |
|---|---|
| 三类主任务识别准确率 | ≥ 90% |
| 不支持请求误生成率 | 0 |
| 缺少关键字段时追问率 | 100% |
| 解析结果包含结构化 JSON | 100% |

### 16.2 数据判断

| 指标 | 目标 |
|---|---|
| 不支持品牌生成报告数量 | 0 |
| `brand_id` 缺失品牌生成报告数量 | 0 |
| 数据缺失时返回 `data_missing` | 100% |
| 可用数据任务进入生成流程 | 100% |

### 16.3 前端反馈

| 指标 | 目标 |
|---|---|
| `run` 状态展示任务摘要 | 是 |
| `ask` 状态只追问一个关键问题 | 是 |
| `data_missing` 展示明确原因 | 是 |
| `refuse` 提供可支持输入示例 | 是 |

---

## 17. 建议实现顺序

### 第 1 步：整理品牌配置

改造 `brands.json`，加入：

```json
{
  "name": "品牌名",
  "brand_id": "...",
  "aliases": [],
  "enabled": true,
  "support_status": "supported"
}
```

先明确：

- 哪些品牌是 `supported`；
- 哪些品牌是 `missing_brand_id`；
- 哪些品牌是 `not_connected`。

### 第 2 步：重构 intent 解析输出

让 `intent_parser.py` 无论成功还是失败，都返回统一结构。

不要返回散乱字段，也不要只返回文本解释。

### 第 3 步：实现 slot 校验

为三类主任务写明确校验函数：

```python
def validate_brand_task(task): ...
def validate_compare_task(task): ...
def validate_filtered_task(task): ...
```

### 第 4 步：实现数据可用性检查

新增或重构：

```python
def inspect_data(task): ...
```

检查：

- 品牌是否支持；
- `brand_id` 是否有效；
- processed 数据是否存在；
- 车型是否能匹配；
- 必要字段是否存在。

### 第 5 步：合并最终 action

新增：

```python
def decide_next_action(task, data_availability): ...
```

确保所有请求最终只落到：

```text
run / ask / refuse / data_missing
```

### 第 6 步：前端展示不同状态

前端根据 action 展示不同 UI，而不是统一显示“生成中”。

---

## 18. 不建议本阶段做的事

本阶段不要做以下事情：

1. 不要新增更多报告类型；
2. 不要做复杂聊天记忆；
3. 不要优先优化 enriched 配置数据；
4. 不要继续扩展前端视觉效果；
5. 不要让 LLM 自动决定是否有数据；
6. 不要在数据缺失时生成“凑合能看”的报告。

本阶段最重要的是：

> 让系统在生成前就知道：这个任务能不能做，为什么能做，为什么不能做。

---

## 19. 本步骤完成后的理想体验

用户输入：

```text
生成比亚迪日报
```

系统反馈：

```text
已识别为品牌日报。
目标品牌：比亚迪。
数据状态：可用。
正在生成报告。
```

用户输入：

```text
特斯拉今天怎么样
```

系统反馈：

```text
当前无法生成可信报告。
原因：特斯拉尚未接入数据源。
你可以查看已支持品牌列表，或先补充该品牌的数据源配置。
```

用户输入：

```text
我要买车
```

系统反馈：

```text
你的预算大概是多少？例如 20 万以内、15-25 万、30 万左右。
```

用户输入：

```text
小米 SU7 对比一下
```

系统反馈：

```text
你想把小米 SU7 和哪款车对比？请输入另一款车型名称。
```

这说明产品已经从“用户说什么都尝试生成”，变成了“先判断，再生成”的可信工作台。

---

## 20. 和下一步的衔接

本步骤完成后，第三步应进入：

```text
报告生成质量改造
```

第三步重点不再是“能不能生成”，而是：

1. LLM 是否成为主生成路径；
2. 模板是否只作为兜底；
3. 每份报告是否满足最低质量标准；
4. 报告 metadata 是否记录生成模式和质量状态。


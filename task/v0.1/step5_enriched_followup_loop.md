# Step 5：修 enriched 与 follow-up 闭环

> 目标：把“补充数据”和“继续追问”从不稳定功能，改造成可控、可验证、可扩展的小闭环。  
> 本步骤聚焦 `enrich.py`、车型 alias 匹配、`context_builder.py`、follow-up 上下文、编码问题、父子报告关系与续问分类。

---

## 1. 本步骤要解决的问题

前四步已经分别完成：

1. 产品最小闭环定义；
2. 任务识别与数据可用性判断；
3. 报告生成质量控制；
4. 报告管理体验优化。

第五步要处理两个目前最影响“深度体验”的问题：

```text
enriched 补充数据没有真正进入报告
follow-up 续问上下文不稳定
```

这两个问题表面上是功能问题，本质上是“上下文可信度”问题。

---

## 2. 当前主要问题

### 2.1 enriched 补充数据是死路径

当前系统已经有补充数据抓取逻辑，但所有已生成报告中都出现类似问题：

```text
补充配置数据存在，但未通过车型匹配校验，已跳过。
```

这说明：

```text
抓取了数据
  ↓
清洗了数据
  ↓
但车型名匹配失败
  ↓
报告完全用不上
```

因此 enriched 现在不是能力，而是噪音。

---

### 2.2 follow-up 上下文递归嵌套

当前 follow-up 存在上下文层层套娃：

```text
新报告摘要
  包含上一份报告摘要
    上一份报告摘要又包含更早摘要
      ...
```

这会导致：

1. prompt 越来越长；
2. 模型越来越难判断重点；
3. 报告内容重复；
4. 续问质量下降；
5. 运行日志膨胀。

---

### 2.3 follow-up 用户输入存在乱码

日志中出现过类似：

```text
新的补充要求：?????????????
```

说明用户输入在传递过程中发生编码丢失。

这不是小问题。  
对于自然语言产品来说，用户补充输入一旦丢失，follow-up 就失去了意义。

---

## 3. 第五步的核心目标

### 3.1 enriched 的目标

不要追求一次性覆盖所有车型。  
先让 5 个高频车型形成稳定闭环。

目标链路：

```text
抓取补充数据
  ↓
车型 alias 匹配
  ↓
匹配置信度判断
  ↓
写入 context
  ↓
报告中出现“配置/评测补充”章节
  ↓
metadata 记录 enriched 使用情况
```

---

### 3.2 follow-up 的目标

不要把 follow-up 当作普通聊天。  
它应该是“基于某份报告发起的新任务”。

目标链路：

```text
用户围绕报告继续提问
  ↓
识别 follow-up 类型
  ↓
读取父报告轻量摘要
  ↓
判断是否需要重新查数据
  ↓
生成新报告
  ↓
写入 parent_report_id
  ↓
更新父报告 child_report_ids
```

---

## 4. enriched 改造方案

## 4.1 enriched 不再默认进入报告

第一原则：

> 只有通过匹配校验的 enriched 数据，才允许进入报告上下文。

如果 enriched 数据存在但匹配失败，不要在报告正文中反复提示失败。  
失败信息应写入 metadata 或 agent_trace。

报告正文只展示：

```text
本报告基于销量、价格、排名数据生成。
```

不要展示：

```text
补充配置数据存在，但未通过车型匹配校验，已跳过。
```

除非用户打开调试信息。

---

## 4.2 建立车型 alias 映射表

新增文件：

```text
config/series_aliases.json
```

建议结构：

```json
{
  "小米SU7": {
    "canonical_name": "小米 SU7",
    "aliases": ["小米SU7", "小米 SU7", "SU7", "Xiaomi SU7"],
    "brand": "小米"
  },
  "小米YU7": {
    "canonical_name": "小米 YU7",
    "aliases": ["小米YU7", "小米 YU7", "YU7", "Xiaomi YU7"],
    "brand": "小米"
  },
  "理想L6": {
    "canonical_name": "理想 L6",
    "aliases": ["理想L6", "理想 L6", "L6"],
    "brand": "理想"
  },
  "比亚迪秦PLUS": {
    "canonical_name": "比亚迪 秦 PLUS",
    "aliases": ["秦PLUS", "秦 PLUS", "秦PLUS DM-i", "秦 PLUS DM-i", "比亚迪秦PLUS"],
    "brand": "比亚迪"
  },
  "蔚来ES6": {
    "canonical_name": "蔚来 ES6",
    "aliases": ["蔚来ES6", "蔚来 ES6", "ES6"],
    "brand": "蔚来"
  }
}
```

第一版只覆盖这 5 个车型。

不要一开始做全量模糊匹配。  
先让少数高频车型稳定通过，再逐步扩展。

---

## 4.3 车型名称标准化

新增函数：

```python
def normalize_series_name(name: str) -> str:
    if not name:
        return ""

    normalized = name.strip()
    normalized = normalized.replace(" ", "")
    normalized = normalized.replace("　", "")
    normalized = normalized.upper()

    return normalized
```

示例：

```text
小米 SU7 → 小米SU7
小米SU7 → 小米SU7
Xiaomi SU7 → XIAOMISU7
秦 PLUS DM-i → 秦PLUSDM-I
```

---

## 4.4 alias 匹配函数

新增函数：

```python
def match_series_alias(input_name: str, alias_config: dict) -> dict:
    normalized_input = normalize_series_name(input_name)

    for key, item in alias_config.items():
        candidates = [item["canonical_name"]] + item.get("aliases", [])

        for candidate in candidates:
            if normalize_series_name(candidate) == normalized_input:
                return {
                    "matched": True,
                    "canonical_name": item["canonical_name"],
                    "match_type": "exact_alias",
                    "confidence": 1.0,
                    "brand": item.get("brand")
                }

    return {
        "matched": False,
        "canonical_name": None,
        "match_type": "none",
        "confidence": 0.0,
        "brand": None
    }
```

第一版只做 exact alias。  
不要急着上复杂 fuzzy matching。

---

## 4.5 enriched 匹配状态

每条 enriched 数据都应有匹配状态：

```json
{
  "raw_series_name": "小米SU7",
  "canonical_series_name": "小米 SU7",
  "matched": true,
  "match_type": "exact_alias",
  "confidence": 1.0,
  "usable": true
}
```

如果失败：

```json
{
  "raw_series_name": "未知车型名",
  "canonical_series_name": null,
  "matched": false,
  "match_type": "none",
  "confidence": 0.0,
  "usable": false
}
```

---

## 4.6 enriched metadata

报告 metadata 中增加：

```json
{
  "enriched": {
    "available": true,
    "used": true,
    "matched_count": 3,
    "skipped_count": 1,
    "match_rate": 0.75,
    "used_series": ["小米 SU7", "小米 YU7"],
    "skipped_reason": []
  }
}
```

如果完全没用上：

```json
{
  "enriched": {
    "available": true,
    "used": false,
    "matched_count": 0,
    "skipped_count": 5,
    "match_rate": 0,
    "used_series": [],
    "skipped_reason": ["series_alias_not_matched"]
  }
}
```

---

## 4.7 报告正文展示规则

### 4.7.1 enriched 使用成功

报告中增加章节：

```text
## 配置与评测补充

以下补充信息来自已通过车型匹配校验的数据：

| 车型 | 补充信息 | 来源说明 |
|---|---|---|
| 小米 SU7 | ... | enriched |
```

### 4.7.2 enriched 存在但未通过

报告正文不显示失败提示。  
只在报告详情的调试信息或 metadata 中显示：

```text
补充数据存在，但本次未通过车型匹配校验，未进入正文。
```

### 4.7.3 enriched 不存在

报告正文在“风险与限制”中可轻量说明：

```text
本报告未包含配置和评测补充信息，主要基于销量、价格和排名数据判断。
```

---

## 4.8 enriched 验收用例

### 用例 1：小米 SU7

输入：

```text
小米 SU7 车型分析
```

期望：

```text
series_alias matched = true
canonical_name = 小米 SU7
enriched.used = true
报告包含“配置与评测补充”
```

---

### 用例 2：小米 YU7

输入：

```text
小米YU7怎么样
```

期望：

```text
canonical_name = 小米 YU7
enriched.used = true
```

---

### 用例 3：秦 PLUS

输入：

```text
秦PLUS DM-i 分析
```

期望：

```text
canonical_name = 比亚迪 秦 PLUS
enriched.used = true
```

---

### 用例 4：未配置 alias 的车型

输入：

```text
一个未配置车型分析
```

期望：

```text
enriched.available 可能为 true
enriched.used = false
报告正文不出现失败提示
metadata 中记录 skipped_reason
```

---

## 5. follow-up 改造方案

## 5.1 follow-up 的产品定义

follow-up 不是普通聊天记录。  
follow-up 是：

> 用户基于一份已有报告发起的新报告任务。

因此每一次 follow-up 都应该生成一个新的报告对象。

---

## 5.2 follow-up 类型枚举

建议将 follow-up 分为 4 类：

```text
expand       展开原报告中的某个点
compare      新增对比对象
refilter     换一个筛选视角
regenerate   用新数据或新要求重新生成
```

### 示例

| 用户输入 | 类型 | 动作 |
|---|---|---|
| 展开讲讲销量变化 | expand | 基于父报告摘要续写 |
| 和小米对比一下 | compare | 新建对比报告 |
| 换成 20 万以内 SUV 视角 | refilter | 新建筛选报告 |
| 用今天最新数据重新生成 | regenerate | 重新跑数据管线 |

---

## 5.3 follow-up 上下文结构

不要传完整历史对话。  
不要传完整父报告。  
不要传摘要套摘要。

只传轻量结构：

```json
{
  "followup_task": {
    "parent_report_id": "brand-byd-2026-07-09-a1b2",
    "parent_report_title": "比亚迪 2026-07-09 市场日报",
    "parent_report_type": "brand",
    "followup_type": "expand",
    "user_followup": "展开讲讲销量变化",
    "need_refresh_data": false
  },
  "parent_context": {
    "entities": {
      "brand": "比亚迪",
      "series": []
    },
    "data_date": "2026-07-09",
    "summary": "150 字以内的父报告摘要",
    "key_findings": [
      "发现 1",
      "发现 2",
      "发现 3"
    ],
    "limitations": [
      "限制 1"
    ]
  }
}
```

---

## 5.4 父报告摘要生成规则

父报告摘要必须短。

建议限制：

```text
summary <= 150 中文字
key_findings <= 5 条
limitations <= 3 条
```

不要把父报告完整正文塞入 follow-up context。

---

## 5.5 防递归规则

构建 follow-up context 时，必须丢弃以下内容：

```text
父报告的 parent_context
父报告的 followup history
父报告的完整 markdown
父报告中嵌套的旧摘要
父报告的完整 agent_trace
```

只保留：

```text
父报告标题
父报告类型
父报告对象
父报告数据日期
父报告一层摘要
用户本次追问
```

---

## 5.6 follow-up 编码规范

所有前后端接口统一使用 UTF-8。

### 5.6.1 HTTP Header

响应和请求应明确：

```http
Content-Type: application/json; charset=utf-8
```

### 5.6.2 Python 文件读写

```python
path.write_text(content, encoding="utf-8")
content = path.read_text(encoding="utf-8")
```

### 5.6.3 JSON 序列化

```python
json.dumps(data, ensure_ascii=False, indent=2)
```

不要使用默认 `ensure_ascii=True` 输出中文转义，虽然不一定错误，但不利于调试。

---

## 5.7 乱码保护

在接收到用户 follow-up 输入后，先做基本校验。

```python
def validate_user_text(text: str) -> dict:
    if not text or not text.strip():
        return {
            "valid": False,
            "reason": "empty"
        }

    if "????" in text:
        return {
            "valid": False,
            "reason": "encoding_error"
        }

    return {
        "valid": True,
        "reason": None
    }
```

如果检测到乱码，不要继续生成报告。

前端提示：

```text
本次补充问题可能发生编码错误，请重新输入。
```

---

## 5.8 follow-up metadata

每份 follow-up 报告写入：

```json
{
  "report_type": "followup",
  "relations": {
    "parent_report_id": "brand-byd-2026-07-09-a1b2",
    "child_report_ids": [],
    "followup_count": 0,
    "derived_from": "followup",
    "followup_type": "expand"
  },
  "followup": {
    "user_followup": "展开讲讲销量变化",
    "need_refresh_data": false,
    "parent_summary_used": true
  }
}
```

父报告同步更新：

```json
{
  "relations": {
    "child_report_ids": [
      "followup-byd-sales-2026-07-09-c3d4"
    ],
    "followup_count": 1
  }
}
```

---

## 5.9 follow-up 文件命名

建议格式：

```text
followup-{parent_entity}-{followup_type}-{date}-{short_hash}.md
```

示例：

```text
followup-byd-expand-2026-07-09-a1b2.md
followup-xiaomi-su7-compare-2026-07-09-c3d4.md
followup-20w-suv-refilter-2026-07-09-e5f6.md
```

---

## 5.10 follow-up 报告结构

### expand 类型

```text
# {父报告标题}：补充分析

## 追问问题
{用户追问}

## 基于原报告的关键背景
...

## 补充分析
...

## 新增判断
...

## 风险与限制
...

## 下一步建议
...
```

---

### compare 类型

应转为 compare 报告结构：

```text
# {原对象} vs {新增对象} 对比补充报告

## 追问问题
...

## 对比总表
...

## 核心差异
...

## 适合人群
...

## 风险与限制
...

## 下一步建议
...
```

---

### refilter 类型

应转为 filtered 报告结构：

```text
# 基于新筛选条件的补充建议

## 追问问题
...

## 新筛选条件
...

## 候选车型
...

## 推荐优先级
...

## 风险与限制
...

## 下一步建议
...
```

---

### regenerate 类型

应重新执行数据检查与报告生成：

```text
inspect_data
  ↓
prepare_data
  ↓
build_context
  ↓
generate_report
```

不要仅基于旧报告生成。

---

## 6. API 改造建议

### 6.1 follow-up 请求

```http
POST /api/reports/{report_id}/followup
```

请求体：

```json
{
  "message": "展开讲讲销量变化"
}
```

### 6.2 follow-up 响应

```json
{
  "status": "created",
  "parent_report_id": "brand-byd-2026-07-09-a1b2",
  "new_report_id": "followup-byd-expand-2026-07-09-c3d4",
  "followup_type": "expand",
  "job_id": "job-xxx"
}
```

### 6.3 编码错误响应

```json
{
  "status": "failed",
  "error_code": "encoding_error",
  "message": "本次补充问题可能发生编码错误，请重新输入。"
}
```

---

## 7. 前端改造建议

## 7.1 报告详情页 follow-up 输入框

在报告详情页底部提供：

```text
围绕这份报告继续提问...
```

按钮：

```text
继续生成
```

不要叫“发送”，避免用户误以为这是普通聊天。

---

## 7.2 follow-up 类型提示

提交后前端可以展示：

```text
已识别为：展开分析
正在基于原报告生成补充报告
```

或：

```text
已识别为：重新生成
将重新检查今日数据
```

---

## 7.3 父子报告展示

在父报告详情页展示：

```text
相关续问报告

1. 比亚迪销量变化补充分析
2. 比亚迪与小米对比补充报告
```

在 follow-up 报告详情页展示：

```text
来源报告：比亚迪 2026-07-09 市场日报
```

---

## 8. 调试日志与 trace

## 8.1 enriched trace

每次 enriched 匹配应记录：

```json
{
  "stage": "match_enriched_data",
  "input_series": "小米SU7",
  "matched": true,
  "canonical_name": "小米 SU7",
  "match_type": "exact_alias",
  "confidence": 1.0
}
```

失败时：

```json
{
  "stage": "match_enriched_data",
  "input_series": "未知车型",
  "matched": false,
  "reason": "series_alias_not_found"
}
```

---

## 8.2 follow-up trace

每次 follow-up 应记录：

```json
{
  "stage": "build_followup_context",
  "parent_report_id": "...",
  "followup_type": "expand",
  "used_parent_summary": true,
  "used_full_parent_markdown": false,
  "need_refresh_data": false
}
```

重点记录：

```text
used_full_parent_markdown = false
```

这可以防止递归上下文重新出现。

---

## 9. 开发优先级

## P0：必须先做

1. 关闭报告正文中的 enriched 失败提示。
2. 新增 `config/series_aliases.json`。
3. 只支持 5 个高频车型 alias 匹配。
4. follow-up context 禁止传完整父报告。
5. 修复 UTF-8 编码和 JSON 序列化。
6. 检测 `????` 乱码并中止生成。
7. 每个 follow-up 新建报告，不覆盖父报告。

---

## P1：随后做

1. enriched metadata 写入 `matched_count`、`used`、`match_rate`。
2. 报告详情页展示 enriched 使用情况。
3. follow-up 类型识别：expand / compare / refilter / regenerate。
4. 父子报告关系展示。
5. follow-up trace 记录上下文构建过程。

---

## P2：后续优化

1. alias 映射扩展到更多车型。
2. 增加人工确认 alias 的前端入口。
3. 支持低置信度 fuzzy matching。
4. 支持 enriched 数据源多源交叉校验。
5. 支持用户手动修正车型匹配。

---

## 10. 验收测试用例

## 10.1 enriched 验收

### 测试 1：小米 SU7 匹配成功

输入：

```text
小米 SU7 车型分析
```

期望：

```text
alias 匹配成功
canonical_name = 小米 SU7
enriched.used = true
报告中出现“配置与评测补充”
```

---

### 测试 2：小米 YU7 匹配成功

输入：

```text
小米YU7报告
```

期望：

```text
canonical_name = 小米 YU7
enriched.used = true
```

---

### 测试 3：未知车型不污染正文

输入：

```text
某未知车型分析
```

期望：

```text
enriched.used = false
报告正文不出现“补充配置数据存在但未通过匹配校验”
metadata 中记录 skipped_reason
```

---

## 10.2 follow-up 验收

### 测试 4：展开分析

操作：

```text
对“比亚迪市场日报”追问：展开讲讲销量变化
```

期望：

```text
followup_type = expand
新建 follow-up 报告
parent_report_id 正确
used_full_parent_markdown = false
无递归摘要
```

---

### 测试 5：新增对比

操作：

```text
对“小米 SU7 报告”追问：和小米 YU7 对比一下
```

期望：

```text
followup_type = compare
生成对比补充报告
entities.series 包含 小米 SU7 和 小米 YU7
```

---

### 测试 6：重新生成

操作：

```text
对旧报告追问：用今天最新数据重新生成
```

期望：

```text
followup_type = regenerate
重新执行 inspect_data
need_refresh_data = true
生成新报告
```

---

### 测试 7：乱码拦截

请求体模拟：

```json
{
  "message": "?????????????"
}
```

期望：

```text
不生成报告
返回 error_code = encoding_error
前端提示用户重新输入
```

---

### 测试 8：父子关系

操作：

```text
连续对同一父报告追问 2 次
```

期望：

```text
父报告 child_report_ids 有 2 个
followup_count = 2
两个 follow-up 报告 parent_report_id 均指向父报告
```

---

## 11. 本步骤完成后的判断标准

完成第五步后，产品应该达到以下状态：

| 指标 | 目标 |
|---|---:|
| enriched 失败提示污染正文 | 0 |
| 5 个高频车型 alias 匹配成功率 | 100% |
| enriched 使用情况写入 metadata | 100% |
| follow-up 递归上下文 | 0 |
| follow-up 用户输入乱码继续生成 | 0 |
| follow-up 新报告 parent_report_id 缺失 | 0 |
| 父报告 followup_count 更新成功 | 100% |
| regenerate 类型重新检查数据 | 100% |

---

## 12. 第五步完成后的产品效果

完成第五步后，产品会从：

```text
报告生成后可以继续问，但上下文可能污染
补充数据抓了，但基本用不上
```

升级为：

```text
补充数据通过 alias 匹配后进入报告
未匹配数据不污染正文
用户可以围绕报告继续生成新报告
follow-up 有明确类型、父子关系和上下文边界
```

这一步完成后，产品的“深度”才开始成立。

---

## 13. 与前四步的关系

前四步解决的是主链路稳定：

```text
产品定位
  ↓
任务识别
  ↓
数据可用性
  ↓
报告质量
  ↓
报告管理
```

第五步解决的是主链路之后的增强能力：

```text
补充数据能否可靠进入报告
用户能否围绕报告继续分析
上下文能否保持干净
```

到这里，V0.2 的完整闭环变成：

```text
用户提出任务
  ↓
系统识别任务
  ↓
检查数据可用性
  ↓
生成可信报告
  ↓
结构化管理报告
  ↓
使用 enriched 增强报告
  ↓
用户继续追问生成新报告
  ↓
报告关系可追踪
```

这才是一个可以继续扩展的汽车情报 Agent。

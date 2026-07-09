# Step 4：修报告管理体验

> 目标：让报告从“生成出来的 Markdown 文件”升级为“可识别、可筛选、可追踪、可复用的产品对象”。  
> 本步骤聚焦 `managed_reports/index.json`、报告标题、报告列表、筛选搜索、归档恢复、follow-up 入口与前端状态展示。

---

## 1. 本步骤要解决的问题

当前产品已经具备报告生成和本地归档能力，但报告管理体验仍然偏“文件管理”，而不是“产品化报告管理”。

主要问题包括：

1. **报告标题不准确**  
   目前部分报告标题被错误提取为正文小标题，例如“核心摘要”“销量前十”“车型表现”等，用户无法快速判断报告内容。

2. **报告列表信息不足**  
   用户只能看到文件名或少量状态，难以判断报告类型、对象、数据是否完整、是否使用 LLM。

3. **报告状态不够清晰**  
   active / archived 只能说明是否归档，不能说明报告质量、生成方式、数据可用性。

4. **归档体验偏文件层**  
   归档只是隐藏或标记文件，缺少“为什么归档”“是否可恢复”“是否有关联 follow-up”等上下文。

5. **报告之间缺少关系表达**  
   follow-up 报告、对比报告、基于旧报告生成的新报告之间没有清晰的父子关系。

6. **前端缺少管理视角**  
   用户无法按品牌、车型、报告类型、生成模式、质量状态筛选报告。

本步骤的核心不是增加复杂功能，而是把报告管理从“文件列表”整理成“报告资产列表”。

---

## 2. 第四步的核心目标

### 2.1 产品目标

让用户打开工作台后，可以快速回答这些问题：

```text
我有哪些报告？
每份报告是关于什么的？
它是 LLM 生成还是模板兜底？
它的数据是否完整？
它的质量是否通过？
它有没有后续追问？
我是否应该保留、归档或重新生成？
```

### 2.2 技术目标

需要完成以下改造：

| 模块 | 改造目标 |
|---|---|
| `managed_reports/index.json` | 增加标准索引字段 |
| 标题生成逻辑 | 不再从正文小标题提取标题 |
| 前端报告列表 | 展示报告核心信息和状态标签 |
| 筛选搜索 | 支持按类型、品牌、车型、状态筛选 |
| 归档恢复 | 明确归档状态和恢复逻辑 |
| follow-up 入口 | 每份报告可继续追问，并保留父子关系 |

---

## 3. 报告管理的基本原则

### 3.1 报告是产品对象，不只是文件

每份报告都应该被视为一个结构化对象：

```text
报告对象 = Markdown 文件 + metadata + 数据状态 + 生成状态 + 质量状态 + 关系信息
```

不要只依赖文件名管理报告。

### 3.2 标题必须来自任务对象

报告标题应由任务解析结果生成，而不是从 Markdown 正文中反向提取。

错误方式：

```text
从 Markdown 里找第一个 ## 标题作为报告标题
```

正确方式：

```text
根据 report_type、brand、series、date 构建标题
```

### 3.3 列表展示优先服务“识别”

报告列表里最重要的不是展示文件路径，而是让用户一眼看懂：

```text
这是什么报告？
什么时候生成？
基于什么数据？
质量如何？
还能做什么？
```

---

## 4. 标准报告索引结构

建议将 `managed_reports/index.json` 中每份报告统一为以下结构。

```json
{
  "report_id": "brand-byd-2026-07-09",
  "title": "比亚迪 2026-07-09 市场日报",
  "subtitle": "基于销量、价格、排名数据生成",
  "report_type": "brand",
  "report_type_label": "品牌日报",
  "entities": {
    "brand": "比亚迪",
    "series": [],
    "competitors": [],
    "budget": null,
    "body_type": null,
    "energy_type": null
  },
  "data": {
    "status": "available",
    "status_label": "数据完整",
    "date": "2026-07-09",
    "source": "懂车帝",
    "available_fields": ["price", "sales", "ranking"],
    "missing_fields": [],
    "snapshot_path": "data/processed/2026-07-09.json"
  },
  "generation": {
    "mode": "llm",
    "mode_label": "LLM 生成",
    "llm_used": true,
    "model": "glm-4-flash",
    "retry_count": 0,
    "fallback_used": false,
    "fallback_reason": null
  },
  "quality": {
    "status": "passed",
    "status_label": "质量通过",
    "score": 0.86,
    "word_count": 1280,
    "issues": []
  },
  "relations": {
    "parent_report_id": null,
    "child_report_ids": [],
    "followup_count": 0,
    "derived_from": null
  },
  "lifecycle": {
    "status": "active",
    "archived_at": null,
    "archive_reason": null,
    "restored_at": null
  },
  "files": {
    "markdown_path": "output/brand-byd-2026-07-09.md",
    "trace_path": "data/traces/brand-byd-2026-07-09.json"
  },
  "created_at": "2026-07-09T10:30:00",
  "updated_at": "2026-07-09T10:30:00"
}
```

---

## 5. 必填字段与可选字段

### 5.1 必填字段

每份报告必须具备：

```text
report_id
title
report_type
entities
data.status
generation.mode
quality.status
lifecycle.status
files.markdown_path
created_at
updated_at
```

缺少这些字段的报告，不应在前端作为完整报告展示。

### 5.2 可选字段

以下字段可以逐步补齐：

```text
subtitle
trace_path
archive_reason
parent_report_id
child_report_ids
quality.issues
data.snapshot_path
```

但如果字段不存在，前端必须有默认展示：

```text
未知
未记录
暂无
```

---

## 6. 报告 ID 规则

报告 ID 应稳定、可读、避免重复。

### 6.1 推荐格式

```text
{report_type}-{entity_slug}-{date}-{short_hash}
```

示例：

```text
brand-byd-2026-07-09-a1b2
series-xiaomi-su7-2026-07-09-c3d4
compare-xiaomi-su7-vs-yu7-2026-07-09-e5f6
filtered-20w-new-energy-suv-2026-07-09-g7h8
```

### 6.2 为什么需要 short_hash

只用日期和对象可能会冲突。  
例如用户一天内多次生成“比亚迪日报”。

因此建议追加 4 到 6 位短 hash：

```python
short_hash = hashlib.md5(raw_task_json.encode("utf-8")).hexdigest()[:4]
```

---

## 7. 标题生成规则

标题应在生成前确定，并写入 metadata。  
Markdown 第一行也应该使用同一个标题。

### 7.1 标题生成函数

```python
def build_report_title(task):
    date = task.date

    if task.report_type == "market":
        return f"{date} 中国汽车市场总览"

    if task.report_type == "brand":
        return f"{task.brand} {date} 市场日报"

    if task.report_type == "series":
        return f"{task.series[0]} {date} 车型分析报告"

    if task.report_type == "compare":
        return f"{task.series[0]} vs {task.series[1]} 对比报告"

    if task.report_type == "filtered":
        return f"{task.filter_summary} 购车建议报告"

    if task.report_type == "followup":
        return f"{task.parent_title} 续问报告"

    return f"{date} 汽车市场报告"
```

### 7.2 禁止的标题来源

禁止从以下位置提取标题：

```text
第一个二级标题
第一个列表项
第一个表格标题
文件名中的 report_type
正文中的“核心摘要”
```

这些都容易造成标题误判。

---

## 8. 报告类型标签

前端不要直接展示英文枚举。  
建议建立映射表：

```json
{
  "market": "市场总览",
  "brand": "品牌日报",
  "series": "车型分析",
  "compare": "车型对比",
  "filtered": "筛选建议",
  "followup": "续问报告"
}
```

前端展示：

```text
品牌日报
车型对比
筛选建议
```

而不是：

```text
brand
compare
filtered
```

---

## 9. 报告状态标签

### 9.1 数据状态

```json
{
  "available": "数据完整",
  "partial": "部分缺失",
  "missing": "数据缺失",
  "unsupported": "暂不支持"
}
```

### 9.2 生成模式

```json
{
  "llm": "LLM 生成",
  "llm_retry": "LLM 重试生成",
  "rule_fallback": "模板兜底",
  "failed": "生成失败"
}
```

### 9.3 质量状态

```json
{
  "passed": "质量通过",
  "warning": "质量警告",
  "failed": "质量失败"
}
```

### 9.4 生命周期状态

```json
{
  "active": "使用中",
  "archived": "已归档",
  "deleted": "已删除"
}
```

短期内可以只支持 `active` 和 `archived`。  
不建议立即实现物理删除，避免误删报告文件。

---

## 10. 前端报告列表设计

### 10.1 列表核心字段

报告列表每一行建议展示：

| 字段 | 示例 |
|---|---|
| 标题 | 比亚迪 2026-07-09 市场日报 |
| 类型 | 品牌日报 |
| 对象 | 比亚迪 |
| 数据状态 | 数据完整 |
| 生成模式 | LLM 生成 |
| 质量状态 | 质量通过 |
| 字数 | 1280 |
| 时间 | 2026-07-09 10:30 |
| 操作 | 查看 / 续问 / 归档 |

### 10.2 卡片式展示建议

如果前端空间较小，可以使用卡片：

```text
比亚迪 2026-07-09 市场日报
品牌日报 · 比亚迪 · 2026-07-09

[数据完整] [LLM 生成] [质量通过]

基于销量、价格、排名数据生成
1280 字 · 0 次续问

查看   继续追问   归档
```

### 10.3 不建议展示在主列表的信息

以下信息不应放在主列表中，避免干扰：

```text
完整文件路径
完整 agent_trace
完整 prompt
完整 JSON metadata
```

这些可以放到详情页或调试面板。

---

## 11. 筛选与搜索

### 11.1 必做筛选项

第一版至少支持：

```text
报告类型
生命周期状态
生成模式
质量状态
品牌 / 车型关键词
日期范围
```

### 11.2 筛选条件示例

```text
只看品牌日报
只看模板兜底报告
只看质量警告报告
只看比亚迪相关报告
只看今天生成的报告
只看已归档报告
```

### 11.3 搜索字段

关键词搜索应覆盖：

```text
title
entities.brand
entities.series
report_type_label
subtitle
```

不要全文搜索 Markdown 正文，第一版没必要，会增加复杂度。

---

## 12. 报告详情页设计

点击报告后，详情页应分为两个区域：

```text
左侧或顶部：报告元信息
主体区域：Markdown 报告正文
```

### 12.1 元信息区

建议展示：

```text
标题
报告类型
报告对象
数据日期
数据状态
数据源
生成模式
质量状态
字数
创建时间
是否有 follow-up
```

### 12.2 正文区

展示 Markdown 渲染后的报告内容。  
如果报告存在质量警告，应在正文上方展示提示：

```text
本报告存在质量警告：字数不足 / 缺少风险说明 / 使用模板兜底。
```

### 12.3 调试信息区

调试信息默认折叠：

```text
查看 metadata
查看 agent_trace
查看原始 Markdown
```

不要默认展开，避免普通使用时干扰用户。

---

## 13. 归档与恢复

### 13.1 归档原则

归档不是删除。  
归档只是表示：

```text
这份报告暂时不在主列表中展示，但仍然可以找回。
```

### 13.2 归档 metadata

归档时更新：

```json
{
  "lifecycle": {
    "status": "archived",
    "archived_at": "2026-07-09T12:00:00",
    "archive_reason": "user_archived"
  }
}
```

### 13.3 恢复 metadata

恢复时更新：

```json
{
  "lifecycle": {
    "status": "active",
    "restored_at": "2026-07-09T12:30:00"
  }
}
```

### 13.4 归档提示

用户点击归档时，应提示：

```text
归档后报告不会被删除，你可以在“已归档”中恢复。
```

不需要复杂确认弹窗，但要防止用户误以为文件被删除。

---

## 14. follow-up 关系管理

### 14.1 follow-up 不应覆盖原报告

每一次 follow-up 都生成一份新报告，并在 metadata 中记录父子关系。

```json
{
  "relations": {
    "parent_report_id": "brand-byd-2026-07-09-a1b2",
    "child_report_ids": [],
    "followup_count": 0,
    "derived_from": "followup"
  }
}
```

原报告应更新：

```json
{
  "relations": {
    "child_report_ids": [
      "followup-byd-sales-detail-2026-07-09-c3d4"
    ],
    "followup_count": 1
  }
}
```

### 14.2 前端展示

原报告卡片中显示：

```text
1 次续问
```

详情页显示：

```text
相关续问报告：
- 比亚迪销量变化展开分析
- 比亚迪与小米对比补充报告
```

### 14.3 follow-up 入口

每份报告详情页提供一个输入框：

```text
围绕这份报告继续提问...
```

但提交后必须进入第二步定义的任务识别逻辑：

```text
expand / compare / refilter / regenerate
```

不要把 follow-up 简单当作聊天消息保存。

---

## 15. 报告列表 API 设计

### 15.1 获取报告列表

```http
GET /api/reports
```

支持参数：

```text
status=active|archived
report_type=brand|series|compare|filtered|market|followup
generation_mode=llm|llm_retry|rule_fallback|failed
quality_status=passed|warning|failed
q=关键词
date_from=YYYY-MM-DD
date_to=YYYY-MM-DD
```

### 15.2 获取报告详情

```http
GET /api/reports/{report_id}
```

返回：

```json
{
  "metadata": {},
  "markdown": "# ..."
}
```

### 15.3 归档报告

```http
POST /api/reports/{report_id}/archive
```

请求体：

```json
{
  "reason": "user_archived"
}
```

### 15.4 恢复报告

```http
POST /api/reports/{report_id}/restore
```

### 15.5 删除接口

短期不建议实现物理删除。  
如果必须实现，也应作为 P2，并增加二次确认和备份。

---

## 16. index.json 迁移策略

已有报告可能缺少新字段。  
不要一次性要求全部重生成，建议做兼容迁移。

### 16.1 迁移脚本目标

新增脚本：

```text
scripts/migrate_report_index.py
```

作用：

```text
读取旧 index.json
补齐缺失字段
修复标题
推断报告类型
写入新 index.json
备份旧 index.json
```

### 16.2 备份规则

迁移前备份：

```text
data/managed_reports/index.backup-YYYYMMDD-HHMMSS.json
```

### 16.3 字段补齐规则

| 缺失字段 | 补齐方式 |
|---|---|
| title | 优先从 task metadata 生成，其次从文件名推断 |
| report_type | 从旧字段或文件名推断 |
| entities | 从旧字段、文件名、正文标题推断 |
| data.status | 默认为 unknown 或根据旧 data_status 推断 |
| generation.mode | 根据 llm_used 推断 |
| quality.status | 旧报告默认为 unknown |
| lifecycle.status | 根据 archived 字段推断 |
| created_at | 使用旧 created_at 或文件修改时间 |

### 16.4 unknown 状态

历史数据无法确定时，不要编造。  
使用：

```text
unknown
```

前端展示为：

```text
未记录
```

---

## 17. 前端空状态与异常状态

### 17.1 没有报告

```text
还没有报告。
你可以先生成一份品牌日报，例如“生成比亚迪日报”。
```

### 17.2 只有归档报告

```text
当前没有使用中的报告。
你可以查看“已归档”，或生成一份新报告。
```

### 17.3 报告文件缺失

metadata 存在，但 Markdown 文件不存在时：

```text
报告索引存在，但正文文件缺失。
建议重新生成该报告，或检查 output 目录。
```

### 17.4 metadata 损坏

```text
报告索引读取失败。
建议检查 data/managed_reports/index.json，或使用备份恢复。
```

---

## 18. 验收测试用例

### 18.1 报告标题正确

输入：

```text
生成比亚迪日报
```

期望：

```text
报告列表标题 = 比亚迪 {date} 市场日报
不应显示“核心摘要”“销量前十”“车型表现”
```

---

### 18.2 车型对比报告显示正确

输入：

```text
小米 SU7 和小米 YU7 对比
```

期望：

```text
标题 = 小米 SU7 vs 小米 YU7 对比报告
类型 = 车型对比
对象 = 小米 SU7、小米 YU7
```

---

### 18.3 模板兜底报告可识别

模拟 LLM 不可用。

期望：

```text
报告列表显示“模板兜底”
详情页提示“本报告为基础模板报告”
```

---

### 18.4 质量警告报告可筛选

模拟生成一份 quality.status = warning 的报告。

期望：

```text
报告列表显示“质量警告”
可以通过筛选条件只看质量警告报告
```

---

### 18.5 归档与恢复

操作：

```text
归档一份报告
切换到已归档
恢复该报告
回到使用中列表
```

期望：

```text
报告不丢失
lifecycle.status 正确变化
archived_at / restored_at 正确记录
```

---

### 18.6 follow-up 关系展示

操作：

```text
对比亚迪日报继续追问“展开讲讲销量变化”
```

期望：

```text
生成新 follow-up 报告
新报告 parent_report_id 指向原报告
原报告 followup_count +1
详情页展示相关续问报告
```

---

## 19. 开发优先级

### P0：必须先做

1. 修复标题来源，不再从正文小标题提取。
2. 统一 `managed_reports/index.json` 字段。
3. 前端报告列表展示标题、类型、对象、数据状态、生成模式、质量状态。
4. 归档 / 恢复只改 metadata，不删除文件。
5. 详情页展示 metadata 摘要。

### P1：随后做

1. 增加筛选：类型、状态、生成模式、质量状态。
2. 增加关键词搜索：标题、品牌、车型。
3. 增加 follow-up 父子关系展示。
4. 增加 index 迁移脚本。
5. 增加报告文件缺失提示。

### P2：后续优化

1. 支持批量归档。
2. 支持收藏 / 置顶。
3. 支持导出报告集合。
4. 支持重新生成低质量报告。
5. 支持物理删除与回收站。

---

## 20. 本步骤完成后的判断标准

完成第四步后，产品应该达到以下状态：

| 指标 | 目标 |
|---|---:|
| 报告标题错误 | 0 |
| 主列表缺少报告类型 | 0 |
| 主列表缺少生成模式 | 0 |
| 主列表缺少质量状态 | 0 |
| 归档后文件丢失 | 0 |
| 已归档报告可恢复 | 100% |
| follow-up 报告可追溯父报告 | 100% |
| 用户能筛选模板兜底报告 | 是 |
| 用户能筛选质量警告报告 | 是 |

---

## 21. 第四步完成后的产品效果

完成本步骤后，产品逻辑会从：

```text
生成报告
  ↓
保存成 Markdown 文件
  ↓
用户在列表里找文件
```

升级为：

```text
生成报告
  ↓
写入结构化 metadata
  ↓
前端展示报告资产
  ↓
用户可筛选、查看、续问、归档、恢复
  ↓
报告形成生命周期管理
```

这一步完成后，报告不再只是输出文件，而是产品中的核心资产。

---

## 22. 与前三步的关系

前三步解决的是主链路：

```text
产品定位
  ↓
任务是否清楚
  ↓
数据是否可用
  ↓
报告是否可信
```

第四步解决的是报告产物的生命周期：

```text
报告是否可识别
  ↓
是否可管理
  ↓
是否可追问
  ↓
是否可复用
```

四步合在一起，V0.2 的核心闭环就变成：

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
用户继续追问或归档
```

这就是一个可用的本地汽车情报工作台，而不是一组松散脚本。

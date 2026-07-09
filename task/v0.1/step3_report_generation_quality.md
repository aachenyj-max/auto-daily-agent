# Step 3：修报告生成质量

> 目标：让报告生成从“能生成”升级为“稳定、完整、可信、可追踪”。  
> 本步骤聚焦 `dynamic_report_generator.py`、`report_agent_prompt.md`、报告 metadata、质量校验与兜底策略。

---

## 1. 本步骤要解决的问题

当前报告生成链路已经具备基本能力，但存在以下问题：

1. **LLM 没有成为主路径**  
   多数报告实际走规则模板，导致内容简陋、分析深度不足。

2. **规则模板兜底过于隐蔽**  
   用户无法判断当前报告是 LLM 生成，还是模板生成。

3. **报告结构不稳定**  
   不同报告之间标题、摘要、分析、建议等结构不统一。

4. **报告质量缺少硬性门槛**  
   只要文件生成且非空，就可能被认为成功。

5. **失败处理不透明**  
   LLM 调用失败、数据不足、生成过短等情况，没有形成清晰的状态和提示。

本步骤不追求“报告非常聪明”，而是先保证：

> 每一份报告都完整、可读、可信，并能说明它是如何生成的。

---

## 2. 第三步的核心目标

### 2.1 产品目标

将报告生成链路调整为：

```text
优先 LLM 生成
  ↓
失败后重试一次
  ↓
仍失败则使用规则模板兜底
  ↓
质量校验
  ↓
写入报告 metadata
  ↓
前端明确展示生成模式
```

### 2.2 技术目标

需要完成以下改造：

| 模块 | 改造目标 |
|---|---|
| `dynamic_report_generator.py` | 建立 LLM 主路径、重试、模板兜底机制 |
| `report_agent_prompt.md` | 约束 LLM 输出结构和质量 |
| `validate_report` / `quality_check` | 从“文件存在校验”升级为“内容质量校验” |
| `managed_reports/index.json` | 增加生成模式、质量分、失败原因等 metadata |
| 前端报告列表 | 展示 LLM / 兜底 / 低质量等状态 |

---

## 3. 报告生成链路设计

### 3.1 标准生成流程

```text
build_context
  ↓
generate_report
  ↓
llm_generate_report
  ↓
validate_structure
  ↓
quality_check
  ↓
save_report
  ↓
update_managed_reports_index
```

### 3.2 推荐生成策略

```text
第 1 层：LLM 正常生成
第 2 层：LLM 失败后重试一次
第 3 层：规则模板兜底
第 4 层：质量校验
第 5 层：生成模式写入 metadata
```

不要让规则模板静默替代 LLM。  
只要进入模板兜底，就必须在 metadata 和前端中明确记录。

---

## 4. 标准 metadata 设计

每份报告生成后，都应该写入统一 metadata。

建议结构如下：

```json
{
  "report_id": "brand-byd-2026-07-09",
  "title": "比亚迪 2026-07-09 市场日报",
  "report_type": "brand",
  "entities": {
    "brand": "比亚迪",
    "series": [],
    "budget": null,
    "body_type": null,
    "energy_type": null
  },
  "data_status": "available",
  "data_date": "2026-07-09",
  "generation": {
    "mode": "llm",
    "llm_used": true,
    "llm_provider": "zhipu",
    "model": "glm-4-flash",
    "retry_count": 0,
    "fallback_used": false,
    "fallback_reason": null
  },
  "quality": {
    "status": "passed",
    "score": 0.86,
    "word_count": 1280,
    "required_sections_passed": true,
    "has_data_table": true,
    "has_limitations": true,
    "issues": []
  },
  "created_at": "2026-07-09T10:30:00",
  "updated_at": "2026-07-09T10:30:00",
  "status": "active",
  "file_path": "output/brand-byd-2026-07-09.md"
}
```

### 4.1 generation.mode 枚举

```text
llm             LLM 一次生成成功
llm_retry       LLM 首次失败，重试后成功
rule_fallback   LLM 不可用或失败，使用规则模板兜底
failed          生成失败，没有可用报告
```

### 4.2 quality.status 枚举

```text
passed          质量通过
warning         可用但有明显缺陷
failed          不应交付给用户
```

---

## 5. 报告最低质量标准

每份报告至少满足以下标准。

### 5.1 通用结构要求

所有报告都必须包含：

```text
# 报告标题

## 核心摘要
## 关键数据
## 主要发现
## 分析判断
## 风险与限制
## 下一步建议
```

其中：

| 模块 | 要求 |
|---|---|
| 报告标题 | 必须包含报告对象、报告类型、日期 |
| 核心摘要 | 3 到 5 条要点 |
| 关键数据 | 至少一个表格或结构化列表 |
| 主要发现 | 至少 3 条 |
| 分析判断 | 不能只复述数据，需要给出解释 |
| 风险与限制 | 必须说明数据缺口或适用边界 |
| 下一步建议 | 至少 2 条可执行建议 |

### 5.2 字数要求

| 报告类型 | 最低字数 |
|---|---:|
| market 市场总览 | 800 字 |
| brand 品牌日报 | 700 字 |
| series 单车型报告 | 600 字 |
| compare 车型对比 | 700 字 |
| filtered 筛选购买建议 | 700 字 |
| followup 续问报告 | 400 字 |

如果用户明确要求“简短”“一句话”“摘要版”，可以降低字数要求，但 metadata 中应记录：

```json
{
  "quality": {
    "short_form_requested": true
  }
}
```

### 5.3 数据引用要求

报告中不能凭空编造数据。  
若数据字段缺失，应明确写成：

```text
当前数据源暂未提供该字段，因此本报告不对此项做确定性判断。
```

禁止写成：

```text
预计表现良好
大概率领先
明显优于竞品
```

除非上下文中有对应数据支撑。

---

## 6. 各类报告结构模板

### 6.1 market 市场总览

```text
# {date} 中国汽车市场总览

## 核心摘要
- ...
- ...
- ...

## 市场关键数据
| 指标 | 数值 | 说明 |
|---|---:|---|

## 销量表现
...

## 价格与竞争格局
...

## 重点品牌观察
...

## 风险与限制
...

## 下一步建议
...
```

---

### 6.2 brand 品牌日报

```text
# {brand} {date} 市场日报

## 核心摘要
- ...
- ...
- ...

## 品牌关键数据
| 指标 | 数值 | 说明 |
|---|---:|---|

## 车型表现
| 车型 | 价格区间 | 销量 | 排名变化 |
|---|---:|---:|---:|

## 主要发现
1. ...
2. ...
3. ...

## 分析判断
...

## 风险与限制
...

## 下一步建议
...
```

---

### 6.3 series 单车型报告

```text
# {series} {date} 车型分析报告

## 核心摘要
- ...
- ...
- ...

## 车型关键数据
| 指标 | 数值 | 说明 |
|---|---:|---|

## 价格与定位
...

## 销量与排名表现
...

## 同品牌参考
...

## 主要判断
...

## 风险与限制
...

## 下一步建议
...
```

---

### 6.4 compare 车型对比

```text
# {series_a} vs {series_b} 对比报告

## 核心摘要
- ...
- ...
- ...

## 对比总表
| 维度 | {series_a} | {series_b} | 判断 |
|---|---|---|---|

## 价格与定位对比
...

## 销量与热度对比
...

## 适合人群
...

## 主要判断
...

## 风险与限制
...

## 下一步建议
...
```

---

### 6.5 filtered 筛选购买建议

```text
# {filter_summary} 购车建议报告

## 核心摘要
- ...
- ...
- ...

## 筛选条件
| 条件 | 用户要求 |
|---|---|
| 预算 | ... |
| 车型 | ... |
| 能源类型 | ... |

## 候选车型列表
| 车型 | 品牌 | 价格区间 | 主要理由 |
|---|---|---:|---|

## 推荐优先级
...

## 不推荐或需谨慎车型
...

## 风险与限制
...

## 下一步建议
...
```

---

## 7. `report_agent_prompt.md` 改造建议

### 7.1 Prompt 目标

Prompt 不应该只告诉模型“生成一份报告”，而应该明确：

1. 你是汽车市场情报报告生成器；
2. 只能基于提供的数据写；
3. 必须按指定结构输出；
4. 数据缺失要明确说明；
5. 不允许编造销量、价格、排名；
6. 输出 Markdown；
7. 不要输出解释性前言。

### 7.2 推荐 Prompt 草案

```text
你是一个汽车市场情报报告生成器。

你的任务是根据系统提供的结构化汽车市场数据，生成一份 Markdown 报告。

必须遵守以下规则：

1. 只能使用输入上下文中提供的数据。
2. 不允许编造销量、价格、排名、配置、评测或市场结论。
3. 如果某项数据缺失，必须明确说明“当前数据源暂未提供该字段”。
4. 报告必须使用 Markdown 格式。
5. 报告必须包含以下章节：
   - 核心摘要
   - 关键数据
   - 主要发现
   - 分析判断
   - 风险与限制
   - 下一步建议
6. 核心摘要必须是 3 到 5 条 bullet points。
7. 主要发现至少 3 条。
8. 下一步建议至少 2 条。
9. 不要输出“根据你提供的数据”等对话式表述。
10. 不要输出报告之外的解释、寒暄或代码块。

报告类型：{report_type}
报告对象：{entities}
数据日期：{data_date}
数据可用性：{data_status}
数据上下文如下：

{context}
```

---

## 8. 质量校验规则

### 8.1 校验函数建议

新增或改造一个质量校验函数：

```python
def check_report_quality(markdown: str, task: ReportTask) -> dict:
    return {
        "status": "passed | warning | failed",
        "score": 0.0,
        "word_count": 0,
        "required_sections_passed": False,
        "has_data_table": False,
        "has_limitations": False,
        "issues": []
    }
```

### 8.2 检查项

| 检查项 | 规则 | 权重 |
|---|---|---:|
| 标题 | 是否存在一级标题 `#` | 0.15 |
| 必要章节 | 是否包含核心摘要、关键数据、风险与限制、下一步建议 | 0.25 |
| 字数 | 是否达到对应报告类型最低字数 | 0.20 |
| 数据表 | 是否存在 Markdown 表格 | 0.15 |
| 分析段落 | 是否包含非表格分析文本 | 0.15 |
| 限制说明 | 是否主动说明数据限制 | 0.10 |

### 8.3 分数规则

```text
score >= 0.80    passed
0.60 - 0.79      warning
score < 0.60     failed
```

### 8.4 失败处理

| 情况 | 动作 |
|---|---|
| LLM 输出为空 | 重试一次 |
| LLM 输出不是 Markdown | 重试一次 |
| 缺少必要章节 | 重试一次，提示缺少章节 |
| 字数严重不足 | 重试一次，要求展开 |
| 重试仍失败 | 使用规则模板兜底 |
| 模板也失败 | 标记 failed，不展示为正常报告 |

---

## 9. 伪代码实现建议

### 9.1 主生成函数

```python
def generate_report(task, context):
    result = {
        "markdown": "",
        "generation": {
            "mode": None,
            "llm_used": False,
            "retry_count": 0,
            "fallback_used": False,
            "fallback_reason": None
        },
        "quality": None
    }

    if llm_is_available():
        markdown = call_llm_report_generator(task, context)
        quality = check_report_quality(markdown, task)

        if quality["status"] in ["passed", "warning"]:
            result["markdown"] = markdown
            result["generation"]["mode"] = "llm"
            result["generation"]["llm_used"] = True
            result["quality"] = quality
            return result

        retry_markdown = call_llm_report_generator(
            task,
            context,
            repair_instruction=build_repair_instruction(quality)
        )
        retry_quality = check_report_quality(retry_markdown, task)

        if retry_quality["status"] in ["passed", "warning"]:
            result["markdown"] = retry_markdown
            result["generation"]["mode"] = "llm_retry"
            result["generation"]["llm_used"] = True
            result["generation"]["retry_count"] = 1
            result["quality"] = retry_quality
            return result

        result["generation"]["fallback_reason"] = "llm_quality_failed"
    else:
        result["generation"]["fallback_reason"] = "llm_unavailable"

    fallback_markdown = generate_rule_based_report(task, context)
    fallback_quality = check_report_quality(fallback_markdown, task)

    result["markdown"] = fallback_markdown
    result["generation"]["mode"] = "rule_fallback"
    result["generation"]["llm_used"] = False
    result["generation"]["fallback_used"] = True
    result["quality"] = fallback_quality

    return result
```

---

## 10. 模板兜底也要升级

规则模板不能再只生成表格和两句话。  
即使是模板兜底，也必须满足最低结构。

### 10.1 模板兜底结构

```text
# {title}

## 核心摘要
- 当前 LLM 不可用，本报告基于规则模板生成。
- 报告仅使用已抓取的结构化数据。
- 深度分析能力有限，建议后续在 LLM 可用后重新生成。

## 关键数据
{table}

## 主要发现
1. ...
2. ...
3. ...

## 分析判断
...

## 风险与限制
- 本报告未使用 LLM 深度分析。
- 本报告不包含未校验的配置或评测数据。
- 若部分品牌或车型数据缺失，相关结论仅供参考。

## 下一步建议
1. ...
2. ...
```

### 10.2 前端提示

如果报告为模板兜底，前端应显示：

```text
本报告为基础模板报告，LLM 未参与生成。报告包含结构化数据，但分析深度有限。
```

---

## 11. 报告标题生成规则

报告标题不应该从正文第一个二级标题提取，而应该在生成前由任务对象确定。

### 11.1 标题生成函数

```python
def build_report_title(task):
    if task.report_type == "market":
        return f"{task.date} 中国汽车市场总览"

    if task.report_type == "brand":
        return f"{task.brand} {task.date} 市场日报"

    if task.report_type == "series":
        return f"{task.series[0]} {task.date} 车型分析报告"

    if task.report_type == "compare":
        return f"{task.series[0]} vs {task.series[1]} 对比报告"

    if task.report_type == "filtered":
        return f"{task.filter_summary} 购车建议报告"

    if task.report_type == "followup":
        return f"{task.parent_title} 续问报告"

    return f"{task.date} 汽车市场报告"
```

### 11.2 metadata 写入规则

标题应来自 `build_report_title(task)`，而不是从 Markdown 中反向提取。

Markdown 第一行也应使用同一个标题：

```markdown
# 比亚迪 2026-07-09 市场日报
```

---

## 12. 前端展示改造

报告列表中建议增加以下字段：

| 字段 | 示例 |
|---|---|
| 报告标题 | 比亚迪 2026-07-09 市场日报 |
| 报告类型 | 品牌日报 |
| 数据状态 | 数据完整 / 部分缺失 / 不支持 |
| 生成模式 | LLM / LLM 重试 / 模板兜底 |
| 质量状态 | 通过 / 警告 / 失败 |
| 字数 | 1280 |
| 生成日期 | 2026-07-09 |

### 12.1 状态标签建议

```text
LLM 生成       绿色
LLM 重试       蓝色
模板兜底       黄色
质量警告       橙色
生成失败       红色
```

不要只展示“完成”。  
要让用户知道这份报告的可信程度。

---

## 13. 验收测试用例

### 13.1 正常生成

输入：

```text
生成比亚迪日报
```

期望：

```text
report_type = brand
brand = 比亚迪
generation.mode = llm 或 llm_retry
quality.status = passed
标题 = 比亚迪 {date} 市场日报
```

---

### 13.2 LLM 不可用

模拟关闭 LLM 配置。

输入：

```text
生成小米日报
```

期望：

```text
generation.mode = rule_fallback
generation.llm_used = false
generation.fallback_reason = llm_unavailable
前端显示“模板兜底”
报告仍包含完整章节
```

---

### 13.3 LLM 输出过短

模拟 LLM 只返回 100 字内容。

期望：

```text
第一次 quality.status = failed
系统触发 retry
retry 后若通过，generation.mode = llm_retry
retry 后若仍失败，generation.mode = rule_fallback
```

---

### 13.4 对比报告

输入：

```text
小米 SU7 和小米 YU7 对比
```

期望：

```text
report_type = compare
标题 = 小米 SU7 vs 小米 YU7 对比报告
包含“对比总表”
包含“适合人群”
包含“风险与限制”
字数 >= 700
```

---

### 13.5 筛选购买建议

输入：

```text
20 万以内新能源 SUV 推荐
```

期望：

```text
report_type = filtered
包含“筛选条件”
包含“候选车型列表”
包含“推荐优先级”
包含“不推荐或需谨慎车型”
```

---

## 14. 开发优先级

### P0：必须先做

1. 增加 `generation.mode`
2. 增加 `quality` metadata
3. 修复标题生成逻辑
4. LLM 失败后重试一次
5. 模板兜底必须显式记录
6. 质量校验不能只检查文件是否存在

### P1：随后做

1. 升级规则模板结构
2. 前端展示生成模式和质量状态
3. Prompt 中增加严格结构约束
4. 对不同报告类型设置最低字数

### P2：后续优化

1. 引入更细的质量评分
2. 支持用户选择“简报 / 标准 / 深度”
3. 支持重新生成低质量报告
4. 记录每次 LLM 失败原因和耗时

---

## 15. 本步骤完成后的判断标准

完成第三步后，产品应该达到以下状态：

| 指标 | 目标 |
|---|---:|
| LLM 使用率 | ≥ 80% |
| 规则兜底率 | ≤ 20% |
| 空报告 | 0 |
| 无标题报告 | 0 |
| 少于最低字数报告 | 0 |
| metadata 缺失 generation 字段 | 0 |
| metadata 缺失 quality 字段 | 0 |
| 用户无法判断生成模式的报告 | 0 |

---

## 16. 第三步完成后的产品效果

完成本步骤后，产品逻辑会从：

```text
用户输入 → 生成一个 Markdown 文件
```

升级为：

```text
用户输入
  ↓
构建报告上下文
  ↓
优先 LLM 生成
  ↓
质量校验
  ↓
必要时重试或兜底
  ↓
写入生成模式和质量信息
  ↓
前端展示可信报告
```

这一步完成后，报告生成链路才真正形成产品级闭环。

---

## 17. 与前两步的关系

本步骤依赖前两步的结果：

1. `product_loop.md` 定义产品最小闭环；
2. `step2_intent_data_availability.md` 定义任务识别和数据可用性；
3. 本文档定义报告生成质量。

三者合在一起，构成 V0.2 的主链路：

```text
任务是否清楚
  ↓
数据是否可用
  ↓
报告是否可信
```

只要这三个问题能稳定回答，产品就已经从 demo 进入可用工具阶段。

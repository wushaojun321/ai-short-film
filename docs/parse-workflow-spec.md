# 剧本解析模块契约

本文件定义当前解析阶段的主流程边界。解析阶段只允许一个全局 LLM 读取剧本索引，其他模块必须使用 `ProductionBlueprint` 和 `ScriptBlock` 做确定性派生，避免重复投喂全文和职责重叠。

## 主链路

```text
parse_script_task
→ ParseOrchestrator
→ ScriptContextPackBuilder
→ ProductionBlueprintPlanner
→ BlueprintSchemaValidator
→ EpisodeMaterialBuilder
→ ContinuitySeedBuilder
→ AssetRegistryBuilder
→ ParseReportBuilder
```

## 模块定义

| 模块 | 类型 | 当前实现 | 职责 | 禁止职责 |
| --- | --- | --- | --- | --- |
| `parse_script_task` | Celery 入口 | `backend/app/tasks/llm_tasks.py` | 保持旧任务名和 API 兼容，只初始化 DB 并调用编排器 | 不再承载解析细节 |
| `ParseOrchestrator` | 编排器 | `backend/app/parsing/orchestrator.py` | 任务日志、进度、失败收敛、模块调用顺序、清理旧初始化产物 | 不直接解析剧本、不拼 prompt、不派生资产细节 |
| `ScriptContextPackBuilder` | 确定性 | `backend/app/parsing/context_pack.py` | 创建 `ScriptBlock`，生成唯一投喂给 LLM 的轻量 `script_index` | 不总结剧情、不输出分集正文 |
| `ProductionBlueprintPlanner` | 唯一全局 LLM | `backend/app/parsing/blueprint_planner.py` | 读取 `script_index` 一次，输出 JSONL 生产蓝图 | 不写分集正文、不写分镜、不写图片/视频提示词 |
| `BlueprintSchemaValidator` | 确定性 | `backend/app/parsing/blueprint_validator.py` | 校验 series、episodes、asset registry、block range 是否可用 | 不做兜底落库、不修改原文 |
| `EpisodeMaterialBuilder` | 确定性 | `backend/app/parsing/episode_builder.py` | 根据 block range 从原文回填 `Episode.script_excerpt` | 不使用 LLM 摘要替代正文 |
| `ContinuitySeedBuilder` | 确定性 | `backend/app/parsing/continuity_seed_builder.py` | 归一化连续性报告、warnings、ignored assets | 不修分镜、不新增剧情 |
| `AssetRegistryBuilder` | 确定性 | `backend/app/parsing/asset_registry_builder.py` | 从蓝图资产注册表派生 `ProductionBlueprint` 和 `Asset` 记录 | 不重新读取剧本、不生成图片提示词 |
| `ParseReportBuilder` | 确定性 | `backend/app/parsing/parse_report_builder.py` | 生成任务结果统计和前端可读解析报告 | 不参与业务决策 |

## 单一事实链

解析阶段的数据事实链固定为：

```text
Project.script_text
→ ScriptBlock
→ ProductionBlueprint
→ Episode / Asset / continuity_report
```

后续模块如需正文，必须通过 `source_block_ranges` 回查 `ScriptBlock`，不能让 LLM 重写正文。资产模块只能读取蓝图资产注册表和分集资产需求，不能重新读取完整剧本。

## LLM 输出边界

`ProductionBlueprintPlanner` 只能输出 JSONL 行：

- `series`
- `episode`
- `character`
- `character_variant`
- `scene`
- `scene_variant`
- `prop`
- `prop_variant`
- `ignore`
- `warning`

每一行必须是完整 JSON 对象。即使输出被截断，前面完整行也应该可用。

## 兼容说明

- 外部 API 和 Celery 任务名保持不变：`app.tasks.llm.parse_script`。
- 当前 prompt scope 仍使用 `script_production_plan`，语义上对应 `ProductionBlueprintPlanner`。
- `backend/app/tasks/llm_tasks.py` 中仍保留部分旧 helper，供分镜链路和兼容逻辑复用；主解析路径已不再由该文件承载。

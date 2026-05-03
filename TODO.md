# TODO / 当前待办

## 已完成

1. 分镜剧照页面增加轮询，后台状态变化后前端可感知。
2. 支持删除项目：`DELETE /api/v1/projects/{project_id}` 已实现。
3. 支持单个资产/单镜头视频单独触发生成；分镜图接口保留为兼容能力，但不在当前主流程展示。
4. 分镜视频生成时已有 `rendering` 状态。
5. 资产生成已有 `queued` / `generating` 状态。
6. 分镜脚本生成已加入短期版片段元数据：LLM 先输出 `segments`，后端展平成 Shot，并按镜头功能归一化 2-8 秒时长。
7. 剧本解析已拆成多模块流水线：`ScriptIndexer` 原文索引、全剧规划、分集范围规划、原文回填、独立资产解析。
8. 新增 `script_blocks` 集合；`Episode.script_excerpt` 由原文块回填，避免长剧本摘要化后丢失台词。
9. 分集数据已增加诊断字段：原文起止行、对白行数、原文完整性，并在分集确认页和制作页展示。
10. 人物资产解析已增加 `asset_package` / `face_identity`，同一人物不同造型共享面部基准，资产生图提示词会继续沿用该基准。

## 待处理

1. 用真实长剧本重新解析回归：检查每集 `script_excerpt` 是否为原文、`dialogue_count` 是否符合预期、`source_integrity` 是否为 `original`。
2. 选 1-2 集重新生成分镜：检查 `Shot.dialogues` 的台词原文保留率、说话人准确率、台词镜数量。
3. LLM 结构化输出仍需加固：增强 `chat_json` 截断检测、JSON 修复重试、错误上下文日志和 schema 校验。
4. 资产解析第二阶段：给资产增加适用集数 / block 范围 / 场景阶段绑定，避免镜头选错人物造型资产。
5. 分镜输入增强：把本集原文起止行、对白数量、相关阶段资产、上一集结尾连续性状态传入 `gen_shot_script_task`。
6. 有时候生成卡通而不是真人：继续调试 `asset_prompt_gen`、`shot_image_gen` 的写实约束。
7. 重启之后继续监控图片、视频生成进度，不要断；需要任务恢复/补偿机制。
8. 图片并发已调整为 20、视频并发已调整为 10；继续观察三方服务限流、机器资源和失败重试情况。
9. 队列满时统一进入 `queued` 状态；当前资产已支持，视频还主要是 `rendering`。
10. 视频生成过程中前端百分比进度未完整透传；火山接口百分比需要写入 `TaskRecord.progress`。
11. TTS 配音任务尚未实现，当前只是保留 `dubbing` 步骤和 `audio_url` 字段。
12. 清理 `backend/app/routers/conversations.py` 的重复路由定义。

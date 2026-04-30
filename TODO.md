# TODO / 当前待办

## 已完成

1. 分镜剧照页面增加轮询，后台状态变化后前端可感知。
2. 支持删除项目：`DELETE /api/v1/projects/{project_id}` 已实现。
3. 支持单个资产/单镜头视频单独触发生成；分镜图接口保留为兼容能力，但不在当前主流程展示。
4. 分镜视频生成时已有 `rendering` 状态。
5. 资产生成已有 `queued` / `generating` 状态。
6. 分镜脚本生成已加入短期版片段元数据：LLM 先输出 `segments`，后端展平成 Shot，并按镜头功能归一化 2-8 秒时长。

## 待处理

1. LLM 剧本解析仍可能返回非法 JSON，前端显示 `Unterminated string...`；需要增强 `chat_json` 截断检测、JSON 修复和错误上下文日志。
2. 有时候生成卡通而不是真人：继续调试 `asset_prompt_gen`、`shot_image_gen` 的写实约束。
3. 重启之后继续监控图片、视频生成进度，不要断；需要任务恢复/补偿机制。
4. 图片并发已调整为 20、视频并发已调整为 10；继续观察三方服务限流、机器资源和失败重试情况。
5. 队列满时统一进入 `queued` 状态；当前资产已支持，视频还主要是 `rendering`。
6. 视频生成过程中前端百分比进度未完整透传；火山接口百分比需要写入 `TaskRecord.progress`。
7. TTS 配音任务尚未实现，当前只是保留 `dubbing` 步骤和 `audio_url` 字段。
8. 清理 `backend/app/routers/conversations.py` 的重复路由定义。
9. 剧本解析 prompt 应减少/限制 `script_excerpt` 原文照抄长度，降低 JSON 超长和截断概率。

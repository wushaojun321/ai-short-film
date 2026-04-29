# TODO / 当前待办

## 已完成

1. 分镜剧照页面增加轮询，后台状态变化后前端可感知。
2. 支持删除项目：`DELETE /api/v1/projects/{project_id}` 已实现。
3. 支持单个资产/分镜图/分镜视频单独触发生成。
4. 分镜视频生成时已有 `rendering` 状态，分镜图生成时已有 `generating` 状态。
5. 资产生成已有 `queued` / `generating` 状态。

## 待处理

1. LLM 剧本解析仍可能返回非法 JSON，前端显示 `Unterminated string...`；需要增强 `chat_json` 截断检测、JSON 修复和错误上下文日志。
2. 有时候生成卡通而不是真人：继续调试 `asset_prompt_gen`、`shot_image_gen` 的写实约束。
3. 重启之后继续监控图片、视频生成进度，不要断；需要任务恢复/补偿机制。
4. 分镜剧照生成完成但列表预览偶发不显示，点击放大可看到；需要检查 COS URL、懒加载和状态刷新。
5. 分镜剧照步骤过后再回来，应仍可点击查看大图，且审核标识不要遮挡预览操作。
6. 图片并发目标 20、视频并发目标 10 尚未调整；当前 Docker Compose 为 `worker-image -c 4`、`worker-video -c 2`。
7. 队列满时统一进入 `queued` 状态；当前资产已支持，分镜图片/视频还主要是 `generating` / `rendering`。
8. 视频生成过程中前端百分比进度未完整透传；火山接口百分比需要写入 `TaskRecord.progress`。
9. TTS 配音任务尚未实现，当前只是保留 `dubbing` 步骤和 `audio_url` 字段。
10. 清理 `backend/app/routers/conversations.py` 的重复路由定义。
11. 剧本解析 prompt 应减少/限制 `script_excerpt` 原文照抄长度，降低 JSON 超长和截断概率。

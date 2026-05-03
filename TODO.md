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
11. 人物资产图片改为面部 / 全身 / 侧面三张独立图，图片确认页按人物资产包聚合展开；资产提示词已调整为写实电影质感。
12. 剧本解析已开始引入 `ProductionBlueprint` 中间真相层：分集蓝图、每集资产需求、人物圣经、人物阶段资产、场景/道具圣经和蓝图校验结果先写入蓝图，再派生现有 `Episode` / `Asset` 记录。

## 待处理

1. 用真实长剧本重新解析回归：检查每集 `script_excerpt` 是否为原文、`dialogue_count` 是否符合预期、`source_integrity` 是否为 `original`。
2. 选 1-2 集重新生成分镜：检查 `Shot.dialogues` 的台词原文保留率、说话人准确率、台词镜数量。
3. LLM 结构化输出仍需加固：增强 `chat_json` 截断检测、JSON 修复重试、错误上下文日志和 schema 校验。
4. 资产解析第二阶段：给资产增加适用集数 / block 范围 / 场景阶段绑定，避免镜头选错人物造型资产。
5. 分镜输入增强：把本集原文起止行、对白数量、相关阶段资产、上一集结尾连续性状态传入 `gen_shot_script_task`。
6. 继续用真实项目回归资产生图风格，观察“超现实电影质感”是否仍偏卡通，并按失败样例继续收紧负向约束。
7. 重启之后继续监控图片、视频生成进度，不要断；需要任务恢复/补偿机制。
8. 图片并发已调整为 20、视频并发已调整为 10；继续观察三方服务限流、机器资源和失败重试情况。
9. 队列满时统一进入 `queued` 状态；当前资产已支持，视频还主要是 `rendering`。
10. 视频生成过程中前端百分比进度未完整透传；火山接口百分比需要写入 `TaskRecord.progress`。
11. TTS 配音任务尚未实现，当前只是保留 `dubbing` 步骤和 `audio_url` 字段。
12. 清理 `backend/app/routers/conversations.py` 的重复路由定义。

## 待真实项目测试后再优化

> 这些事项来自本地短剧流程 `prompt-spec.md` / `schema-reference.md` / `workflow-tuning-guide.md` 的实跑经验。当前先记录方向，等新蓝图解析链路用真实项目跑完后，再按失败样例逐项落地，避免一次改动过大。

1. 补独立 `ScriptAnalysisAgent`：在 `ProductionBlueprint` 中增加 `script_analysis`，结构化记录主要人物、人物关系、主线/副线、关键节点、分集切点候选、角色状态变化线和原稿风险点。
2. 把 `BeatPlanningAgent` 做成正式阶段：每集先拆 `beat / 片段`，再拆镜头；片段需包含功能、场景、人物、开头状态、结尾落点、与前后片段衔接方式和片段级资产需求。
3. 升级资产结构：从当前通用 `Asset` 卡片逐步拆出 `CharacterCore`、`CharacterLook`、`ScenePackage`、`SceneView`、`PropPackage`、`KeyframeRequirement` 等更细数据边界。
4. 升级 `ShotAssetBinding`：增加 `character_id`、`look_id`、`scene_id`、`scene_view_id`、`role_in_shot`、`speaker/listener`、`keyframe_id`、`tail_frame_policy`，避免只靠 `asset_id / asset_name`。
5. 做确定性 `ShotPreflightValidator`：生成视频前检查每镜是否绑定角色和场景资产、有台词是否声明 `speaker_id`、多人镜是否声明 speaker/listener、使用 last_frame 时是否仍有角色/场景资产、台词字数是否超出时长承载。
6. 持久化 `SeedanceRequestPackage`：保存每次真实提交的视频请求包，包括 text prompt、参考图 `image_url` 列表、ratio、duration、return_last_frame、watermark 等，前端展示“真实提交内容”。
7. 增加高风险镜头识别和可选关键帧：片段首镜、三人以上关系镜、复杂动作镜、身份易混镜、悬念落点镜可先生成关键帧；关键帧只能辅助构图，不能替代角色/场景资产绑定。
8. 将本地实跑调优规则产品化：景别配比、机位方向、时间分段动作、观察镜视线方向、说话人排斥项、空间坐标继承、道具/服装连续性硬规则。

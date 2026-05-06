# TODO / 当前待办

## 已完成

1. 分镜剧照页面增加轮询，后台状态变化后前端可感知。
2. 支持删除项目：`DELETE /api/v1/projects/{project_id}` 已实现。
3. 支持单个资产/单镜头视频单独触发生成；分镜图接口保留为兼容能力，但不在当前主流程展示。
4. 分镜视频生成时已有 `rendering` 状态。
5. 资产生成已有 `queued` / `generating` 状态。
6. 分镜脚本生成已加入短期版片段元数据：LLM 先输出 `segments`，后端展平成 Shot，并按镜头功能归一化 2-8 秒时长。
7. 剧本解析已收敛为低 token 的单次综合规划：`ScriptIndexer` 原文索引 + `ScriptProductionPlanAgent` JSONL 蓝图 + 后端原文回填和资产归并，不再串行调用多个解析 Agent。
8. 新增 `script_blocks` 集合；`Episode.script_excerpt` 由原文块回填，避免长剧本摘要化后丢失台词。
9. 分集数据已增加诊断字段：原文起止行、对白行数、原文完整性，并在分集确认页和制作页展示。
10. 人物资产解析已增加 `asset_package` / `face_identity`，同一人物不同造型共享面部基准，资产生图提示词会继续沿用该基准。
11. 人物资产图片改为面部 / 全身 / 侧面三张独立图，图片确认页按人物资产包聚合展开；资产提示词已调整为写实电影质感。
12. 剧本解析已开始引入 `ProductionBlueprint` 中间真相层：分集蓝图、每集资产需求、人物圣经、人物阶段资产、场景/道具圣经和蓝图校验结果先写入蓝图，再派生现有 `Episode` / `Asset` 记录。
13. LLM 调用链路已增加 `llm_call_records` 轻量审计，记录 scope、输入/输出字符数、token 用量、耗时和项目/分集/镜头关联，便于定位 token 热点。
14. 分镜视频生成已增加最终提示词输入 hash，镜头描述、台词、资产引用和敏感词黑名单未变化时复用已保存的 `submitted_prompt`，减少重复调用 `ShotPromptAgent`。
15. Agent 对话已限制最近 10 轮上下文，并压缩项目级资产快照，避免长对话反复投喂资产提示词。
16. 分镜片段细化已按 `key_asset_ids` 收缩资产索引，LLM 未输出片段资产时才回退本集候选资产。
17. 人物资产三视图继续保持纯文本独立生成，但解析和最终提示词新增 `distinctive_traits`、`avoid_similar_to`、`look_lock`，用于锁定同一阶段发型/服装/配饰并拉开不同角色面部差异。
18. 会话路由重复定义已清理，只保留带项目归属校验的 `/conversations` 接口实现。
19. 剧本解析已拆成明确模块：`ParseOrchestrator`、`ScriptContextPackBuilder`、`ProductionBlueprintPlanner`、`BlueprintSchemaValidator`、`EpisodeMaterialBuilder`、`ContinuitySeedBuilder`、`AssetRegistryBuilder`、`ParseReportBuilder`；外部任务名和 API 保持不变。
20. 分镜视频批量生成已改为片段链式调度：顶部「生成所有镜头」会按连续 `segment_code` 拆成多个链式任务，片段之间并发，片段内按镜头顺序生成并传递上一镜 `last_frame_url`。

## 待处理

1. 用真实长剧本重新解析回归：检查每集 `script_excerpt` 是否为原文、`dialogue_count` 是否符合预期、`source_integrity` 是否为 `original`。
2. 选 1-2 集重新生成分镜：检查 `Shot.dialogues` 的台词原文保留率、说话人准确率、台词镜数量。
3. LLM 结构化输出仍需加固：在已有截断检测、JSON 修复和调用审计基础上，继续补 schema 校验和可视化调用统计页。
4. 资产解析第二阶段：给资产增加适用集数 / block 范围 / 场景阶段绑定，避免镜头选错人物造型资产。
5. 分镜输入增强：把本集原文起止行、对白数量、相关阶段资产、上一集结尾连续性状态传入 `gen_shot_script_task`。
6. 继续用真实项目回归资产生图风格，观察“写实电影质感”是否仍偏卡通，并按失败样例继续收紧负向约束。
7. 重启之后继续监控图片、视频生成进度，不要断；需要任务恢复/补偿机制。
8. 图片并发已调整为 20、视频 worker 并发为 10；当前视频批量入口按片段链并发，不再等同于“同一集所有镜头同时并发”。
9. 队列满时统一进入 `queued` 状态；当前资产已支持，视频批量链路用 `TaskRecord` 表示排队/执行进度，但 Shot 状态仍主要是 `rendering`。
10. 视频生成过程中前端百分比进度未完整透传；火山接口百分比需要写入 `TaskRecord.progress`。
11. TTS 配音任务尚未实现，当前只是保留 `dubbing` 步骤和 `audio_url` 字段。
12. 继续把解析旧 helper 从 `backend/app/tasks/llm_tasks.py` 迁移到 `backend/app/parsing/`，等分镜链路完成复用替换后再删除旧兼容函数。
13. 视频生成前增加确定性 `ShotPreflightValidator`，优先本地检查台词、资产、转场、上一镜尾帧，只有脏镜头才交给 LLM 修复。

## 待真实项目测试后再优化

> 这些事项来自本地短剧流程 `prompt-spec.md` / `schema-reference.md` / `workflow-tuning-guide.md` 的实跑经验。当前先记录方向，等新蓝图解析链路用真实项目跑完后，再按失败样例逐项落地，避免一次改动过大。

1. 评估是否补独立 `ScriptAnalysisAgent`：当前生产路径优先保持单次综合解析降低成本；如真实长剧本仍出现人物关系、状态线或资产阶段误判，再把“剧情理解”拆成独立模块，并在 `ProductionBlueprint` 中增加 `script_analysis`。
2. 把 `BeatPlanningAgent` 做成正式阶段：每集先拆 `beat / 片段`，再拆镜头；片段需包含功能、场景、人物、开头状态、结尾落点、与前后片段衔接方式和片段级资产需求。
3. 升级资产结构：从当前通用 `Asset` 卡片逐步拆出 `CharacterCore`、`CharacterLook`、`ScenePackage`、`SceneView`、`PropPackage`、`KeyframeRequirement` 等更细数据边界。
4. 升级 `ShotAssetBinding`：增加 `character_id`、`look_id`、`scene_id`、`scene_view_id`、`role_in_shot`、`speaker/listener`、`keyframe_id`、`tail_frame_policy`，避免只靠 `asset_id / asset_name`。
5. 做确定性 `ShotPreflightValidator`：生成视频前检查每镜是否绑定角色和场景资产、有台词是否声明 `speaker_id`、多人镜是否声明 speaker/listener、使用 last_frame 时是否仍有角色/场景资产、台词字数是否超出时长承载。
6. 持久化 `SeedanceRequestPackage`：保存每次真实提交的视频请求包，包括 text prompt、参考图 `image_url` 列表、ratio、duration、return_last_frame、watermark 等，前端展示“真实提交内容”。
7. 增加高风险镜头识别和可选关键帧：片段首镜、三人以上关系镜、复杂动作镜、身份易混镜、悬念落点镜可先生成关键帧；关键帧只能辅助构图，不能替代角色/场景资产绑定。
8. 将本地实跑调优规则产品化：景别配比、机位方向、时间分段动作、观察镜视线方向、说话人排斥项、空间坐标继承、道具/服装连续性硬规则。

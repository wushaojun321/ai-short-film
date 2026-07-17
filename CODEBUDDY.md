# AI 短剧生产系统

## 项目概览

AI 辅助短剧（竖屏 9:16）从剧本到分集、资产、分镜、剧照、视频和合片的生产系统。

当前项目已经不是纯前端 Mock：

- 前端为 React/Vite 单页应用，已接入真实 API、登录态、项目数据、任务轮询和对话侧边栏。
- 后端为 FastAPI + MongoDB/Beanie + Redis/Celery，负责项目、分集、资产、分镜、任务记录、代码侧提示词和多轮对话。
- 生成任务拆成独立 Celery 队列：LLM、图像、视频、合片。
- 初始化阶段先解析分集和资产需求，创建资产记录；资产图片不再强制一次性全量生成，当前界面支持进入图片确认阶段后按需/批量生成。
- 人物资产保持三张独立纯文本生图：面部、全身、侧面。`face_identity` 锁同一角色面部，`distinctive_traits` / `avoid_similar_to` 拉开不同角色差异，`look_lock` 锁同一阶段发型、服装、配饰、伤势和道具。
- 分镜视频批量入口已改为片段链式调度：同一片段内按镜头顺序生成，后一镜可引用前一镜 `last_frame_url`；不同片段链可由 `worker-video` 并发执行。

## 技术栈

- **前端**：React 18 + TypeScript + Vite + Tailwind CSS + React Router 6
- **UI 组件**：自写组件 + shadcn/ui 风格（基于 Radix UI）
- **API 客户端**：`frontend/src/lib/api.ts`
- **状态转换**：`frontend/src/lib/transforms.ts`
- **认证**：JWT Bearer token，前端存储在 `localStorage`
- **后端**：Python 3.12 + FastAPI + Beanie + MongoDB
- **异步任务**：Celery + Redis
- **对象存储**：COS/S3 风格存储，STS 临时密钥用于前端访问
- **外部生成**：OpenRouter LLM、Seedream 图像、Seedance 视频
- **核心文档**：`docs/workflow-spec.md`
- **解析模块契约**：`docs/parse-workflow-spec.md`
- **后端说明**：`docs/backend-plan.md`
- **提示词调试**：`docs/prompt-debug.md`
- **火山 API 文档**：`docs/volcano/`

## 目录结构

```
ai-short-film/
├── frontend/src/
│   ├── App.tsx                       # 路由入口和登录保护
│   ├── lib/
│   │   ├── api.ts                    # axios 客户端、API 封装、任务轮询
│   │   ├── AuthContext.tsx           # 登录态
│   │   ├── CosContext.tsx            # COS 访问 URL 处理
│   │   ├── ProjectsContext.tsx       # 项目列表状态
│   │   ├── transforms.ts             # API 数据转前端视图模型
│   │   ├── data.ts                   # 前端视图类型和步骤定义
│   │   └── utils.ts
│   ├── components/
│   │   ├── AgentDialog.tsx           # 制品级多轮对话侧边栏
│   │   ├── EpisodeSidebar.tsx
│   │   ├── EpisodeStepBar.tsx
│   │   ├── StepContent.tsx           # 分镜/剧照/视频/合片步骤 UI
│   │   └── screens/
│   │       ├── NewProjectScreen.tsx   # 上传剧本、等待解析、分集与资产、图片确认
│   │       └── ProjectStudioScreen.tsx
│   └── pages/
│       ├── LoginPage.tsx
│       ├── ProjectsHome.tsx
│       ├── NewProjectPage.tsx
│       └── ProjectDetailPage.tsx
├── backend/app/
│   ├── main.py                       # FastAPI 入口，统一 id 归一化
│   ├── models/                       # Beanie 文档模型
│   ├── routers/                      # REST API
│   ├── services/                     # LLM/图像/视频/存储/业务服务
│   ├── tasks/                        # Celery 任务
│   ├── prompts/                      # 默认提示词
│   ├── tools/                        # Agent 可调用工具
│   └── agent/                        # 对话 Agent 运行器
├── docs/
│   ├── workflow-spec.md
│   ├── backend-plan.md
│   ├── prompt-debug.md
│   └── volcano/
├── docker-compose.yml
└── TODO.md
```

## 路由结构

```
/login                      → 登录/邀请码注册
/                            → /projects
/projects                    → 项目列表
/projects/new                → 新建项目
/projects/:projectId         → 项目详情
  initStatus !== initialized → NewProjectScreen
  initStatus === initialized → ProjectStudioScreen
```

前端 API 默认走 `/api/v1`，可通过 `VITE_API_URL` 覆盖。

## 当前初始化流程

```
阶段 1：上传剧本
  → 上传 .txt/.docx/.pdf → 配置目标最低集数、最短时长、补充说明 → 触发 LLM 解析任务

阶段 1.5：等待解析
  → 前端轮询 TaskRecord → 展示进度和日志 → 成功后加载分集草案

阶段 2：分集与资产
  → 用户审核/编辑分集 → 确认分集 → 查看解析出的资产记录

阶段 3：图片确认
  → 对资产单独/批量生成图片 → 审核确认资产 → 确认初始化完成
```

注意：解析任务会创建 `Episode` 和 `Asset` 记录，但资产图片由 `worker-image` 后续生成，不是解析阶段一次性全部出图。

解析阶段当前已经拆成模块化主链路：

```
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

解析阶段只有 `ProductionBlueprintPlanner` 读取轻量 `script_index` 并调用 LLM。其他模块只读取 `ProductionBlueprint` 和 `ScriptBlock` 做确定性派生，避免分集、资产、连续性模块重复投喂完整剧本。

## 单集制作流程

前端当前将审核合并进生成步骤，视图上是 5 个主步骤：

```
1. 分镜脚本      → worker-llm 先拆片段，再生成 Shot 列表、台词、资产绑定
2. 分镜视频      → worker-video 生成视频；单镜可独立生成，批量入口按片段链并发、片段内顺序生成
3. 配音          → 类型和步骤保留，实际 TTS 任务尚未落地
4. 合并成片      → worker-merge 使用 ffmpeg 拼接 approved 镜头
5. 完成          → 展示 final_video_url
```

后端 `EpisodeStep` 仍保留更细状态：

```
storyboard_script → storyboard_images → image_review → storyboard_videos
→ video_review → dubbing → merge → done
```

## 关键数据类型

后端真实枚举以 `backend/app/models/` 为准：

```typescript
ProjectInitStatus =
  "not_started" | "script_uploaded" | "episodes_confirmed" |
  "assets_confirmed" | "initialized"

EpisodeStatus = "not_started" | "in_progress" | "completed"

EpisodeStep =
  "storyboard_script" | "storyboard_images" | "image_review" |
  "storyboard_videos" | "video_review" | "dubbing" | "merge" | "done"

ShotState =
  "planned" | "asset_required" | "generating" | "asset_ready" |
  "rendering" | "rendered" | "review_failed" | "approved"

AssetStatus =
  "pending" | "queued" | "generating" | "approved" |
  "need_regen" | "missing"

TaskStatus =
  "pending" | "running" | "success" | "failed" | "cancelled"
```

## API 结构

所有业务接口都挂在 `/api/v1` 下，并要求 Bearer token，除了登录注册。

主要路由：

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login

GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
POST   /api/v1/projects/{project_id}/upload-script
POST   /api/v1/projects/{project_id}/confirm-episodes
POST   /api/v1/projects/{project_id}/confirm-assets

GET    /api/v1/projects/{project_id}/episodes
GET    /api/v1/projects/{project_id}/episodes/{episode_id}?include_shots=true
PATCH  /api/v1/projects/{project_id}/episodes/{episode_id}
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/advance-step
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/set-step

GET    /api/v1/projects/{project_id}/episodes/{episode_id}/shots
PATCH  /api/v1/projects/{project_id}/episodes/{episode_id}/shots/{shot_id}
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/shots/{shot_id}/review
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/shots/batch-review

GET    /api/v1/projects/{project_id}/assets
PATCH  /api/v1/projects/{project_id}/assets/{asset_id}
DELETE /api/v1/projects/{project_id}/assets/{asset_id}
POST   /api/v1/projects/{project_id}/assets/{asset_id}/confirm
POST   /api/v1/projects/{project_id}/assets/{asset_id}/regen

POST   /api/v1/generate/projects/{project_id}/parse-script
POST   /api/v1/generate/episodes/{episode_id}/shot-script
POST   /api/v1/generate/assets/{asset_id}/image
POST   /api/v1/generate/shots/{shot_id}/image
POST   /api/v1/generate/shots/{shot_id}/video
POST   /api/v1/generate/episodes/{episode_id}/shot-videos
POST   /api/v1/generate/episodes/{episode_id}/merge
GET    /api/v1/generate/tasks/{record_id}/progress       # SSE，当前前端主要使用普通轮询

GET    /api/v1/tasks/{record_id}
GET    /api/v1/tasks

GET    /api/v1/conversations
POST   /api/v1/conversations
GET    /api/v1/conversations/{conversation_id}
DELETE /api/v1/conversations/{conversation_id}
POST   /api/v1/conversations/{conversation_id}/chat

GET    /api/v1/admin/prompt-configs
GET    /api/v1/admin/prompt-configs/{scope}
```

## ID 字段规范（`_id` vs `id`）

Beanie/MongoDB 原生序列化用 `_id`，为保证前后端一致，所有 API 响应统一输出 `id`：

- 后端：`app/main.py` 注册了 `normalize_id_middleware`，递归将 `_id` 改为 `id`。
- 前端：`frontend/src/lib/api.ts` 的 axios 响应拦截器也做同样转换，作为双重保险。
- 规则：前端代码一律用 `.id`，不要用 `._id`。
- 外键：`project_id`、`episode_id` 等字段名不变。

## 任务队列

Celery 队列和 Docker Compose 服务对应关系：

| 服务 | 队列 | 作用 |
| --- | --- | --- |
| `worker-llm` | `llm` | 剧本综合规划、分镜片段规划/细化、对话 Agent |
| `worker-image` | `image` | 资产图片、兼容性分镜剧照接口 |
| `worker-video` | `video` | 分镜视频；批量入口按片段创建链式任务 |
| `worker-merge` | `merge` | 整集视频拼接 |

解析剧本时报错时，优先看 `worker-llm`；图片生成看 `worker-image`；视频生成看 `worker-video`。

## 主题

当前前端采用深色现代工作台风格：浅黑/中性色背景，科技绿作为主操作色，避免高饱和蓝青和过强霓虹。
颜色 token 在 `tailwind.config.js` 和全局样式中定义，可使用 `bg-bg`、`text-sub`、`border-line` 等。

## 部署

服务器通过 `ssh root@YOUR_SERVER_IP` 访问，使用 Docker Compose 部署，代码在 `/root/ai-short-film`。

> **部署注意**：所有 worker 容器共享后端 Python 代码。模型、枚举、任务、服务、提示词等代码有任何变更时，必须 build 并重启对应 worker。只重启 `api` 或 `frontend` 不会更新 `worker-llm`、`worker-image`、`worker-video`、`worker-merge` 的代码。

```bash
# 标准部署流程（代码已推到 gitee 后执行）
ssh root@YOUR_SERVER_IP "cd /root/ai-short-film && ./scripts/update-server.sh"

# 只重建/重启部分服务
ssh root@YOUR_SERVER_IP "cd /root/ai-short-film && SERVICES='api worker-llm worker-video' ./scripts/update-server.sh"

# 仅重启不重新 build（只改环境变量或临时重启时）
ssh root@YOUR_SERVER_IP "cd /root/ai-short-film && docker compose restart"

# 查看服务状态
ssh root@YOUR_SERVER_IP "cd /root/ai-short-film && docker compose ps"

# 查看日志
ssh root@YOUR_SERVER_IP "cd /root/ai-short-film && docker compose logs -f api"
ssh root@YOUR_SERVER_IP "cd /root/ai-short-film && docker compose logs -f worker-llm"
ssh root@YOUR_SERVER_IP "cd /root/ai-short-film && docker compose logs -f worker-image"
ssh root@YOUR_SERVER_IP "cd /root/ai-short-film && docker compose logs -f worker-video"
```

> **容器代码不会自动更新**：`git pull` 只更新宿主机文件，`docker compose restart` 只重启旧镜像里的进程。代码变更必须重新 build。

> **Dockerfile 依赖是硬编码的**：`backend/Dockerfile` 中的 `uv pip install ...` 列表与 `pyproject.toml` 独立维护。新增 Python 依赖时必须同时更新两边。

服务清单：

- `frontend`：nginx，80/443，前端静态文件 + API 反代
- `api`：FastAPI 主进程
- `worker-llm`：Celery LLM 队列，并发 2
- `worker-image`：Celery 图像队列，并发 20
- `worker-video`：Celery 视频队列，并发 10
- `worker-merge`：Celery 合并队列，并发 1
- `mongodb`：MongoDB 7，宿主机端口 27018
- `redis`：Redis 7，宿主机端口 6380
- `v2ray`：代理，供 LLM/API 外网访问

环境变量：`backend/.env`（不入 git）。

## 当前实现与工作流文档的关系

`docs/workflow-spec.md` 是目标工作流规范，当前代码已经实现主链路，但仍有差距：

- 已实现：项目/用户隔离、剧本上传、原文索引、分集和资产记录、资产图、单镜视频、按片段链式批量视频生成、合片、任务记录、进度轮询、代码侧提示词配置、制品对话入口。
- 解析链路已经收敛为“原文索引 + 单次综合 JSONL 规划 + 后端归并派生”：`ScriptIndexer` 保留原文块和行号，`ScriptProductionPlanAgent` 一次输出 series / episodes / asset registry / ignore / warning 行，后端再回填 `Episode.script_excerpt` 并派生 `ProductionBlueprint`、`Episode`、`Asset`。
- 这不是串行多 Agent 解析；多模块解析目前只作为后续演进选项，需等真实项目验证单次综合解析的瓶颈后再拆。
- LLM 调用已写入 `llm_call_records`，可按 `scope`、项目、分集、镜头追踪输入/输出字符、token 用量和耗时。
- 视频生成前 `ShotPromptAgent` 的最终提示词已加输入 hash 缓存；镜头、资产引用、台词和敏感词黑名单未变化时复用 `submitted_prompt`，避免重复调用 LLM。
- 分镜片段细化阶段优先只传当前片段 `key_asset_ids` 对应资产，LLM 未给片段资产 id 时才回退本集候选资产。
- 部分实现：短期版片段元数据、资产按需生成、连续性注入、参考图策略、片段内上一镜尾帧辅助、敏感词重试、审核状态机。
- 未完全实现：独立 beat/片段实体、镜头级资产绑定 schema、自动缺失资产检查、提交前校验器、片段预览、TTS 配音任务、视频生成百分比透传、任务恢复监控、队列满时的 queued 状态全链路、Seedance 请求包持久化。

## 后续测试后再落地的优化方向

这组方向来自 `/Users/vanky/code/short film/docs/prompt-spec.md`、`schema-reference.md` 和 `workflow-tuning-guide.md` 的本地实跑经验。当前先记录，不要在未跑真实项目前继续大幅扩展，避免把新蓝图链路和镜头执行链路同时改复杂。

优先级建议：

1. `ScriptAnalysisAgent`：暂不作为默认解析链路；如果真实长剧本继续暴露人物关系、角色状态线或资产阶段误判，再新增独立剧本理解层，写入 `ProductionBlueprint.script_analysis`。它只做理解，不拆镜头。
2. `BeatPlanningAgent`：将片段/beat 做成正式阶段和可审核数据。每集先拆片段，再拆镜头；片段字段至少包含 `beat_id`、功能、场景、人物、开头状态、结尾落点、转场方式、片段级资产需求。
3. 资产结构细化：当前 `Asset` 可继续作为前端卡片兼容层，但蓝图层应逐步拆出 `CharacterCore`、`CharacterLook`、`ScenePackage`、`SceneView`、`PropPackage`、`KeyframeRequirement`。
4. 镜头资产绑定升级：`ShotAssetBinding` 不应长期只有 `asset_id / asset_name`，需要增加 `character_id`、`look_id`、`scene_id`、`scene_view_id`、`role_in_shot`、`speaker/listener`、`keyframe_id`、`tail_frame_policy`。
5. `ShotPreflightValidator`：视频提交前做确定性校验，不只依赖 LLM 修复。必检项包括每镜绑定角色/场景、有台词必须有说话人、多人镜声明 speaker/listener、last_frame 只能辅助不能替代资产、台词字数和镜头时长匹配。
6. `SeedanceRequestPackage` 持久化：每次真实提交给 Seedance 的 text prompt、参考图 URL 列表、ratio、duration、return_last_frame、watermark、模型名都应保存，前端展示“真实提交内容”。
7. 高风险镜头关键帧：片段首镜、三人以上关系镜、复杂动作镜、身份易混镜、悬念落点镜可选关键帧；关键帧只锁构图/站位，不能替代角色和场景资产绑定。

已验证的执行原则：

- 每一个视频镜头都必须绑定角色资产和场景资产。
- `last_frame` 只能作为连续性辅助，不能替代角色/场景资产。
- 先拆片段，再拆短镜头，避免长镜头承担过多剧情任务。
- 有台词的镜头必须结构化说话人、静默角色和 mouth-sync 归属。
- 观察镜必须写清观察者位置、被观察者位置、身体朝向、头部朝向、视线方向和禁止看向。
- 场景切换需要过渡镜或空间重建镜，不能从近景硬切到近景。

## 已知代码风险

- `backend/app/routers/conversations.py` 的重复路由已清理；后续重点是补齐会话触发生成任务的场景覆盖、提示词快照和流式响应。
- `llm_service.chat_json()` 已有截断检测、JSON 修复和调用审计；下一步需要补 schema 校验、调用统计页和失败样例聚合。
- 提示词当前由 `backend/app/prompts/llm_prompts.py` 代码常量提供，`PromptConfig` 数据库模型和 `seed_data.py` 属于残留/预留结构；在线编辑、版本回滚当前不生效。
- 后端测试依赖需要在本机安装完整；当前测试依赖缺失时会出现 `ModuleNotFoundError: motor`。

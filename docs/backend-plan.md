# AI 短剧生产系统 — 后端实现计划

> **技术栈**：Python 3.12 · FastAPI · MongoDB · Beanie (ODM) · Celery · Redis · S3/OSS
>
> **文档目的**：记录后端目标架构和当前实现状态。本文最初是实现计划，当前项目已经落地了主链路，因此以下内容同时标注“已实现”和“待完善”的差距。
> 1. 各制品（分集规划、资产、分镜脚本、剧照、视频、配音）下的**多轮会话修改**机制
> 2. 所有 LLM/图像/视频 调用所使用的**系统提示词外部化管理**
> 3. REST API + Celery 异步任务调度方案

---

## 目录

1. [整体架构](#1-整体架构)
2. [数据模型设计](#2-数据模型设计)
3. [提示词配置系统](#3-提示词配置系统)
4. [多轮会话机制](#4-多轮会话机制)
5. [API 路由设计](#5-api-路由设计)
6. [Celery 任务调度设计](#6-celery-任务调度设计)
7. [目录结构](#7-目录结构)
8. [实现分阶段计划](#8-实现分阶段计划)

---

## 当前实现快照

截至当前代码，后端已经实现：

- JWT 登录/邀请码注册，所有业务路由默认需要 Bearer token。
- 项目按 `owner_id` 做用户隔离。
- 剧本上传、解析任务、分集确认、资产确认。
- 长剧本解析 Map-Reduce：超过 `10000` 字先走 `script_map` 分段摘要，再走 `script_parse` 总解析。
- `TaskRecord` 记录异步任务状态、进度、日志和结果。
- Celery 队列：`llm`、`image`、`video`、`merge`。
- 资产图片、分镜剧照、分镜视频、整集合并任务。
- 提示词已迁移为代码侧常量：`prompt_service.render()` 直接读取 `app.prompts.DEFAULT_PROMPTS`，不再查询 MongoDB 的 `prompt_configs`。
- Conversation + Agent 工具调用入口。
- `/generate/tasks/{record_id}/progress` SSE 端点和 `/tasks/{record_id}` 普通轮询端点；当前前端主要使用普通轮询。

仍未完全落地或需要加固：

- TTS 配音任务和音频合成。
- 结构化 beat/片段层。
- 视频生成百分比透传到前端。
- 队列满时统一 `queued` 状态。
- 任务恢复监控。
- 视频生成前自动缺失资产检查。
- `chat_json` 对 LLM 非法 JSON 的修复和截断诊断。
- `conversations.py` 中重复路由定义需要清理。

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 (React)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│                    FastAPI  应用层                               │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────────┐   │
│  │  REST API    │  │  SSE 事件流   │  │  WebSocket (可选)  │   │
│  └──────┬───────┘  └───────┬───────┘  └─────────┬──────────┘   │
│         └──────────────────┼─────────────────────┘             │
│                            │                                    │
│  ┌─────────────────────────▼──────────────────────────────┐    │
│  │                   Service 层                            │    │
│  │  ProjectService · EpisodeService · AssetService         │    │
│  │  ShotService · ConversationService · PromptService      │    │
│  └─────────────────────────┬──────────────────────────────┘    │
└────────────────────────────┼────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌────────▼───────┐  ┌────────▼───────┐  ┌───────▼────────┐
│   MongoDB       │  │  Redis          │  │  Celery Worker │
│   (Beanie ODM)  │  │  (Broker/Cache) │  │  (异步任务)    │
└─────────────────┘  └─────────────────┘  └───────┬────────┘
                                                   │
                              ┌────────────────────┼──────────────┐
                              │                    │              │
                     ┌────────▼──────┐  ┌──────────▼──┐  ┌───────▼─────┐
                     │  LLM 服务     │  │  图像生成    │  │  视频生成   │
                     │  (GPT/Claude) │  │  (Seedream)  │  │  (Seedance) │
                     └───────────────┘  └─────────────┘  └─────────────┘
```

### 关键设计决策

| 关注点 | 方案 | 理由 |
|--------|------|------|
| 异步任务 | Celery + Redis | 图像/视频生成耗时长，必须异步；任务状态轮询友好 |
| 实时推送 | SSE + 普通轮询 | 后端已有 SSE 端点；当前前端主要轮询 `GET /tasks/{record_id}` |
| ODM | Beanie | 原生 async，与 FastAPI 兼容最佳；支持 `Revision` 版本控制 |
| 提示词管理 | 代码常量 `backend/app/prompts/llm_prompts.py` | 当前实际运行链路直接读代码；调整后需要重新 build/restart 对应 worker |
| 会话修改 | 每个制品下挂载 `conversations` 子集合 | 支持多轮对话式修改，完整保留历史 |
| 文件存储 | S3/OSS | 剧照/视频/音频文件不入库，存对象存储，DB 只存 URL |

---

## 2. 数据模型设计

> 所有模型使用 Beanie Document，字段命名遵循 snake_case。

### 2.1 Project（项目）

```python
class ProjectInitStatus(str, Enum):
    not_started       = "not_started"
    script_uploaded   = "script_uploaded"
    episodes_confirmed = "episodes_confirmed"
    assets_confirmed  = "assets_confirmed"
    initialized       = "initialized"

class Project(Document):
    owner_id: PydanticObjectId | None = None  # 创建者用户 ID
    title: str
    genre: str
    format: str = "VERTICAL_9_16"
    target_episode_count: int = 0
    min_episode_duration: int = 120       # 秒
    init_status: ProjectInitStatus = ProjectInitStatus.not_started
    script_file_url: str | None = None    # 原始剧本文件 OSS URL
    script_text: str | None = None        # 解析后纯文本（供 LLM 使用）
    series_prompt: str | None = None      # 剧集总览提示词（LLM 生成）
    parse_notes: str | None = None        # 用户补充说明/连续性约束
    progress: int = 0                     # 0-100
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "projects"
        indexes = ["title", "owner_id"]
```

### 2.2 Episode（分集）

```python
class EpisodeStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed   = "completed"

class EpisodeStep(str, Enum):
    storyboard_script  = "storyboard_script"
    storyboard_images  = "storyboard_images"
    image_review       = "image_review"
    storyboard_videos  = "storyboard_videos"
    video_review       = "video_review"
    dubbing            = "dubbing"
    merge              = "merge"
    done               = "done"

class Episode(Document):
    project_id: PydanticObjectId
    number: int
    title: str
    summary: str = ""
    word_count: int = 0
    estimated_duration: int = 0           # 秒
    status: EpisodeStatus = EpisodeStatus.not_started
    current_step: EpisodeStep = EpisodeStep.storyboard_script
    continuity_notes: str = ""            # 上集结尾状态约束
    final_video_url: str | None = None    # 合并成片 URL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "episodes"
        indexes = [
            ("project_id", 1),
            [("project_id", 1), ("number", 1)],
        ]
```

### 2.3 Shot（分镜/镜头）

```python
class ShotState(str, Enum):
    planned        = "planned"
    asset_required = "asset_required"
    generating     = "generating"   # 剧照生成中
    asset_ready    = "asset_ready"
    rendering      = "rendering"    # 视频生成中
    rendered       = "rendered"
    review_failed  = "review_failed"
    approved       = "approved"

class ShotAssetBinding(BaseModel):
    asset_id: PydanticObjectId
    asset_name: str                       # 冗余存储，便于显示

class Shot(Document):
    project_id: PydanticObjectId
    episode_id: PydanticObjectId
    shot_code: str                        # "S01", "S02" ...
    order: int
    duration: int                         # 秒
    segment_code: str = ""                # 短期折中版：所属片段编号
    segment_name: str = ""                # 短期折中版：所属片段名称
    segment_function: str = ""            # 建立/试探/冲突/反应/过渡/悬念等
    shot_function: str = ""               # 建立镜/关系镜/台词镜/动作镜/反应镜等
    description: str                      # 导演式分镜描述
    dialogues: list[ShotDialogueLine] = [] # 一个镜头可有多句对白
    prompt: str = ""                      # 最终提交视频模型的提示词
    required_assets: list[ShotAssetBinding] = []
    state: ShotState = ShotState.planned
    version: str = "v1"
    image_url: str | None = None          # 剧照 OSS URL
    video_url: str | None = None          # 视频 OSS URL
    audio_url: str | None = None          # 配音 OSS URL
    last_frame_url: str | None = None     # 上一镜尾帧 URL
    review_comment: str = ""              # 审核拒绝原因
    generation_task_id: str | None = None # Celery task id
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "shots"
        indexes = [
            ("episode_id", 1),
            [("episode_id", 1), ("order", 1)],
        ]
```

### 2.4 Asset（资产）

```python
class AssetType(str, Enum):
    character = "character"
    scene     = "scene"
    prop      = "prop"
    template  = "template"   # 群演模板

class AssetStatus(str, Enum):
    pending    = "pending"    # 待确认
    queued     = "queued"     # 已入队，等待 worker
    generating = "generating" # worker 已接单，生成中
    approved   = "approved"   # 已生成/已确认
    need_regen = "need_regen" # 需重生
    missing    = "missing"    # 缺失

class AssetVersion(BaseModel):
    version: str
    url: str
    prompt: str
    note: str = ""
    view_type: str = ""                   # 人物视角：face / full_body / side
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Asset(Document):
    project_id: PydanticObjectId
    name: str
    asset_type: AssetType
    status: AssetStatus = AssetStatus.pending
    prompt: str = ""                      # 当前采用的生成提示词
    voice_profile: str = ""               # 人物资产的固定音色
    character_name: str = ""              # 人物资产对应的角色本名
    asset_package: str = ""               # 人物资产包；同一角色不同造型共用
    face_identity: str = ""               # 共享面部基准；同一资产包保持同一张脸
    distinctive_traits: list[str] = []     # 当前角色区别于其他角色的固定面部差异点
    avoid_similar_to: list[str] = []       # 避免相似的角色或排斥特征
    look_lock: str = ""                    # 当前阶段发型、胡须、服装、配饰、伤势、道具锁定
    scene_scope: str = ""                 # 人物资产适用场景
    appearance_stage: str = ""            # 人物资产适用剧情/造型阶段
    view_requirements: str = ""           # 人物资产视角要求
    preview_url: str | None = None        # 当前预览图 URL
    view_urls: dict[str, str] = {}         # 人物三视角图：face / full_body / side
    versions: list[AssetVersion] = []     # 历史版本
    generation_task_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "assets"
        indexes = [
            ("project_id", 1),
            [("project_id", 1), ("asset_type", 1)],
        ]
```

### 2.5 Conversation（多轮会话）

> 这是支持"在制品下多轮对话修改"的核心模型。
> 每个制品（Shot、Asset、Episode）都可以挂载一个或多个 Conversation。

```python
class ConversationRole(str, Enum):
    user      = "user"
    assistant = "assistant"
    system    = "system"

class ConversationTarget(str, Enum):
    """会话关联的制品类型"""
    project         = "project"          # 项目级（剧集总览修改）
    episode         = "episode"          # 分集（分集规划/连续性约束修改）
    shot_script     = "shot_script"      # 分镜脚本修改
    shot_image      = "shot_image"       # 分镜剧照修改
    shot_video      = "shot_video"       # 分镜视频修改
    asset           = "asset"            # 资产修改

class Message(BaseModel):
    role: ConversationRole
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # 如果该消息触发了生成任务，记录任务 ID
    task_id: str | None = None
    # 生成结果的快照（图片URL、脚本文本等）
    artifact_snapshot: dict | None = None

class Conversation(Document):
    """每个制品下可以有多个会话（每次重改可开新会话，也可复用）"""
    target_type: ConversationTarget
    target_id: PydanticObjectId           # 关联的制品 ID（Shot/Asset/Episode）
    project_id: PydanticObjectId
    title: str = "新对话"                 # 会话标题（用于列表区分）
    messages: list[Message] = []
    # 当前使用的提示词配置快照（生成时锁定，便于追溯）
    prompt_config_snapshot: dict | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "conversations"
        indexes = [
            ("target_id", 1),
            ("project_id", 1),
            [("target_type", 1), ("target_id", 1)],
        ]
```

### 2.6 PromptConfig（提示词配置，当前为残留/预留模型）

当前主链路不从 MongoDB 读取提示词。`PromptConfig` 模型和 `prompt_configs` 集合仍在代码中保留，主要是历史结构或未来如果恢复在线编辑时的预留模型。

```python
class PromptConfigScope(str, Enum):
    """提示词作用范围"""
    script_parse          = "script_parse"          # 剧本解析
    episode_split         = "episode_split"          # 分集规划
    continuity_extract    = "continuity_extract"     # 连续性约束提取
    shot_script_gen       = "shot_script_gen"        # 分镜脚本生成
    shot_script_edit      = "shot_script_edit"       # 分镜脚本多轮修改
    asset_prompt_gen      = "asset_prompt_gen"       # 资产提示词生成
    asset_prompt_edit     = "asset_prompt_edit"      # 资产多轮修改
    shot_image_gen        = "shot_image_gen"         # 分镜图生成（发给 Seedream）
    shot_image_edit       = "shot_image_edit"        # 分镜图多轮修改
    shot_video_gen        = "shot_video_gen"         # 视频生成（发给 Seedance）
    shot_video_edit       = "shot_video_edit"        # 视频多轮修改
    dubbing_gen           = "dubbing_gen"            # 配音生成
    series_overview_edit  = "series_overview_edit"   # 剧集总览多轮修改
    script_map            = "script_map"             # 长剧本 Map 阶段摘要

class PromptConfig(Document):
    scope: PromptConfigScope
    name: str                             # 人类可读名称，如"分镜脚本生成-系统提示"
    system_prompt: str                    # 系统提示词正文
    user_prompt_template: str = ""        # 用户提示词模板（支持 {变量} 插值）
    description: str = ""                # 用途说明
    version: int = 1                      # 版本号（每次修改递增）
    is_active: bool = True                # 是否启用（可快速回滚到旧版）
    variables: list[str] = []            # 模板中用到的变量名列表，如 ["episode_summary", "continuity_notes"]
    created_by: str = "system"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "prompt_configs"
        indexes = [
            [("scope", 1), ("is_active", 1)],
        ]
```

### 2.7 TaskRecord（任务记录）

```python
class TaskStatus(str, Enum):
    pending   = "pending"
    running   = "running"
    success   = "success"
    failed    = "failed"
    cancelled = "cancelled"

class TaskRecord(Document):
    """Celery 任务的持久化记录，与 Celery result backend 互补"""
    celery_task_id: str
    task_type: str                        # "generate_shot_image", "generate_shot_video" 等
    project_id: PydanticObjectId | None = None
    episode_id: PydanticObjectId | None = None
    target_id: PydanticObjectId | None = None   # Shot/Asset ID
    status: TaskStatus = TaskStatus.pending
    progress: int = 0                     # 0-100
    result: dict | None = None            # 成功时的结果数据
    error: str | None = None             # 失败时的错误信息
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "task_records"
        indexes = [
            ("celery_task_id", 1),
            ("target_id", 1),
            [("project_id", 1), ("status", 1)],
        ]
```

---

## 3. 提示词配置系统

### 3.1 设计原则

- **当前实际方案**：所有 LLM scope 提示词集中在 `backend/app/prompts/llm_prompts.py`，运行时由 `backend/app/services/prompt_service.py` 直接读取代码常量 `DEFAULT_PROMPTS`。
- **部署生效方式**：修改提示词代码后，必须重新 build 并重启对应 worker；数据库里的 `prompt_configs` 不影响生成结果。
- **版本追踪**：当前没有在线版本回滚；版本随代码和 Git 记录管理。
- **快照锁定**：`render()` 会返回代码侧 config snapshot，但生成链路尚未系统性写入 Conversation 或 TaskRecord。
- **模板插值**：user_prompt_template 支持 `{变量名}` 占位符，由 Service 层在运行时填充
- **分 scope 管理**：每种生成场景独立配置，互不影响

### 3.2 提示词服务

```python
# app/services/prompt_service.py

_PROMPTS = {str(p["scope"].value): p for p in DEFAULT_PROMPTS}

async def render(scope: PromptConfigScope, variables: dict) -> tuple[str, str, dict]:
    config = _PROMPTS[str(scope.value)]
    system_prompt = config["system_prompt"].format(**variables)
    user_prompt = config.get("user_prompt_template", "").format(**variables)
    snapshot = {
        "scope": str(scope.value),
        "version": 1,
        "system_prompt": config["system_prompt"],
        "user_prompt_template": config.get("user_prompt_template", ""),
    }
    return system_prompt, user_prompt, snapshot
```

### 3.3 提示词清单

当前 `DEFAULT_PROMPTS` 包含以下 scope：

| scope | 用途 | 关键变量 |
|-------|------|---------|
| `script_parse` | 剧本整体解析，提取世界观/人物/情节线 | `script_text`, `target_episodes`, `min_duration`, `parse_notes` |
| `episode_split` | 将剧本拆分为 N 集，输出结构化 JSON | `script_text`, `series_context`, `target_episodes` |
| `continuity_extract` | 从剧本中提取跨集连续性约束 | `episode_script`, `prev_episode_ending` |
| `shot_script_gen` | 为单集生成完整分镜脚本 | `episode_script`, `continuity_notes`, `asset_list`, `series_style` |
| `shot_script_edit` | 多轮对话修改分镜脚本 | `current_script`, `user_instruction` |
| `asset_prompt_gen` | 为角色/场景/道具生成 Seedream 提示词 | `asset_description`, `style_guide`, `negative_prompt_rules` |
| `asset_prompt_edit` | 多轮修改资产提示词 | `current_prompt`, `asset_name`, `user_feedback` |
| `shot_image_gen` | 生成发给 Seedream 的最终提示词 | `shot_description`, `required_assets_prompts`, `continuity_notes`, `style_guide` |
| `shot_video_gen` | 生成发给 Seedance 的镜头提示词 | `shot_description`, `character_prompts`, `scene_prompt`, `camera_motion`, `dialogue` |
| `dubbing_gen` | 生成配音指令 | `dialogue_lines`, `character_voice_profiles` |
| `series_overview_edit` | 多轮修改剧集总览/世界观提示词 | `current_overview`, `user_instruction` |

---

## 4. 多轮会话机制

### 4.1 核心思路

前端在每个制品（分镜脚本、剧照、视频、资产）下都有一个**聊天侧边栏**，用户可以用自然语言向 AI 发出修改指令。后端将：

1. 将用户消息追加到该制品的 Conversation
2. 拼装上下文（历史消息 + 当前制品内容 + 对应系统提示词）
3. 调用 LLM，流式返回修改结果
4. 如果修改是"重新生成图/视频"，则发一个 Celery 任务，返回 task_id
5. 将 assistant 回复追加到 Conversation，更新制品状态

### 4.2 会话上下文构建规则

```
[系统提示词 (来自 PromptConfig)]
  + 当前制品内容快照
  + 历史 N 轮消息（默认保留最近 10 轮，防止超 token）
  + 用户最新消息
```

对于不同制品类型，"当前制品内容快照"不同：

| 制品类型 | 上下文快照内容 |
|---------|--------------|
| 分镜脚本 | 所有 Shot 的 description + assets 列表 |
| 分镜剧照 | 单个 Shot 的 description + imageUrl + prompt |
| 分镜视频 | 单个 Shot 的 description + videoUrl + prompt |
| 资产 | Asset 的 name + prompt + versions 历史 |
| 分集规划 | Episode 的 title + summary + word_count |

### 4.3 API 端点

```
POST /api/v1/conversations
  → 创建绑定 project/episode/shot_image/shot_video/asset 等目标的会话

GET  /api/v1/conversations?project_id=xxx&target_id=xxx
  → 获取会话列表

GET  /api/v1/conversations/{conversation_id}
  → 获取指定会话和消息列表

POST /api/v1/conversations/{conversation_id}/chat
  → 发送消息，后端执行 Agent tool-calling，当前返回完整 JSON 响应

DELETE /api/v1/conversations/{conversation_id}
  → 删除会话
```

### 4.4 响应方式

会话接口当前不是流式 SSE，而是 `POST /conversations/{id}/chat` 返回：

- `reply`
- `tool_calls_made`
- `conversation_id`

任务进度已有 SSE 端点 `/api/v1/generate/tasks/{record_id}/progress`，但前端当前主要通过 `GET /api/v1/tasks/{record_id}` 普通轮询。

### 4.5 修改能力矩阵

| 用户指令示例 | 后端行为 |
|------------|---------|
| "把第3镜的景别改成全景" | LLM 修改 Shot.description，同步更新数据库 |
| "重新生成这张剧照，风格更暗" | 更新 Shot.prompt，发 Celery 任务，返回 task_id |
| "给顾文池的提示词加上不得生成女性" | 更新 Asset.prompt，可选触发重生 |
| "把第2集的标题改成XXX" | 更新 Episode.title |
| "这集的连续性约束需要加上谢风凌有新伤" | 更新 Episode.continuity_notes |
| "调整世界观描述，突出权谋感" | 更新 Project.series_prompt |

---

## 5. API 路由设计

### 5.1 Projects

```
GET    /api/v1/projects                    # 项目列表
POST   /api/v1/projects                    # 创建项目
GET    /api/v1/projects/{project_id}       # 项目详情
PATCH  /api/v1/projects/{project_id}       # 更新项目基本信息
DELETE /api/v1/projects/{project_id}       # 删除项目

POST   /api/v1/projects/{project_id}/upload-script    # 上传剧本文件
POST   /api/v1/projects/{project_id}/confirm-episodes # 确认分集规划
POST   /api/v1/projects/{project_id}/confirm-assets   # 确认资产，完成初始化
```

剧本解析任务实际在 Generate 路由：

```
POST   /api/v1/generate/projects/{project_id}/parse-script
```

### 5.2 Episodes

```
GET    /api/v1/projects/{project_id}/episodes                      # 分集列表
POST   /api/v1/projects/{project_id}/episodes                      # 手动创建分集
GET    /api/v1/projects/{project_id}/episodes/{episode_id}         # 分集详情，可带 ?include_shots=true
PATCH  /api/v1/projects/{project_id}/episodes/{episode_id}         # 更新分集信息
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/advance-step
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/set-step
```

### 5.3 Shots（分镜）

```
GET    /api/v1/projects/{project_id}/episodes/{episode_id}/shots
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/shots
GET    /api/v1/projects/{project_id}/episodes/{episode_id}/shots/{shot_id}
PATCH  /api/v1/projects/{project_id}/episodes/{episode_id}/shots/{shot_id}
DELETE /api/v1/projects/{project_id}/episodes/{episode_id}/shots/{shot_id}
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/shots/{shot_id}/review
  body: {"approved": true, "comment": "..."}
POST   /api/v1/projects/{project_id}/episodes/{episode_id}/shots/batch-review
```

### 5.4 Assets（资产）

```
GET    /api/v1/projects/{project_id}/assets                        # 资产列表（支持 ?type=character|scene|prop）
POST   /api/v1/projects/{project_id}/assets                        # 手动创建资产
GET    /api/v1/projects/{project_id}/assets/{asset_id}             # 资产详情
PATCH  /api/v1/projects/{project_id}/assets/{asset_id}             # 更新资产
DELETE /api/v1/projects/{project_id}/assets/{asset_id}             # 删除资产
POST   /api/v1/projects/{project_id}/assets/{asset_id}/regen       # 触发重新生成
POST   /api/v1/projects/{project_id}/assets/{asset_id}/confirm     # 确认资产
```

### 5.5 Conversations（多轮会话）

```
GET    /api/v1/conversations?project_id=xxx&target_id=xxx          # 获取会话列表
POST   /api/v1/conversations                                       # 新建会话
GET    /api/v1/conversations/{conversation_id}                     # 会话详情（含消息列表）
POST   /api/v1/conversations/{conversation_id}/chat                # 发送消息
DELETE /api/v1/conversations/{conversation_id}                     # 删除会话
```

### 5.6 Tasks（任务状态）

```
GET    /api/v1/tasks/{record_id}                                   # 查询任务记录
GET    /api/v1/tasks?project_id=xxx&episode_id=xxx&task_type=xxx   # 任务列表

GET    /api/v1/generate/tasks/{record_id}/progress                 # SSE 实时推送任务进度
  # SSE 事件：{"progress": 60, "status": "running", "logs": [...]}
```

### 5.7 Prompt Configs（提示词管理 — Admin）

```
GET    /api/v1/admin/prompt-configs                                # 所有提示词配置列表
GET    /api/v1/admin/prompt-configs/{scope}                        # 指定 scope 的配置
```

当前代码只提供代码侧提示词查看接口；更新、历史和回滚接口尚未实现。该接口从 `_PROMPTS` 返回内容，不查 MongoDB。

---

## 6. Celery 任务调度设计

### 6.1 任务队列划分

```python
# celery_app.py
app = Celery("ai_short_film")
app.conf.task_routes = {
    "app.tasks.llm.*":   {"queue": "llm"},
    "app.tasks.image.*": {"queue": "image"},
    "app.tasks.video.*": {"queue": "video"},
    "app.tasks.merge.*": {"queue": "merge"},
}
# 启动命令示例（每个 worker 类型单独伸缩）：
# celery -A app.celery_app worker -Q llm -c 2
# celery -A app.celery_app worker -Q image -c 20
# celery -A app.celery_app worker -Q video -c 10
# celery -A app.celery_app worker -Q merge -c 1
```

当前没有 `audio` 队列和 TTS worker。

### 6.2 核心任务定义

```python
# app/tasks/llm_tasks.py

@celery_app.task(bind=True, name="app.tasks.llm.parse_script", queue="llm")
def parse_script_task(self, project_id: str):
    """
    解析剧本，返回：
    - series_prompt: 剧集总览
    - episodes: 分集草案列表
    - assets: 资产需求列表
    - continuity_items: 连续性约束列表
    """
    ...

@celery_app.task(bind=True, name="app.tasks.llm.gen_shot_script", queue="llm")
def gen_shot_script_task(self, episode_id: str, max_shot_duration: int = 8, feedback: str | None = None):
    """为整集生成所有分镜脚本；当前短期版会先输出 segments，再展平成 Shot"""
    ...
```

```python
# app/tasks/image_tasks.py

@celery_app.task(bind=True, name="app.tasks.image.gen_asset", queue="image")
def gen_asset_image_task(self, asset_id: str):
    """生成资产图片"""
    ...

@celery_app.task(bind=True, name="app.tasks.image.gen_shot_image", queue="image")
def gen_shot_image_task(self, shot_id: str):
    """
    调用 Seedream 生成分镜剧照：
    1. 从 DB 读取 Shot + 关联 Assets 的 prompt
    2. 调用 PromptService 构建完整提示词
    3. 调用 Seedream API
    4. 上传结果到 OSS
    5. 更新 Shot.image_url + state
    """
    ...

```

```python
# app/tasks/video_tasks.py

@celery_app.task(bind=True, name="app.tasks.video.gen_shot_video", queue="video")
def gen_shot_video_task(self, shot_id: str):
    """
    调用 Seedance 生成分镜视频：
    1. 读取 Shot + Assets + last_frame（上一镜尾帧）
    2. 构建 reference_strategy（角色资产 + 场景资产 + 可选尾帧）
    3. 调用 Seedance API（长耗时，更新进度）
    4. 上传 video_url + last_frame_url
    5. 更新 Shot.state = "rendered"
    """
    ...
```

```python
# app/tasks/merge_tasks.py

@celery_app.task(bind=True, name="app.tasks.merge.merge_episode", queue="merge")
def merge_episode_task(self, episode_id: str):
    """
    合并整集视频：
    1. 按 Shot.order 排序，收集所有 approved shot 的 video_url
    2. 下载到本地临时目录
    3. 调用 ffmpeg 拼接（带进度回调更新 TaskRecord.progress）
    4. 上传成片到 OSS
    5. 更新 Episode.final_video_url + status = "completed"
    """
    ...
```

### 6.3 任务进度推送机制

```
任务执行中 → 定期更新 TaskRecord.progress / logs / result / error
前端当前 → 轮询 GET /api/v1/tasks/{record_id}
可选能力 → SSE GET /api/v1/generate/tasks/{record_id}/progress
```

当前没有 Redis pub/sub 版本的 `/tasks/stream/{task_id}`。

### 6.4 批量任务策略

当前没有后端 batch task；批量生成由前端遍历多个镜头/资产，逐个调用生成接口，Celery 再按队列并发处理。后续如果要做真正的批量任务，可以再引入 `group/chord` 和批量 TaskRecord。

---

## 7. 目录结构

```
backend/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 环境配置（pydantic-settings）
│   ├── database.py                # Beanie 初始化
│   ├── celery_app.py              # Celery 实例
│   │
│   ├── models/                    # Beanie Document 模型
│   │   ├── __init__.py
│   │   ├── project.py
│   │   ├── episode.py
│   │   ├── shot.py
│   │   ├── asset.py
│   │   ├── conversation.py
│   │   ├── prompt_config.py
│   │   └── task_record.py
│   │
│   ├── schemas/                   # Pydantic 请求/响应 Schema
│   │   ├── project.py
│   │   ├── episode.py
│   │   ├── shot.py
│   │   ├── asset.py
│   │   ├── conversation.py
│   │   └── prompt_config.py
│   │
│   ├── routers/                   # FastAPI 路由
│   │   ├── projects.py
│   │   ├── episodes.py
│   │   ├── shots.py
│   │   ├── assets.py
│   │   ├── conversations.py
│   │   ├── tasks.py
│   │   └── admin/
│   │       └── prompt_configs.py
│   │
│   ├── services/                  # 业务逻辑层
│   │   ├── project_service.py
│   │   ├── episode_service.py
│   │   ├── shot_service.py
│   │   ├── asset_service.py
│   │   ├── conversation_service.py
│   │   ├── prompt_service.py      # 提示词配置管理 + 渲染
│   │   └── storage_service.py     # OSS 文件上传/下载
│   │
│   ├── tasks/                     # Celery 任务
│   │   ├── __init__.py
│   │   ├── llm_tasks.py           # LLM 调用任务
│   │   ├── image_tasks.py         # 图像生成任务
│   │   ├── video_tasks.py         # 视频生成任务
│   │   ├── merge_tasks.py         # 视频合并任务
│   │   └── base.py                # 任务辅助函数
│   │
│   ├── agent/                     # Agent 上下文和 runner
│   ├── tools/                     # Agent 工具
│   ├── prompts/                   # 默认提示词
│   │
│   └── utils/
│       └── seed_data.py           # 数据库种子数据（初始提示词）
│
├── tests/
│   ├── test_projects.py
│   ├── test_generation.py
│   └── ...
│
├── pyproject.toml
└── .env.example
```

---

## 8. 实现分阶段计划

### Phase 1：基础骨架

**目标**：跑通数据 CRUD，前端能从真实 API 读写数据。

- [x] 搭建 FastAPI + Beanie 骨架，连接 MongoDB
- [x] 实现主要数据模型（Project / Episode / Shot / Asset / TaskRecord / PromptConfig / Conversation / User）
- [x] 实现 Project / Episode / Shot / Asset 的基础 CRUD API
- [x] 实现文件上传接口（COS/S3 风格存储）
- [x] 代码侧默认提示词集中管理，`prompt_service.render()` 直接读取
- [~] Admin 提示词 API：当前只实现代码侧查看，更新/历史/回滚未实现
- [x] Docker Compose 运行 MongoDB、Redis、API、前端和各 worker

### Phase 2：Celery 异步任务 + 任务状态

**目标**：生成类操作全部异步化，前端能轮询进度。

- [x] 搭建 Celery + Redis，定义 `llm`、`image`、`video`、`merge` 队列
- [x] `TaskRecord` + 任务状态查询 API
- [x] 实现 `llm_tasks.py`：`parse_script_task`、`gen_shot_script_task`
- [x] 实现长剧本 Map-Reduce 解析
- [x] 实现 `image_tasks.py`：`gen_asset_image_task`、`gen_shot_image_task`
- [x] 实现 `video_tasks.py`：`gen_shot_video_task`
- [x] 实现 `merge_tasks.py`：`merge_episode_task`
- [~] 批量生成：当前前端逐个触发，未做后端 batch task
- [~] SSE 任务进度推送：已有 `/generate/tasks/{record_id}/progress`，前端主要用轮询

### Phase 3：多轮会话机制

**目标**：每个制品下的对话框能真实工作。

- [x] `Conversation` 模型 + CRUD
- [x] Agent 上下文构建和 tool-calling runner
- [x] `POST /conversations/{conversation_id}/chat` 返回完整 JSON
- [x] 前端会话侧边栏对接
- [~] 会话触发生成任务能力部分依赖 tools，仍需逐场景完善
- [ ] 提示词配置快照写入 Conversation / TaskRecord
- [ ] 流式 SSE 对话响应

### Phase 4：审核流程 + 合并成片

**目标**：完整走通单集从脚本到成片的全流程。

- [x] 图像/视频共用 Shot 审核 API（通过/拒绝/批量审核）
- [x] Shot 状态机（含 `generating`、`asset_ready`、`rendering`、`rendered`、`approved`）
- [ ] 缺失资产检查（视频生成前自动触发）
- [ ] TTS 配音生成
- [x] `merge_tasks.py`：ffmpeg 合并成片 + 进度回调
- [~] Episode 状态推进：步骤 API 和合片完成推进已实现，自动化仍可继续补

### Phase 5：生产加固

**目标**：稳定性、可观测性、安全性。

- [x] 接口鉴权（JWT Bearer）
- [ ] Celery 重试策略 + 死信队列
- [~] 任务幂等性（资产生成已有部分防重复，镜头生成仍需加强）
- [ ] 日志 + Sentry 错误追踪
- [ ] Prometheus metrics（任务成功率/耗时）
- [ ] 如需在线改 prompt，再补 PromptConfig 写入接口、版本历史和审计日志
- [ ] 压测 + 限流（对生成 API 的 rate limit）

---

## 附录：关键难点分析

### 难点 1：多轮会话 + 制品修改的一致性

**问题**：用户通过对话修改了分镜脚本，同时系统正在生成该集的剧照，数据可能不一致。

**方案**：
- Shot 级别的乐观锁（`updated_at` 版本检查）
- 生成任务开始时锁定 Shot 数据快照，不受后续修改影响
- 前端展示"已有进行中任务"警告，阻止并发修改

### 难点 2：LLM 输出结构化 JSON

**问题**：分镜脚本、分集规划等都需要 LLM 返回结构化数据，输出不稳定。

**方案**：
- 当前使用 OpenAI/OpenRouter `response_format={"type": "json_object"}` + prompt 严格约束。
- 后续应补 `finish_reason == "length"` 截断检测、JSON 修复重试、错误上下文日志。
- 可以再评估是否引入 Pydantic schema 校验或 `instructor`，但当前代码尚未真正使用它来约束输出。

### 难点 3：视频生成的长耗时 + 超时

**问题**：Seedance 视频生成可能耗时 60-300 秒，HTTP 请求会超时。

**方案**：
- 全部改为异步：API 只返回 `task_id`，前端轮询或 SSE 监听
- Celery task 设置 `time_limit=600`（10 分钟硬超时）
- 提供"取消任务"接口（当前尚未实现）

### 难点 4：连续性约束的传递

**问题**：上一集的结尾状态（服装/伤势/站位等）需要自动传递到下一集的分镜生成中。

**方案**：
- 当前已有 `Episode.continuity_notes` 字段，生成分镜脚本时会注入 prompt。
- 自动从上一集 shots 提取连续性（`continuity_extract`）尚未形成独立任务链。
- 允许人工编辑（通过对话或直接 PATCH）

### 难点 5：提示词版本管理与回滚

**问题**：修改了某个 scope 的提示词后，发现效果变差，需要快速回滚。

**方案**：
- 当前运行时提示词不读数据库，修改效果依赖代码发布和 worker 重启。
- Admin 查看接口已实现，返回代码侧 `_PROMPTS`；在线更新、历史版本列表和回滚接口尚未实现。
- `seed_prompt_configs()` 旧函数仍保留，但没有在 `main.py` 启动链路中调用。
- Conversation 中的 `prompt_config_snapshot` 字段已存在，但生成链路尚未系统性写入快照。

### 难点 6：长剧本解析不能丢失原文台词

**问题**：旧的长剧本 Map-Reduce 会先把原文压缩成摘要，再让 `script_parse` 生成分集。分集 `script_excerpt` 因此可能只剩剧情概述，后续分镜生成无法恢复原始台词。

**已落地方案**：
- 新增 `ScriptBlock` / `script_blocks` 集合，解析开始先做确定性原文索引。
- `parse_script_task` 内部拆为全剧规划、分集范围规划、原文回填、资产解析。
- `Episode.script_excerpt` 由后端根据 `source_block_ranges` 从原文块拼回，不再信任 LLM 重写正文。
- `Episode` 保存 `source_block_ids`、原文起止行、`dialogue_count` 和 `source_integrity`，用于排查分集材料质量。
- 旧项目不自动迁移；重新解析或新项目才使用新链路。

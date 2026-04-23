# AI 短剧生产系统 — 后端实现计划

> **技术栈**：Python 3.12 · FastAPI · MongoDB · Beanie (ODM) · Celery · Redis · S3/OSS
>
> **文档目的**：为配套前端（React 18）设计完整后端架构，重点覆盖：
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
| 实时推送 | SSE (Server-Sent Events) | 任务进度推送；比 WebSocket 简单，单向足够 |
| ODM | Beanie | 原生 async，与 FastAPI 兼容最佳；支持 `Revision` 版本控制 |
| 提示词管理 | MongoDB 集合 `prompt_configs` | 运营人员可通过后台 API/admin 动态修改，无需部署 |
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
        indexes = [("title", 1)]
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
    asset_ready    = "asset_ready"
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
    description: str                      # 导演式分镜描述
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
    approved   = "approved"   # 已生成/已确认
    need_regen = "need_regen" # 需重生
    missing    = "missing"    # 缺失

class AssetVersion(BaseModel):
    version: str
    url: str
    prompt: str
    note: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Asset(Document):
    project_id: PydanticObjectId
    name: str
    asset_type: AssetType
    status: AssetStatus = AssetStatus.pending
    prompt: str = ""                      # 当前采用的生成提示词
    preview_url: str | None = None        # 当前预览图 URL
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

### 2.6 PromptConfig（提示词配置）

> 所有 LLM/图像/视频 调用的系统提示词都存入此集合，
> 管理员可通过 Admin API 动态修改，无需重新部署。

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

- **运行时可改**：所有系统提示词存 MongoDB，Admin API 暴露 CRUD，无需重新部署
- **版本追踪**：每次修改创建新版本记录（或递增 version 字段），可回滚
- **快照锁定**：生成任务触发时，将当前使用的 PromptConfig 快照写入 Conversation 或 TaskRecord，便于事后复盘
- **模板插值**：user_prompt_template 支持 `{变量名}` 占位符，由 Service 层在运行时填充
- **分 scope 管理**：每种生成场景独立配置，互不影响

### 3.2 提示词服务

```python
# app/services/prompt_service.py

class PromptService:

    async def get_active(self, scope: PromptConfigScope) -> PromptConfig:
        """获取指定 scope 的当前激活配置，缓存 60s"""
        config = await PromptConfig.find_one(
            PromptConfig.scope == scope,
            PromptConfig.is_active == True,
        )
        if not config:
            raise ValueError(f"No active prompt config for scope: {scope}")
        return config

    async def render(
        self,
        scope: PromptConfigScope,
        variables: dict,
    ) -> tuple[str, str, dict]:
        """
        返回 (system_prompt, rendered_user_prompt, config_snapshot)
        snapshot 用于写入 Conversation/TaskRecord
        """
        config = await self.get_active(scope)
        user_prompt = config.user_prompt_template.format(**variables)
        snapshot = config.model_dump(include={"scope", "version", "system_prompt", "user_prompt_template"})
        return config.system_prompt, user_prompt, snapshot

    async def upsert(self, scope: PromptConfigScope, system_prompt: str, user_prompt_template: str, ...) -> PromptConfig:
        """更新提示词（版本递增，旧版本标记 is_active=False）"""
        ...
```

### 3.3 初始提示词清单（种子数据）

系统启动时自动 upsert 以下默认配置（若数据库中不存在）：

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
POST /api/v1/conversations/{target_type}/{target_id}/messages
  → 发送消息，流式返回（SSE）

GET  /api/v1/conversations/{target_type}/{target_id}
  → 获取会话历史列表

GET  /api/v1/conversations/{conversation_id}/messages
  → 获取指定会话的消息列表

POST /api/v1/conversations/{conversation_id}/new
  → 开启新的会话轮次（清空上下文重来）
```

### 4.4 流式响应（SSE）

```python
# 前端收到的 SSE 事件类型：
data: {"type": "text_delta", "content": "正在修改第3个镜头..."}
data: {"type": "artifact_update", "artifact": {"shots": [...]}}   # 修改后的制品
data: {"type": "task_created", "task_id": "abc123", "task_type": "generate_shot_image"}
data: {"type": "done"}
data: {"type": "error", "message": "..."}
```

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
POST   /api/v1/projects/{project_id}/parse-script     # 触发剧本解析（异步任务）
GET    /api/v1/projects/{project_id}/parse-status     # 查询解析任务状态
POST   /api/v1/projects/{project_id}/confirm-episodes # 确认分集规划
POST   /api/v1/projects/{project_id}/confirm-assets   # 确认资产，完成初始化
```

### 5.2 Episodes

```
GET    /api/v1/projects/{project_id}/episodes                      # 分集列表
GET    /api/v1/projects/{project_id}/episodes/{episode_id}         # 分集详情
PATCH  /api/v1/projects/{project_id}/episodes/{episode_id}         # 更新分集信息

POST   /api/v1/projects/{project_id}/episodes/{episode_id}/generate-storyboard  # 生成分镜脚本
PATCH  /api/v1/projects/{project_id}/episodes/{episode_id}/step    # 推进/回退当前步骤
```

### 5.3 Shots（分镜）

```
GET    /api/v1/episodes/{episode_id}/shots                         # 分镜列表
GET    /api/v1/episodes/{episode_id}/shots/{shot_id}               # 分镜详情
PATCH  /api/v1/episodes/{episode_id}/shots/{shot_id}               # 更新分镜

POST   /api/v1/episodes/{episode_id}/shots/{shot_id}/generate-image  # 生成剧照
POST   /api/v1/episodes/{episode_id}/shots/{shot_id}/generate-video  # 生成视频
POST   /api/v1/episodes/{episode_id}/shots/{shot_id}/generate-audio  # 生成配音

POST   /api/v1/episodes/{episode_id}/shots/{shot_id}/review        # 审核（通过/拒绝）
  body: {"action": "approve" | "reject", "comment": "..."}

POST   /api/v1/episodes/{episode_id}/shots/batch-generate-images   # 批量生成剧照
POST   /api/v1/episodes/{episode_id}/shots/batch-generate-videos   # 批量生成视频

POST   /api/v1/episodes/{episode_id}/merge                         # 触发合并成片
GET    /api/v1/episodes/{episode_id}/merge-status                  # 合并进度
```

### 5.4 Assets（资产）

```
GET    /api/v1/projects/{project_id}/assets                        # 资产列表（支持 ?type=character|scene|prop）
GET    /api/v1/projects/{project_id}/assets/{asset_id}             # 资产详情
PATCH  /api/v1/projects/{project_id}/assets/{asset_id}             # 更新资产

POST   /api/v1/projects/{project_id}/assets/{asset_id}/regenerate  # 触发重新生成
POST   /api/v1/projects/{project_id}/assets/{asset_id}/confirm     # 确认资产
  body: {"status": "approved" | "need_regen"}
```

### 5.5 Conversations（多轮会话）

```
GET    /api/v1/conversations/{target_type}/{target_id}             # 获取制品的会话列表
POST   /api/v1/conversations/{target_type}/{target_id}             # 新建会话

GET    /api/v1/conversations/{conversation_id}                     # 会话详情（含消息列表）
POST   /api/v1/conversations/{conversation_id}/messages            # 发送消息（SSE 流式返回）
DELETE /api/v1/conversations/{conversation_id}                     # 删除会话
```

### 5.6 Tasks（任务状态）

```
GET    /api/v1/tasks/{task_id}                                     # 查询任务状态
DELETE /api/v1/tasks/{task_id}                                     # 取消任务

GET    /api/v1/tasks/stream/{task_id}                              # SSE 实时推送任务进度
  # SSE 事件：{"progress": 60, "status": "running", "message": "正在渲染第3帧..."}
```

### 5.7 Prompt Configs（提示词管理 — Admin）

```
GET    /api/v1/admin/prompt-configs                                # 所有提示词配置列表
GET    /api/v1/admin/prompt-configs/{scope}                        # 指定 scope 的配置
PUT    /api/v1/admin/prompt-configs/{scope}                        # 更新提示词
  body: {"system_prompt": "...", "user_prompt_template": "...", "description": "..."}

GET    /api/v1/admin/prompt-configs/{scope}/history                # 历史版本列表
POST   /api/v1/admin/prompt-configs/{scope}/rollback/{version}     # 回滚到指定版本
```

---

## 6. Celery 任务调度设计

### 6.1 任务队列划分

```python
# celery_app.py
app = Celery("ai_short_film")
app.conf.task_routes = {
    "tasks.llm.*":        {"queue": "llm"},       # LLM 调用，并发适中
    "tasks.image.*":      {"queue": "image"},     # 图像生成，GPU 限流
    "tasks.video.*":      {"queue": "video"},     # 视频生成，最慢，独立队列
    "tasks.audio.*":      {"queue": "audio"},     # 配音，较快
    "tasks.merge.*":      {"queue": "merge"},     # 视频合并
}
# 启动命令示例（每个 worker 类型单独伸缩）：
# celery -A app.celery_app worker -Q llm -c 8
# celery -A app.celery_app worker -Q image -c 4
# celery -A app.celery_app worker -Q video -c 2
```

### 6.2 核心任务定义

```python
# tasks/llm.py

@celery_app.task(bind=True, name="tasks.llm.parse_script", max_retries=3)
def parse_script(self, project_id: str, script_text: str, config: dict) -> dict:
    """
    解析剧本，返回：
    - series_prompt: 剧集总览
    - episodes: 分集草案列表
    - assets: 资产需求列表
    - continuity_items: 连续性约束列表
    """
    ...

@celery_app.task(bind=True, name="tasks.llm.generate_shot_scripts")
def generate_shot_scripts(self, episode_id: str) -> dict:
    """为整集生成所有分镜脚本"""
    ...

@celery_app.task(bind=True, name="tasks.llm.edit_artifact_via_chat")
def edit_artifact_via_chat(self, conversation_id: str, message: str) -> dict:
    """处理多轮会话中的制品修改请求"""
    ...
```

```python
# tasks/image.py

@celery_app.task(bind=True, name="tasks.image.generate_shot_image", max_retries=2)
def generate_shot_image(self, shot_id: str, prompt_override: str | None = None) -> dict:
    """
    调用 Seedream 生成分镜剧照：
    1. 从 DB 读取 Shot + 关联 Assets 的 prompt
    2. 调用 PromptService 构建完整提示词
    3. 调用 Seedream API
    4. 上传结果到 OSS
    5. 更新 Shot.image_url + state
    """
    ...

@celery_app.task(bind=True, name="tasks.image.regenerate_asset", max_retries=2)
def regenerate_asset(self, asset_id: str, prompt_override: str | None = None) -> dict:
    """重新生成资产图片"""
    ...
```

```python
# tasks/video.py

@celery_app.task(bind=True, name="tasks.video.generate_shot_video", max_retries=1)
def generate_shot_video(self, shot_id: str) -> dict:
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
# tasks/merge.py

@celery_app.task(bind=True, name="tasks.merge.merge_episode", max_retries=1)
def merge_episode(self, episode_id: str) -> dict:
    """
    合并整集视频：
    1. 按 Shot.order 排序，收集所有 approved shot 的 video_url + audio_url
    2. 下载到本地临时目录
    3. 调用 ffmpeg 拼接（带进度回调更新 TaskRecord.progress）
    4. 上传成片到 OSS
    5. 更新 Episode.final_video_url + status = "completed"
    """
    ...
```

### 6.3 任务进度推送机制

```
任务执行中 → 定期更新 TaskRecord.progress → 前端轮询 GET /tasks/{task_id}
         OR
任务执行中 → 写入 Redis channel → 前端 SSE GET /tasks/stream/{task_id}（推荐）
```

```python
# 任务中更新进度示例
def update_progress(self, task_id: str, progress: int, message: str):
    # 更新 MongoDB TaskRecord
    # 发布到 Redis pub/sub channel: f"task_progress:{task_id}"
    redis_client.publish(f"task_progress:{task_id}", json.dumps({
        "progress": progress,
        "message": message,
        "status": "running",
    }))
```

### 6.4 批量任务策略

```python
# 批量生成剧照
@celery_app.task(name="tasks.image.batch_generate_shot_images")
def batch_generate_shot_images(self, episode_id: str, shot_ids: list[str] | None = None):
    """
    使用 Celery group + chord：
    - 并行触发所有 shot 的 generate_shot_image 任务
    - 全部完成后触发 on_batch_complete 回调更新 Episode.current_step
    """
    from celery import group, chord
    shots = shot_ids or get_all_shot_ids(episode_id)
    job = chord(
        group(generate_shot_image.s(shot_id) for shot_id in shots),
        on_image_batch_complete.s(episode_id=episode_id),
    )
    return job.delay()
```

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
│   │   ├── llm.py                 # LLM 调用任务
│   │   ├── image.py               # 图像生成任务
│   │   ├── video.py               # 视频生成任务
│   │   ├── audio.py               # 配音任务
│   │   └── merge.py               # 视频合并任务
│   │
│   ├── integrations/              # 外部 API 封装
│   │   ├── openai_client.py       # LLM 调用（OpenAI/Claude）
│   │   ├── seedream_client.py     # Seedream 图像生成
│   │   ├── seedance_client.py     # Seedance 视频生成
│   │   └── tts_client.py          # 配音 TTS
│   │
│   └── utils/
│       ├── sse.py                 # SSE 响应生成器
│       ├── ffmpeg.py              # 视频合并工具
│       └── seed_data.py           # 数据库种子数据（初始提示词）
│
├── tests/
│   ├── test_api/
│   └── test_tasks/
│
├── scripts/
│   └── seed_prompts.py            # 初始化默认提示词配置
│
├── docker-compose.yml             # MongoDB + Redis + Worker
├── pyproject.toml
└── .env.example
```

---

## 8. 实现分阶段计划

### Phase 1：基础骨架（最先完成，解锁前端联调）

**目标**：跑通数据 CRUD，前端能从真实 API 读写数据。

- [ ] 搭建 FastAPI + Beanie 骨架，连接 MongoDB
- [ ] 实现所有数据模型（`models/`）
- [ ] 实现 Project / Episode / Shot / Asset 的基础 CRUD API
- [ ] 实现文件上传接口（OSS/本地开发用 MinIO）
- [ ] `seed_prompts.py`：写入初始默认提示词
- [ ] Admin 提示词 CRUD API（`/admin/prompt-configs`）
- [ ] Docker Compose 开发环境（MongoDB + Redis + MinIO）

### Phase 2：Celery 异步任务 + 任务状态

**目标**：生成类操作全部异步化，前端能轮询进度。

- [ ] 搭建 Celery + Redis，定义队列
- [ ] `TaskRecord` CRUD + 任务状态 API
- [ ] 实现 `tasks/llm.py`：`parse_script`、`generate_shot_scripts`
- [ ] 实现 `tasks/image.py`：`generate_shot_image`（对接 Seedream）
- [ ] 实现 `tasks/video.py`：`generate_shot_video`（对接 Seedance）
- [ ] 实现批量任务（`batch_generate_shot_images`）
- [ ] SSE 任务进度推送（Redis pub/sub → `/tasks/stream/{task_id}`）

### Phase 3：多轮会话机制

**目标**：每个制品下的对话框能真实工作。

- [ ] `Conversation` 模型 + CRUD
- [ ] `ConversationService`：上下文构建（历史消息 + 制品快照 + 提示词渲染）
- [ ] `POST /conversations/{target_type}/{target_id}/messages` — SSE 流式返回
- [ ] 会话触发生成任务（用户说"重新生成"→发 Celery task→返回 task_id）
- [ ] 提示词配置快照写入 Conversation
- [ ] 前端会话侧边栏对接

### Phase 4：审核流程 + 合并成片

**目标**：完整走通单集从脚本到成片的全流程。

- [ ] 图像审核 API（通过/拒绝/批量审核）
- [ ] 视频审核 API
- [ ] Shot 状态机（`planned → asset_ready → rendered → approved`）
- [ ] 缺失资产检查（视频生成前自动触发）
- [ ] `tasks/audio.py`：配音生成（TTS）
- [ ] `tasks/merge.py`：ffmpeg 合并成片 + 进度回调
- [ ] Episode 状态自动推进（当所有 Shot approved 后）

### Phase 5：生产加固

**目标**：稳定性、可观测性、安全性。

- [ ] 接口鉴权（JWT 或 API Key）
- [ ] Celery 重试策略 + 死信队列
- [ ] 任务幂等性（同一 Shot 不重复生成）
- [ ] 日志 + Sentry 错误追踪
- [ ] Prometheus metrics（任务成功率/耗时）
- [ ] 提示词配置变更审计日志
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
- 使用 `instructor` 库（基于 Pydantic）强制 LLM 输出符合 Schema 的 JSON
- 失败时自动重试（最多 3 次）
- 每个 scope 的 prompt 中包含严格的输出格式说明 + few-shot 示例

### 难点 3：视频生成的长耗时 + 超时

**问题**：Seedance 视频生成可能耗时 60-300 秒，HTTP 请求会超时。

**方案**：
- 全部改为异步：API 只返回 `task_id`，前端轮询或 SSE 监听
- Celery task 设置 `time_limit=600`（10 分钟硬超时）
- 提供"取消任务"接口

### 难点 4：连续性约束的传递

**问题**：上一集的结尾状态（服装/伤势/站位等）需要自动传递到下一集的分镜生成中。

**方案**：
- `Episode.continuity_notes` 字段由 LLM 自动从上一集 shots 中提取（`continuity_extract` 任务）
- 生成分镜脚本时将 `continuity_notes` 注入 prompt
- 允许人工编辑（通过对话或直接 PATCH）

### 难点 5：提示词版本管理与回滚

**问题**：修改了某个 scope 的提示词后，发现效果变差，需要快速回滚。

**方案**：
- 每次 `PUT /admin/prompt-configs/{scope}` 不覆盖旧数据，而是创建新版本（version+1），旧版本 `is_active=False`
- `POST /admin/prompt-configs/{scope}/rollback/{version}` 将指定版本重新激活
- Conversation 中的 `prompt_config_snapshot` 记录了生成时使用的版本，便于对比效果

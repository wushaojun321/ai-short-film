# AI 短剧生产系统

> 一个由 AI 驱动的短剧生产流水线——从输入总剧本开始，自动完成分集、资产生成、分镜规划、逐镜视频合成，直到最终剪辑输出。

**[English Documentation](README.md)**

---

## 项目简介

系统接收原始剧本，通过 LLM 编排层驱动完整的生产流程，底层对接真实图像和视频生成 API：

```
总剧本
  → 分集拆分
  → 人物 & 场景资产生成（人工审核关卡）
  → 逐镜分镜脚本
  → 分镜图生成
  → 视频逐镜合成（链式传递首尾帧保持连续性）
  → 整集合片
```

核心设计原则：
- **一致性优先** — 通过面部锁定（face-lock）和造型锁定（look-lock）机制，确保角色、场景、道具在跨镜头间保持视觉一致性。
- **人工介入节点** — 资产图和分镜脚本都有人工审核环节，审核通过后才进入视频生成阶段。
- **全异步架构** — LLM、图像、视频、合片任务分别运行在独立的 Celery 队列，前端通过轮询感知状态变化。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + React Router 6 |
| UI 组件 | Radix UI + shadcn/ui 风格 |
| 后端 | Python 3.12 + FastAPI + Beanie（MongoDB ODM）|
| 任务队列 | Celery + Redis（独立队列：`llm`、`image`、`video`、`merge`）|
| 数据库 | MongoDB 7 |
| 对象存储 | 腾讯云 COS（前端使用 STS 临时密钥直传）|
| 大语言模型 | OpenRouter（模型可配置，默认 GPT-4o）|
| 图像生成 | 火山引擎 Seedream |
| 视频生成 | 火山引擎 Seedance（通过 `last_frame_url` 链式保持镜头连续性）|
| 认证 | JWT Bearer Token |
| 代理 | V2Ray（LLM 流量走代理，图像/视频调用直连）|

---

## 目录结构

```
.
├── backend/
│   ├── app/
│   │   ├── agent/          # LLM Agent 运行器与提示词 Agent
│   │   ├── models/         # Beanie 文档模型
│   │   ├── parsing/        # 剧本解析流水线各模块
│   │   ├── routers/        # FastAPI 路由
│   │   ├── services/       # 存储、认证、任务服务
│   │   └── tasks/          # Celery 任务定义
│   ├── .env.example        # 环境变量模板
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # 公共 UI 组件
│   │   ├── lib/            # API 客户端、认证、COS 上下文
│   │   └── pages/          # 路由级页面组件
│   └── Dockerfile
├── docs/
│   ├── workflow-spec.md    # 生产流程规范
│   ├── parse-workflow-spec.md
│   └── backend-plan.md
├── v2ray/
│   └── config.json.example # 代理配置模板（复制为 config.json 后填写）
└── docker-compose.yml
```

---

## 快速开始

### 前置条件

- Docker & Docker Compose
- [腾讯云 COS](https://cloud.tencent.com/product/cos) 存储桶
- [OpenRouter](https://openrouter.ai) API Key
- [火山引擎方舟](https://www.volcengine.com/product/ark) API Key（用于 Seedream 图像模型和 Seedance 视频模型）
- *(可选)* 如果服务器无法直连 OpenRouter，需要一个 V2Ray 代理节点

### 1. 克隆并配置

```bash
git clone https://github.com/wushaojun321/ai-short-film.git
cd ai-short-film
```

复制并填写后端环境变量：

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入真实的 Key 和配置
```

如果需要代理，配置 V2Ray：

```bash
cp v2ray/config.json.example v2ray/config.json
# 编辑 v2ray/config.json，填入代理服务器地址和 UUID
# 如果不需要代理，可以从 docker-compose.yml 中删除 v2ray service，
# 并移除 api / worker 服务中的 HTTP_PROXY / HTTPS_PROXY 环境变量
```

### 2. 启动所有服务

```bash
docker compose up -d
```

将启动：`frontend`、`api`、`worker-llm`、`worker-image`、`worker-video`、`worker-merge`、`mongodb`、`redis`，以及可选的 `v2ray`。

### 3. 打开应用

访问 `http://localhost`（80 端口）。

注册账号后，新建项目，粘贴剧本文本即可开始生产流程。

---

## 环境变量说明

完整列表参见 `backend/.env.example`，主要变量如下：

| 变量名 | 说明 |
|--------|------|
| `MONGODB_URL` | MongoDB 连接字符串 |
| `REDIS_URL` | Redis 连接字符串 |
| `COS_SECRET_ID` / `COS_SECRET_KEY` | 腾讯云 COS 密钥 |
| `COS_REGION` / `COS_BUCKET` | COS 地域和存储桶名 |
| `OPENROUTER_API_KEY` | OpenRouter API Key |
| `OPENROUTER_MODEL` | LLM 模型名（如 `openai/gpt-4o`）|
| `ARK_API_KEY` | 火山引擎方舟 API Key |
| `ARK_IMAGE_MODEL` | 图像模型 ID（Seedream）|
| `ARK_VIDEO_MODEL` | 视频模型 ID（Seedance）|

---

## 生产流水线详解

### 剧本解析
剧本经过多阶段解析器处理：
1. `ScriptIndexer` — 将原文索引为块范围
2. `ProductionBlueprintPlanner` — 调用 LLM 生成结构化分集/资产/场景蓝图
3. `EpisodeMaterialBuilder` — 根据块范围回填原文（不做 LLM 摘要，保留台词原文）
4. `AssetRegistryBuilder` — 从蓝图派生人物和场景资产记录

### 资产生成
- 每个角色生成三张标准视图：面部、全身、侧面
- `face_identity` 锁定同一角色的面部基准，跨镜头保持一致
- `look_lock` 在同一故事阶段内锁定发型、服装、配饰
- 所有资产图生成后需经过人工审核才能进入分镜阶段

### 分镜视频生成
- 同一片段内的镜头按顺序串行生成
- 每个镜头可引用上一镜的 `last_frame_url` 作为起始帧，保持视觉连续性
- 不同片段链在多个 `worker-video` 实例上并发执行

---

## License

MIT

# AI 短剧生产系统

## 项目概览

AI 辅助短剧（竖屏 9:16）从剧本到成片的生产系统。当前前端为 **纯 Mock 数据**，用于流程演示。

## 技术栈

- **前端**：React 18 + TypeScript + Vite + Tailwind CSS + React Router 6
- **UI 组件**：自写组件 + shadcn/ui 风格（基于 Radix UI）
- **Mock 数据**：`frontend/src/lib/data.ts`
- **核心文档**：`docs/workflow-spec.md`（完整工作流规范）
- **后端规划**：`docs/backend-plan.md`（Python/FastAPI/Beanie/Celery 后端实现计划）
- **火山 API 文档**：`docs/volcano/`（Seedream 文生图 + Seedance 视频生成 API 参考）

## 目录结构

```
ai-short-film/
├── frontend/src/
│   ├── App.tsx                              # 路由入口（3条路由）
│   ├── lib/
│   │   ├── data.ts                          # 所有 Mock 数据和类型定义
│   │   └── utils.ts                         # cn() 工具函数
│   ├── components/
│   │   ├── ui/                              # shadcn 风格 UI 组件库
│   │   │   ├── button.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── input.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── tabs.tsx
│   │   │   └── textarea.tsx
│   │   ├── Nav.tsx                          # 顶部导航（项目下拉切换）
│   │   ├── Shell.tsx                        # 页面壳（只包含 Nav）
│   │   ├── EpisodeSidebar.tsx               # 左侧分集列表（已初始化项目）
│   │   ├── EpisodeStepBar.tsx               # 顶部分集制作步骤条（8步）
│   │   ├── StepContent.tsx                  # 各步骤制品展示区
│   │   └── screens/
│   │       ├── NewProjectScreen.tsx         # 三阶段初始化流程
│   │       └── ProjectStudioScreen.tsx      # 分集制作台主页面
│   └── pages/
│       ├── ProjectsHome.tsx                 # 首页（项目列表）
│       ├── NewProjectPage.tsx               # 路由包装
│       └── ProjectDetailPage.tsx            # 路由包装（判断初始化状态）
├── docs/
│   ├── workflow-spec.md                     # 完整工作流规范（分镜/资产/连续性策略）
│   ├── backend-plan.md                      # 后端实现计划（Python+Mongo+Beanie+Celery）
│   └── volcano/                             # 火山引擎 API 参考文档
│       ├── 01_create-video.md               # Seedance 创建视频生成任务 API
│       ├── 02_query-video.md                # Seedance 查询单个视频任务 API
│       ├── 03_query-video-list.md           # Seedance 批量查询视频任务列表 API
│       ├── 04_seedance_tutorial.md          # Seedance 完整使用教程（参考图/首尾帧/多模态）
│       └── 05_t2i.md                        # Seedream 文生图 API（图像生成）
```

## 路由结构

```
/                           → /projects (重定向)
/projects                   → 首页（项目列表 + 新建按钮）
/projects/new               → 新建项目（三阶段初始化流程）
/projects/:projectId        → 项目详情
  initStatus !== "initialized" → NewProjectScreen（补充初始化）
  initStatus === "initialized" → ProjectStudioScreen（分集制作台）
    URL 参数：?episode=EP04&step=video_review
```

## 初始化流程（三阶段）

```
阶段 1：导入剧本
  → 上传文件 → 点击「解析剧本」→ 弹窗配置（集数/时长/连续性约束）→ AI 解析

阶段 2：分集规划审核
  → AI 生成分集列表（集数/标题/字数/预估时长）→ 用户可 inline 编辑 → 确认

阶段 3：资产审核
  → AI 生成角色/场景/道具资产图 → 用户可单独重生 → 确认初始化
```

## 单集制作 Step 流程（8步）

```
1. 生成分镜脚本  → 分镜列表（含连续性约束、资产绑定）
2. 生成分镜剧照  → 网格展示，可单独/批量生成
3. 剧照审核      → 逐镜通过/拒绝
4. 生成分镜视频  → 批量生成，状态列表
5. 视频审核      → 左列表+右预览，逐镜通过/拒绝
6. 配音          → 按角色音色设定生成
7. 合并成片      → 进度条合并
8. 完成          → 成片预览/下载
```

## 关键数据类型

```typescript
ProjectInitStatus = "not_started" | "script_uploaded" | "episodes_confirmed" | "assets_confirmed" | "initialized"
EpisodeStatus = "not_started" | "in_progress" | "completed"
EpisodeStep = "storyboard_script" | "storyboard_images" | "image_review" | "storyboard_videos" | "video_review" | "dubbing" | "merge" | "done"
ShotState = "planned" | "asset_required" | "asset_ready" | "rendered" | "review_failed" | "approved"
AssetStatus = "已生成" | "待确认" | "需重生" | "缺失"
```

## 主题

白色风格（#FFFFFF 背景），品牌绿 #0F8A52 保留。
颜色 token 在 `tailwind.config.js` 中定义，可直接使用 `bg-bg`、`text-sub`、`border-line` 等。

## 部署

服务器通过 `ssh film` 访问，使用 Docker Compose 部署，代码在 `/root/ai-short-film`。

```bash
# 标准部署流程（代码已推到 gitee 后执行）
ssh film "cd /root/ai-short-film && git pull && docker compose build api worker-llm worker-image worker-video worker-merge && docker compose up -d"

# 仅重启不重新 build
ssh film "cd /root/ai-short-film && docker compose restart api worker-llm worker-image worker-video worker-merge"

# 查看日志
ssh film "cd /root/ai-short-film && docker compose logs -f api"
ssh film "cd /root/ai-short-film && docker compose logs -f worker-llm"

# 查看服务状态
ssh film "cd /root/ai-short-film && docker compose ps"
```

**服务清单：**
- `api` — FastAPI 主进程，端口 8000
- `worker-llm` — Celery LLM 队列，并发 2
- `worker-image` — Celery 图像队列，并发 4
- `worker-video` — Celery 视频队列，并发 2
- `worker-merge` — Celery 合并队列，并发 1
- `mongodb` — MongoDB 7，宿主机端口 27018
- `redis` — Redis 7，宿主机端口 6380
- `v2ray` — 代理（供 LLM/API 外网访问）

**环境变量**：`backend/.env`（不入 git）

## 核心设计原则（来自 workflow-spec.md）

1. 初始化阶段一次性完成：全剧资产图片在初始化时生成，保障后续角色一致性
2. 分镜生成时带入资产清单，AI 自动绑定 required_assets
3. 连续性约束由上一集结尾状态自动触发生成，用户可修改
4. 每集独立推进，支持并发制作
5. 资产在全剧共享（asset_bible），不是每集独立

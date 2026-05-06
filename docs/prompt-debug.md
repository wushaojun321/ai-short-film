# 提示词调试指南

> 服务器连接方式、部署命令见 [CODEBUDDY.md 部署章节](../CODEBUDDY.md#部署)。
> 本文档中所有命令均在**服务器上**执行（先 `ssh root@42.193.144.175` 登录，再 `cd /root/ai-short-film`）。

## 工作流概述

系统中有三类提示词需要调试：

1. **剧本解析提示词（LLM / OpenRouter）** — 用于上传剧本后的分集和资产解析
2. **图像提示词（Seedream）** — 用于生成资产图片和分镜剧照
3. **视频提示词（Seedance）** — 用于生成分镜视频

当前要求保留中文写实电影风格，不再统一把提示词翻译成英文。部分环节会先由 LLM 优化/结构化最终提交提示词，资产图片提示词则主要由确定性 builder 生成。
调试流程：在界面触发生成 → 从日志或制品详情拿到实际提交提示词 → 根据效果反馈给 AI 调整。

---

## 第一步：触发生成

在前端界面手动触发需要调试的环节：

| 环节 | 操作路径 |
|------|----------|
| 剧本解析 | 项目初始化阶段 → 上传剧本 → 点击「解析剧本」 |
| 资产图片 | 项目初始化阶段 → 资产审核 → 点击单个资产的「重新生成」 |
| 分镜剧照 | 兼容接口保留，当前主流程不展示为必经步骤 |
| 分镜视频 | 单集制作 → Step 2「分镜视频」→ 单镜「生成视频」或顶部「生成所有镜头」 |

---

## 第二步：从日志中拿到提示词

登录服务器后，在 `/root/ai-short-film` 目录下执行：

```bash
# 实时查看 LLM worker 日志（剧本解析 + 分镜脚本）
docker compose logs -f worker-llm

# 实时查看图片 worker 日志（资产图片 + 分镜剧照）
docker compose logs -f worker-image

# 实时查看视频 worker 日志（分镜视频）
docker compose logs -f worker-video
```

### 日志格式

触发生成后，日志中会出现以下格式的输出：

**剧本解析（OpenRouter LLM）：**
```
[init] 项目加载完成：xxx
[init] 剧本长度：xxxx 字，目标最低集数：x
[index] 原文索引完成：xxx 个块
[blueprint] 综合规划完成
[prompt] Prompt 渲染完成，发送 LLM 请求…
[error] Unterminated string starting at: line ...   # LLM 返回的 JSON 非法或被截断
```

如果使用低风险 demo 剧本仍出现 `Unterminated string...` 或 `LLM JSON response was truncated...`，优先判断为 LLM 输出结构异常、max_tokens/输出结构不合适，或运行中的 `worker-llm` 仍是旧镜像，不要继续只改剧本文本。

**资产图片（Seedream）：**
```
[ASSET IMAGE PROMPT] asset_id=xxx asset=角色名 attempt=1/3
--- PROMPT START ---
<实际发给 Seedream 的提示词>
--- PROMPT END ---
[IMAGE PROMPT] model=xxx size=2048x2048 watermark=False
--- PROMPT START ---
<最终发给 API 的提示词>
--- PROMPT END ---
```

**分镜剧照（Seedream）：**
```
[SHOT IMAGE PROMPT] shot_id=xxx shot=EP01-S03 attempt=1/3
--- PROMPT START ---
<实际发给 Seedream 的提示词>
--- PROMPT END ---
```

**分镜视频（Seedance）：**
```
[SHOT VIDEO PROMPT] shot_id=xxx shot=EP01-S03 attempt=1/3 ref_images=2
--- PROMPT START ---
<实际发给 Seedance 的提示词>
--- PROMPT END ---
[VIDEO PROMPT] model=xxx ratio=9:16 duration=5s resolution=720p has_images=True
--- PROMPT START ---
<最终发给 API 的提示词>
--- PROMPT END ---
```

### 过滤日志（只看提示词）

```bash
# 只看资产/分镜图片提示词
docker compose logs worker-image 2>&1 | grep -A 5 'PROMPT START'

# 只看视频提示词
docker compose logs worker-video 2>&1 | grep -A 5 'PROMPT START'

# 跟踪批量视频片段链
docker compose logs -f worker-video 2>&1 | grep -E 'video-chain|SHOT VIDEO PROMPT|last_frame'

# 最近 200 行日志（排查最新一次生成）
docker compose logs --tail=200 worker-image

# 查看剧本解析 worker 最近日志
docker compose logs --tail=200 worker-llm
```

---

## 第三步：反馈给 AI 调整提示词

### 调整 LLM 生成提示词的系统 prompt

LLM 提示词模板当前存在代码文件 `backend/app/prompts/llm_prompts.py` 中，运行时由 `backend/app/services/prompt_service.py` 直接读取 `DEFAULT_PROMPTS`。

项目中仍保留 `PromptConfig` 数据库模型和 `/admin/prompt-configs` 查看接口，但当前生成链路不从 MongoDB 读取提示词；修改数据库里的 `prompt_configs` 不会影响实际生成。要调整提示词，需要修改代码、重新 build 并重启对应 worker。

把从日志拿到的提示词和生成效果描述给 AI，例如：

> 这是当前分镜剧照的提示词：
> `cinematic vertical shot, office scene, ...`
> 效果问题：画面太暗，人物表情模糊，背景太乱
> 请帮我调整 `shot_image_gen` 的 system prompt，让生成的提示词更强调明亮光线、清晰人脸

### 提示词配置的位置

| 配置项 | 作用 |
|--------|------|
| `asset_prompt_gen` | 资产图片的 LLM 优化 prompt 模板 |
| `shot_image_gen` | 分镜剧照的 LLM 优化 prompt 模板 |
| `shot_video_gen` | 分镜视频的 LLM 优化 prompt 模板 |
| `shot_script_gen` | 分镜脚本生成模板 |
| `script_parse` | 剧本解析模板 |
| `script_map` | 历史兼容模板；当前默认解析链路不再使用 Map-Reduce 压缩正文 |

查看当前所有代码侧配置（需先登录获取 token）：

```bash
# 1. 登录拿 token
TOKEN=$(curl -s -X POST https://你的域名/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xxx","password":"xxx"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. 查看所有 prompt 配置
curl -s -H "Authorization: Bearer $TOKEN" \
  https://你的域名/api/v1/admin/prompt-configs | python3 -m json.tool
```

---

## 典型调试场景

### 场景 1：图片风格不对（太卡通 / 不够写实）

1. 触发一次资产或分镜图片生成
2. 从 `worker-image` 日志拿到 `PROMPT START` 到 `PROMPT END` 之间的内容
3. 告知 AI：「当前提示词是 `xxx`，生成效果太卡通，请修改 `shot_image_gen` 的 system prompt，强调电影级写实风格、摄影棚打光」

### 场景 2：视频运动幅度太大 / 太小

1. 触发一次视频生成
2. 从 `worker-video` 日志拿到视频提示词
3. 告知 AI：「当前提示词是 `xxx`，视频抖动太厉害，请修改 `shot_video_gen` 的 system prompt，让生成的 prompt 更强调 steady camera、slow movement」

### 场景 3：人物不一致

1. 对比不同镜头的提示词
2. 告知 AI：「角色A在镜头1的提示词是 `xxx`，在镜头2是 `yyy`，两者描述不一致，请修改 `shot_image_gen` 以更好地沿用资产描述」

### 场景 4：批量视频生成连贯性差

1. 点击顶部「生成所有镜头」
2. 在 `worker-video` 中查看 `[video-chain]` 日志，确认是否按片段链顺序生成
3. 检查后一镜的 `SHOT VIDEO PROMPT` 是否包含上一镜尾帧辅助说明，以及当前镜头的角色/场景资产引用
4. 如果后一镜没有可用尾帧，检查上一镜是否生成了 `last_frame_url`

```bash
docker compose logs --tail=300 worker-video | grep -E 'video-chain|SHOT VIDEO PROMPT|last_frame'

docker compose exec mongodb mongosh ai_short_film --quiet
db.shots.find(
  {episode_id:ObjectId("替换为 episode_id")},
  {shot_code:1,segment_code:1,state:1,last_frame_url:1,generation_task_id:1}
).sort({order:1})
```

---

## 快速命令备忘

在服务器 `/root/ai-short-film` 目录下执行：

```bash
# 实时跟踪图片生成提示词
docker compose logs -f worker-image 2>&1 | grep -E 'PROMPT|--- PROMPT'

# 实时跟踪视频生成提示词
docker compose logs -f worker-video 2>&1 | grep -E 'PROMPT|--- PROMPT'

# 实时跟踪片段链批量生成
docker compose logs -f worker-video 2>&1 | grep -E 'video-chain|SHOT VIDEO PROMPT|last_frame'

# 查看所有 worker 日志
docker compose logs -f worker-image worker-video worker-llm

# 确认 worker-llm 容器内是否是最新代码
docker compose exec worker-llm grep -n "ParseOrchestrator\|ScriptProductionPlanAgent\|max_tokens" /app/app/parsing/*.py /app/app/tasks/llm_tasks.py
```

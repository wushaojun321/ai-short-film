# 提示词调试指南

## 工作流概述

系统中有两类提示词需要调试：

1. **图像提示词（Seedream）** — 用于生成资产图片和分镜剧照
2. **视频提示词（Seedance）** — 用于生成分镜视频

每次生成时，系统会先用 LLM 将剧本描述优化为英文提示词，再发给对应 API。
调试流程：在界面触发生成 → 从日志拿到实际发送的提示词 → 根据效果反馈给 AI 调整。

---

## 第一步：触发生成

在前端界面手动触发需要调试的环节：

| 环节 | 操作路径 |
|------|----------|
| 资产图片 | 项目初始化阶段 → 资产审核 → 点击单个资产的「重新生成」 |
| 分镜剧照 | 单集制作 → Step 2「生成分镜剧照」→ 点击单镜「生成」或「批量生成」 |
| 分镜视频 | 单集制作 → Step 4「生成分镜视频」→ 点击单镜「生成」或「批量生成」 |

---

## 第二步：从日志中拿到提示词

### 连接服务器，实时查看 worker 日志

```bash
# 查看图片 worker 日志（资产图片 + 分镜剧照）
ssh root@42.193.144.175 "cd /root/ai-short-film && docker compose logs -f worker-image"

# 查看视频 worker 日志（分镜视频）
ssh root@42.193.144.175 "cd /root/ai-short-film && docker compose logs -f worker-video"
```

### 日志格式

触发生成后，日志中会出现以下格式的输出：

**资产图片（Seedream）：**
```
[ASSET IMAGE PROMPT] asset_id=xxx asset=角色名 attempt=1/3
--- PROMPT START ---
<实际发给 Seedream 的英文提示词>
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
<实际发给 Seedream 的英文提示词>
--- PROMPT END ---
```

**分镜视频（Seedance）：**
```
[SHOT VIDEO PROMPT] shot_id=xxx shot=EP01-S03 attempt=1/3 first_frame=True ref_images=2
--- PROMPT START ---
<实际发给 Seedance 的英文提示词>
--- PROMPT END ---
[VIDEO PROMPT] model=xxx ratio=9:16 duration=5s resolution=720p has_images=True
--- PROMPT START ---
<最终发给 API 的提示词>
--- PROMPT END ---
```

### 过滤日志（只看提示词）

```bash
# 只看资产图片提示词
ssh root@42.193.144.175 "cd /root/ai-short-film && docker compose logs worker-image 2>&1 | grep -A 5 'PROMPT START'"

# 只看视频提示词
ssh root@42.193.144.175 "cd /root/ai-short-film && docker compose logs worker-video 2>&1 | grep -A 5 'PROMPT START'"

# 最近 200 行日志（排查最新一次生成）
ssh root@42.193.144.175 "cd /root/ai-short-film && docker compose logs --tail=200 worker-image"
```

---

## 第三步：反馈给 AI 调整提示词

### 调整 LLM 生成提示词的系统 prompt

LLM 提示词模板存在数据库的 `prompt_configs` 集合中，可通过管理 API 修改，也可以直接告知 AI。

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

查看当前所有配置（需先登录获取 token）：

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

---

## 快速命令备忘

```bash
# 实时跟踪图片生成提示词
ssh root@42.193.144.175 "cd /root/ai-short-film && docker compose logs -f worker-image 2>&1 | grep -E 'PROMPT|--- PROMPT'"

# 实时跟踪视频生成提示词
ssh root@42.193.144.175 "cd /root/ai-short-film && docker compose logs -f worker-video 2>&1 | grep -E 'PROMPT|--- PROMPT'"

# 查看所有 worker 日志
ssh root@42.193.144.175 "cd /root/ai-short-film && docker compose logs -f worker-image worker-video worker-llm"
```

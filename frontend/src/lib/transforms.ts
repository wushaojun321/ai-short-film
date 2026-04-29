import type { ApiProject, ApiEpisode, ApiShot, ApiAsset } from "./api";
import type { Project, EpisodeDetail, Shot, ShotState, EpisodeStep, Asset, AssetStatus } from "./data";

// ─── Project ──────────────────────────────────────────────────

export function transformProject(p: ApiProject): Project {
  return {
    id: p.id,
    title: p.title,
    genre: p.genre,
    format: p.format === "VERTICAL_9_16" ? "VERTICAL 9:16" : p.format,
    episodes: p.target_episode_count,
    renderedEpisodes: 0,
    stage: initStatusToStage(p.init_status),
    progress: p.progress,
    initStatus: p.init_status as Project["initStatus"],
    blockers: 0,
    note: undefined,
  };
}

function initStatusToStage(status: string): string {
  const map: Record<string, string> = {
    not_started:        "未初始化",
    script_uploaded:    "待解析",
    episodes_confirmed: "资产生成",
    assets_confirmed:   "资产审核",
    initialized:        "分集制作",
  };
  return map[status] ?? status;
}

// ─── Episode ──────────────────────────────────────────────────

// 后端保留旧图片步骤以兼容历史数据；前端流程跳过图片步骤，直接进入视频生成。
const STEP_MAP: Record<string, EpisodeStep> = {
  storyboard_script:  "storyboard_script",
  storyboard_images:  "storyboard_videos",
  image_review:       "storyboard_videos",
  storyboard_videos:  "storyboard_videos",
  video_review:       "storyboard_videos",
  dubbing:            "dubbing",
  merge:              "merge",
  done:               "done",
};

export function transformEpisode(e: ApiEpisode): EpisodeDetail {
  return {
    id: e.id,
    number: e.number,
    title: e.title,
    summary: e.summary,
    scriptExcerpt: e.script_excerpt,
    wordCount: e.word_count,
    estimatedDuration: e.estimated_duration,
    status: e.status as EpisodeDetail["status"],
    currentStep: STEP_MAP[e.current_step] ?? "storyboard_script",
    shots: e.shots ? e.shots.map(transformShot) : [],
    continuityNotes: e.continuity_notes,
    finalVideoUrl: e.final_video_url,
    runningTasks: (e.running_tasks ?? []).map((t) => t.task_type),
    taskProgress: Object.fromEntries((e.running_tasks ?? []).map((t) => [t.task_type, t.progress])),
  };
}

// ─── Shot ─────────────────────────────────────────────────────

const SHOT_STATE_MAP: Record<string, ShotState> = {
  planned:        "planned",
  generating:     "generating",   // 图片生成中
  asset_required: "asset_ready",
  asset_ready:    "asset_ready",
  rendering:      "rendering",    // 视频生成中
  rendered:       "rendered",
  review_failed:  "review_failed",
  approved:       "approved",
};

export function transformShot(s: ApiShot): Shot {
  return {
    id: s.id,
    shotCode: s.shot_code,
    order: s.order,
    duration: s.duration,
    description: s.description,
    dialogues: s.dialogues ?? (
      // 兼容旧格式：dialogue/speaker 字符串
      s.dialogue ? [{ speaker: s.speaker ?? "", text: s.dialogue }] : []
    ),
    assets: s.required_assets.map((a) => a.asset_name),
    state: SHOT_STATE_MAP[s.state] ?? "planned",
    imageUrl: s.image_url ?? undefined,
    videoUrl: s.video_url ?? undefined,
    version: s.version,
    prompt: s.prompt,
  };
}

// ─── Asset ────────────────────────────────────────────────────

const ASSET_STATUS_MAP: Record<string, AssetStatus> = {
  pending:    "待确认",
  generating: "生成中",
  approved:   "已生成",
  need_regen: "需重生",
  missing:    "缺失",
};

const ASSET_TYPE_MAP: Record<string, "人物" | "场景" | "道具"> = {
  character: "人物",
  scene:     "场景",
  prop:      "道具",
  template:  "人物",
};

export function transformAsset(a: ApiAsset): Asset {
  return {
    id: a.id,
    name: a.name,
    type: ASSET_TYPE_MAP[a.asset_type] ?? "人物",
    status: ASSET_STATUS_MAP[a.status] ?? "待确认",
    previewUrl: a.preview_url,
    prompt: a.prompt,
    history: a.versions.map((v, i) => `v${i + 1}`),
  };
}

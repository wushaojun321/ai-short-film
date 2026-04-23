import type { ApiProject, ApiEpisode, ApiShot, ApiAsset } from "./api";
import type { Project, EpisodeDetail, Shot, ShotState, EpisodeStep } from "./data";

// ─── Project ──────────────────────────────────────────────────

export function transformProject(p: ApiProject): Project {
  return {
    id: p.id,
    title: p.title,
    genre: p.genre,
    format: p.format === "VERTICAL_9_16" ? "VERTICAL 9:16" : p.format,
    episodes: p.target_episode_count,
    renderedEpisodes: 0,       // 后端暂无，页面自行计算
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

// 后端 8 步 → 前端 6 步
const STEP_MAP: Record<string, EpisodeStep> = {
  storyboard_script:  "storyboard_script",
  storyboard_images:  "storyboard_images",
  image_review:       "storyboard_images",
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
    wordCount: e.word_count,
    estimatedDuration: e.estimated_duration,
    status: e.status as EpisodeDetail["status"],
    currentStep: STEP_MAP[e.current_step] ?? "storyboard_script",
    shots: [],
    continuityNotes: e.continuity_notes,
    finalVideoUrl: e.final_video_url,
  };
}

// ─── Shot ─────────────────────────────────────────────────────

const SHOT_STATE_MAP: Record<string, ShotState> = {
  planned:        "planned",
  asset_required: "asset_ready",
  asset_ready:    "asset_ready",
  rendered:       "rendered",
  review_failed:  "rendered",
  approved:       "approved",
};

export function transformShot(s: ApiShot): Shot {
  return {
    id: s.id,
    order: s.order,
    duration: s.duration,
    description: s.description,
    assets: s.required_assets.map((a) => a.name),
    state: SHOT_STATE_MAP[s.state] ?? "planned",
    imageUrl: s.image_url,
    videoUrl: s.video_url,
    version: s.version,
  };
}

// ─── Asset ────────────────────────────────────────────────────

const ASSET_STATUS_MAP: Record<string, string> = {
  pending:    "待确认",
  approved:   "已生成",
  need_regen: "需重生",
  missing:    "缺失",
};

const ASSET_TYPE_MAP: Record<string, string> = {
  character: "人物",
  scene:     "场景",
  prop:      "道具",
  template:  "模板",
};

export function transformAsset(a: ApiAsset) {
  return {
    id: a.id,
    name: a.name,
    type: (ASSET_TYPE_MAP[a.asset_type] ?? a.asset_type) as "人物" | "场景" | "道具",
    status: (ASSET_STATUS_MAP[a.status] ?? a.status) as import("./data").AssetStatus,
    previewUrl: a.preview_url,
    prompt: a.prompt,
    history: a.versions.map((v) => `v${v.version}`),
  };
}

// ─── 类型定义 ────────────────────────────────────────────────

export type ProjectInitStatus =
  | "not_started"        // 未上传剧本
  | "script_uploaded"    // 已上传剧本，待解析
  | "episodes_confirmed" // 分集规划已确认
  | "assets_confirmed"   // 资产已审核确认
  | "initialized";       // 初始化完成，可进入分集制作

export type EpisodeStatus = "not_started" | "in_progress" | "completed";

export type EpisodeStep =
  | "storyboard_script"  // 分镜脚本
  | "storyboard_videos"  // 分镜视频（含审批）
  | "dubbing"            // 配音
  | "merge"              // 合并
  | "done";              // 完成

export type ShotState =
  | "planned"       // 待生成
  | "generating"    // 图片生成中
  | "asset_ready"   // 资产就绪
  | "rendering"     // 视频生成中
  | "rendered"      // 已生成（待审批）
  | "review_failed" // 审批未通过
  | "approved";     // 已审批通过

export type AssetStatus = "已生成" | "待确认" | "需重生" | "缺失" | "生成中" | "排队中";

// ─── 步骤定义 ────────────────────────────────────────────────

export const EPISODE_STEPS: { key: EpisodeStep; label: string; shortLabel: string }[] = [
  { key: "storyboard_script",  label: "分镜脚本", shortLabel: "分镜脚本" },
  { key: "storyboard_videos",  label: "分镜视频", shortLabel: "分镜视频" },
  { key: "dubbing",            label: "配音",     shortLabel: "配音" },
  { key: "merge",              label: "合并成片", shortLabel: "合并" },
  { key: "done",               label: "完成",     shortLabel: "完成" },
];

export const STEP_ORDER: EpisodeStep[] = [
  "storyboard_script",
  "storyboard_videos",
  "dubbing",
  "merge",
  "done",
];

export function getStepIndex(step: EpisodeStep): number {
  return STEP_ORDER.indexOf(step);
}

// ─── 分镜数据 ────────────────────────────────────────────────

export interface ShotDialogueLine {
  speaker: string;
  text: string;
  emotion?: string;
  delivery?: string;
  action?: string;
  expression?: string;
}

export interface Shot {
  id: string;
  shotCode: string;
  order: number;
  duration: number; // 秒
  segmentCode?: string;
  segmentName?: string;
  segmentFunction?: string;
  shotFunction?: string;
  transitionIn?: string;
  transitionOut?: string;
  startState?: string;
  endState?: string;
  screenDirection?: string;
  continuityNotes?: string;
  usePrevLastFrame?: boolean;
  description: string;
  dialogues: ShotDialogueLine[];
  assets: string[];
  state: ShotState;
  imageUrl?: string;
  videoUrl?: string;
  version: string;
  prompt?: string;
  submittedPrompt?: string;
}

// ─── 分集数据 ────────────────────────────────────────────────

export interface EpisodeDetail {
  id: string;
  number: number;
  title: string;
  summary: string;
  scriptExcerpt: string;
  wordCount: number;
  estimatedDuration: number; // 秒
  sourceStartLine?: number;
  sourceEndLine?: number;
  dialogueCount?: number;
  sourceIntegrity?: string;
  status: EpisodeStatus;
  currentStep: EpisodeStep;
  shots: Shot[];
  continuityNotes?: string;
  finalVideoUrl?: string;
  runningTasks: string[];  // 当前 pending/running 的 task_type 列表
  taskProgress: Record<string, number>;  // task_type -> progress (0-100)
}

// ─── 项目数据 ────────────────────────────────────────────────

export interface Project {
  id: string;
  title: string;
  genre: string;
  format: string;
  episodes: number;
  renderedEpisodes: number;
  stage: string;
  progress: number;
  initStatus: ProjectInitStatus;
  blockers?: number;
  note?: string;
}

// ─── 资产 Tab ────────────────────────────────────────────────

export const ASSET_TABS = [
  { key: "characters", label: "人物" },
  { key: "scenes",     label: "场景" },
  { key: "props",      label: "道具" },
] as const;

export type AssetTabKey = "characters" | "scenes" | "props";

export interface Asset {
  id: string;
  name: string;
  type: "人物" | "场景" | "道具";
  status: AssetStatus;
  previewUrl?: string | null;
  prompt: string;
  voiceProfile?: string;
  characterName?: string;
  assetPackage?: string;
  faceIdentity?: string;
  sceneScope?: string;
  appearanceStage?: string;
  viewRequirements?: string;
  viewUrls?: Record<string, string>;
  history: string[];
}

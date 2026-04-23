import axios from "axios";

const API_BASE = (import.meta.env.VITE_API_URL as string) || "/api/v1";

const client = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err)
);

// ─── 类型（与后端对齐） ───────────────────────────────────────

export interface ApiProject {
  id: string;
  title: string;
  genre: string;
  format: string;
  target_episode_count: number;
  min_episode_duration: number;
  init_status: string;
  progress: number;
  script_file_url?: string;
  series_prompt?: string;
  parse_notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ApiEpisode {
  id: string;
  project_id: string;
  number: number;
  title: string;
  summary: string;
  word_count: number;
  estimated_duration: number;
  status: string;
  current_step: string;
  continuity_notes: string;
  final_video_url?: string;
  created_at: string;
  updated_at: string;
}

export interface ApiShot {
  id: string;
  project_id: string;
  episode_id: string;
  shot_code: string;
  order: number;
  duration: number;
  description: string;
  prompt: string;
  required_assets: Array<{ asset_id: string; name: string; asset_type: string }>;
  state: string;
  version: string;
  image_url?: string;
  video_url?: string;
  audio_url?: string;
  last_frame_url?: string;
  review_comment: string;
  generation_task_id?: string;
}

export interface ApiAsset {
  id: string;
  project_id: string;
  name: string;
  asset_type: string;
  status: string;
  prompt: string;
  preview_url?: string;
  versions: Array<{ version: number; preview_url?: string; prompt: string; created_at: string }>;
  generation_task_id?: string;
  created_at: string;
  updated_at: string;
}

export interface ApiTaskRecord {
  id: string;
  project_id?: string;
  task_type: string;
  target_id?: string;
  status: string;
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
  started_at: string;
  finished_at?: string;
}

// ─── Project API ──────────────────────────────────────────────

export const projectAPI = {
  list: (): Promise<ApiProject[]> =>
    client.get("/projects"),

  get: (projectId: string): Promise<ApiProject> =>
    client.get(`/projects/${projectId}`),

  create: (data: { title: string; genre: string; target_episode_count?: number }): Promise<ApiProject> =>
    client.post("/projects", data),

  update: (projectId: string, data: Partial<ApiProject>): Promise<ApiProject> =>
    client.patch(`/projects/${projectId}`, data),

  uploadScript: (projectId: string, file: File): Promise<ApiProject> => {
    const fd = new FormData();
    fd.append("file", file);
    return client.post(`/projects/${projectId}/upload-script`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  confirmEpisodes: (
    projectId: string,
    episodes: Array<{ number: number; title: string; summary: string; word_count: number; estimated_duration: number }>
  ): Promise<ApiProject> =>
    client.post(`/projects/${projectId}/confirm-episodes`, { episodes }),

  confirmAssets: (projectId: string): Promise<ApiProject> =>
    client.post(`/projects/${projectId}/confirm-assets`),
};

// ─── Episode API ──────────────────────────────────────────────

export const episodeAPI = {
  list: (projectId: string): Promise<ApiEpisode[]> =>
    client.get(`/projects/${projectId}/episodes`),

  get: (projectId: string, episodeId: string): Promise<ApiEpisode> =>
    client.get(`/projects/${projectId}/episodes/${episodeId}`),

  update: (projectId: string, episodeId: string, data: Partial<ApiEpisode>): Promise<ApiEpisode> =>
    client.patch(`/projects/${projectId}/episodes/${episodeId}`, data),

  advanceStep: (projectId: string, episodeId: string): Promise<ApiEpisode> =>
    client.post(`/projects/${projectId}/episodes/${episodeId}/advance-step`),

  setStep: (projectId: string, episodeId: string, step: string): Promise<ApiEpisode> =>
    client.post(`/projects/${projectId}/episodes/${episodeId}/set-step`, { step }),
};

// ─── Shot API ─────────────────────────────────────────────────

export const shotAPI = {
  list: (projectId: string, episodeId: string): Promise<ApiShot[]> =>
    client.get(`/projects/${projectId}/episodes/${episodeId}/shots`),

  get: (projectId: string, episodeId: string, shotId: string): Promise<ApiShot> =>
    client.get(`/projects/${projectId}/episodes/${episodeId}/shots/${shotId}`),

  update: (projectId: string, episodeId: string, shotId: string, data: Partial<ApiShot>): Promise<ApiShot> =>
    client.patch(`/projects/${projectId}/episodes/${episodeId}/shots/${shotId}`, data),

  review: (
    projectId: string,
    episodeId: string,
    shotId: string,
    data: { approved: boolean; comment?: string }
  ): Promise<ApiShot> =>
    client.post(`/projects/${projectId}/episodes/${episodeId}/shots/${shotId}/review`, data),

  batchReview: (
    projectId: string,
    episodeId: string,
    reviews: Array<{ shot_id: string; approved: boolean; comment?: string }>
  ): Promise<ApiShot[]> =>
    client.post(`/projects/${projectId}/episodes/${episodeId}/shots/batch-review`, { reviews }),
};

// ─── Asset API ────────────────────────────────────────────────

export const assetAPI = {
  list: (projectId: string): Promise<ApiAsset[]> =>
    client.get(`/projects/${projectId}/assets`),

  get: (projectId: string, assetId: string): Promise<ApiAsset> =>
    client.get(`/projects/${projectId}/assets/${assetId}`),

  update: (projectId: string, assetId: string, data: Partial<ApiAsset>): Promise<ApiAsset> =>
    client.patch(`/projects/${projectId}/assets/${assetId}`, data),

  confirm: (projectId: string, assetId: string): Promise<ApiAsset> =>
    client.post(`/projects/${projectId}/assets/${assetId}/confirm`),

  regen: (projectId: string, assetId: string): Promise<ApiAsset> =>
    client.post(`/projects/${projectId}/assets/${assetId}/regen`),
};

// ─── Generate API ─────────────────────────────────────────────

export const generateAPI = {
  parseScript: (projectId: string, data: { target_episodes: number; min_duration: number; parse_notes?: string }): Promise<ApiTaskRecord> =>
    client.post(`/generate/projects/${projectId}/parse-script`, data),

  shotScript: (episodeId: string): Promise<ApiTaskRecord> =>
    client.post(`/generate/episodes/${episodeId}/shot-script`),

  assetImage: (assetId: string): Promise<ApiTaskRecord> =>
    client.post(`/generate/assets/${assetId}/image`),

  shotImage: (shotId: string): Promise<ApiTaskRecord> =>
    client.post(`/generate/shots/${shotId}/image`),

  shotVideo: (shotId: string): Promise<ApiTaskRecord> =>
    client.post(`/generate/shots/${shotId}/video`),

  mergeEpisode: (episodeId: string): Promise<ApiTaskRecord> =>
    client.post(`/generate/episodes/${episodeId}/merge`),

  getTaskProgress: (recordId: string): Promise<ApiTaskRecord> =>
    client.get(`/generate/tasks/${recordId}/progress`),
};

// ─── 任务轮询工具 ─────────────────────────────────────────────

export function pollTask(
  recordId: string,
  onProgress: (task: ApiTaskRecord) => void,
  intervalMs = 2000,
  timeoutMs = 300000
): Promise<ApiTaskRecord> {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const timer = setInterval(async () => {
      try {
        const task = await generateAPI.getTaskProgress(recordId);
        onProgress(task);
        if (task.status === "success") {
          clearInterval(timer);
          resolve(task);
        } else if (task.status === "failed" || task.status === "cancelled") {
          clearInterval(timer);
          reject(new Error(task.error ?? "任务失败"));
        } else if (Date.now() - start > timeoutMs) {
          clearInterval(timer);
          reject(new Error("任务超时"));
        }
      } catch (err) {
        clearInterval(timer);
        reject(err);
      }
    }, intervalMs);
  });
}

import axios from "axios";

const API_BASE = (import.meta.env.VITE_API_URL as string) || "/api/v1";

const client = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// 将后端返回的 _id 统一映射为 id（Beanie/MongoDB 默认序列化为 _id）
function normalizeIds(data: unknown): unknown {
  if (Array.isArray(data)) return data.map(normalizeIds);
  if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    const result: Record<string, unknown> = {};
    for (const key of Object.keys(obj)) {
      const val = normalizeIds(obj[key]);
      result[key === "_id" ? "id" : key] = val;
    }
    return result;
  }
  return data;
}

// 将 FastAPI 422 detail 数组转成可读字符串
function extractErrorMessage(err: unknown): string {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string; loc?: string[] }) =>
      d.loc ? `${d.loc.slice(-1)[0]}: ${d.msg}` : d.msg ?? "错误"
    ).join("; ");
  }
  if (typeof detail === "string") return detail;
  return e?.message ?? "请求失败";
}

// 请求拦截：注入 Authorization Bearer token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (res) => normalizeIds(res.data) as any,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_username");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
      return Promise.reject(new Error("登录已过期，请重新登录"));
    }
    return Promise.reject(new Error(extractErrorMessage(err)));
  }
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
  script_excerpt: string;
  word_count: number;
  estimated_duration: number;
  status: string;
  current_step: string;
  continuity_notes: string;
  final_video_url?: string;
  shots?: ApiShot[];  // 当 include_shots=true 时后端附带
  running_tasks?: Array<{ task_type: string; status: string; progress: number }>;  // 当前 pending/running 的任务
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
  segment_code?: string;
  segment_name?: string;
  segment_function?: string;
  shot_function?: string;
  description: string;
  dialogues: Array<{ speaker: string; text: string }>;
  // 兼容旧数据
  dialogue?: string;
  speaker?: string;
  prompt: string;
  submitted_prompt?: string;
  required_assets: Array<{ asset_id: string; asset_name: string }>;
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

// generate 接口统一返回 { task_id, record_id }
export interface ApiGenResponse {
  task_id: string;
  record_id: string;
}

export interface ApiTaskRecord {
  id: string;
  project_id?: string;
  episode_id?: string;
  task_type: string;
  target_id?: string;
  status: string;
  progress: number;
  logs?: string[];
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

  create: (data: { title: string; target_episode_count?: number }): Promise<ApiProject> =>
    client.post("/projects", data),

  update: (projectId: string, data: Partial<ApiProject>): Promise<ApiProject> =>
    client.patch(`/projects/${projectId}`, data),

  delete: (projectId: string): Promise<void> =>
    client.delete(`/projects/${projectId}`),

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

  get: (projectId: string, episodeId: string, opts?: { include_shots?: boolean }): Promise<ApiEpisode> =>
    client.get(`/projects/${projectId}/episodes/${episodeId}`, { params: opts }),
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

  delete: (projectId: string, assetId: string): Promise<void> =>
    client.delete(`/projects/${projectId}/assets/${assetId}`),
};

// ─── Generate API ─────────────────────────────────────────────

export const generateAPI = {
  parseScript: (projectId: string, data: { target_episodes: number; min_duration: number; parse_notes?: string }): Promise<ApiGenResponse> =>
    client.post(`/generate/projects/${projectId}/parse-script`, data),

  shotScript: (episodeId: string, feedback?: string): Promise<ApiGenResponse> =>
    client.post(`/generate/episodes/${episodeId}/shot-script`, undefined, {
      params: feedback ? { feedback } : undefined,
    }),

  assetImage: (assetId: string): Promise<ApiGenResponse> =>
    client.post(`/generate/assets/${assetId}/image`),

  shotImage: (shotId: string): Promise<ApiGenResponse> =>
    client.post(`/generate/shots/${shotId}/image`),

  shotVideo: (shotId: string): Promise<ApiGenResponse> =>
    client.post(`/generate/shots/${shotId}/video`),

  mergeEpisode: (episodeId: string): Promise<ApiGenResponse> =>
    client.post(`/generate/episodes/${episodeId}/merge`),

  // 普通 GET 轮询（不是 SSE）
  getTask: (recordId: string): Promise<ApiTaskRecord> =>
    client.get(`/tasks/${recordId}`),

  listTasks: (params: { project_id?: string; episode_id?: string; task_type?: string; limit?: number }): Promise<ApiTaskRecord[]> =>
    client.get(`/tasks`, { params: { ...params, limit: params.limit ?? 5 } }),
};

// ─── Conversation API ──────────────────────────────────────────

export interface ApiMessage {
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  task_id?: string;
}

export interface ApiConversation {
  id: string;
  target_type: string;
  target_id: string;
  project_id: string;
  title: string;
  messages: ApiMessage[];
  created_at: string;
  updated_at: string;
}

export interface ApiChatResponse {
  reply: string;
  tool_calls_made: Array<{ tool: string; arguments: Record<string, unknown>; result: Record<string, unknown> }>;
  conversation_id: string;
}

export const conversationAPI = {
  create: (data: { target_type: string; target_id: string; project_id: string; title?: string }): Promise<ApiConversation> =>
    client.post("/conversations", data),

  list: (params: { target_id?: string; target_type?: string; project_id?: string }): Promise<ApiConversation[]> =>
    client.get("/conversations", { params }),

  get: (convId: string): Promise<ApiConversation> =>
    client.get(`/conversations/${convId}`),

  delete: (convId: string): Promise<void> =>
    client.delete(`/conversations/${convId}`),

  chat: (convId: string, content: string): Promise<ApiChatResponse> =>
    client.post(`/conversations/${convId}/chat`, { content }),
};

// ─── STS 临时密钥 ──────────────────────────────────────────────

export interface StsToken {
  tmpSecretId: string;
  tmpSecretKey: string;
  sessionToken: string;
  expiredTime: number; // unix timestamp (seconds)
  bucket: string;
  region: string;
}

export const stsAPI = {
  getToken: (): Promise<StsToken> => client.get("/sts-token"),
};

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
        const task = await generateAPI.getTask(recordId);
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

// ─── Auth API ─────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  token_type: string;
  username: string;
}

export const authAPI = {
  login: (username: string, password: string): Promise<TokenResponse> =>
    client.post("/auth/login", { username, password }),
  register: (username: string, password: string, invite_code: string): Promise<TokenResponse> =>
    client.post("/auth/register", { username, password, invite_code }),
};

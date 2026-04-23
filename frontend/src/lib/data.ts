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
  | "storyboard_images"  // 分镜剧照（含审批）
  | "storyboard_videos"  // 分镜视频（含审批）
  | "dubbing"            // 配音
  | "merge"              // 合并
  | "done";              // 完成

export type ShotState =
  | "planned"       // 待生成
  | "asset_ready"   // 资产就绪
  | "rendered"      // 已生成（待审批）
  | "approved";     // 已审批通过

export type AssetStatus = "已生成" | "待确认" | "需重生" | "缺失";

// ─── 步骤定义 ────────────────────────────────────────────────

export const EPISODE_STEPS: { key: EpisodeStep; label: string; shortLabel: string }[] = [
  { key: "storyboard_script",  label: "分镜脚本", shortLabel: "分镜脚本" },
  { key: "storyboard_images",  label: "分镜剧照", shortLabel: "分镜剧照" },
  { key: "storyboard_videos",  label: "分镜视频", shortLabel: "分镜视频" },
  { key: "dubbing",            label: "配音",     shortLabel: "配音" },
  { key: "merge",              label: "合并成片", shortLabel: "合并" },
  { key: "done",               label: "完成",     shortLabel: "完成" },
];

export const STEP_ORDER: EpisodeStep[] = [
  "storyboard_script",
  "storyboard_images",
  "storyboard_videos",
  "dubbing",
  "merge",
  "done",
];

export function getStepIndex(step: EpisodeStep): number {
  return STEP_ORDER.indexOf(step);
}

// ─── 分镜数据 ────────────────────────────────────────────────

export interface Shot {
  id: string;
  order: number;
  duration: number; // 秒
  description: string;
  assets: string[];
  state: ShotState;
  imageUrl?: string;
  videoUrl?: string;
  version: string;
}

export const MOCK_SHOTS: Shot[] = [
  {
    id: "S01", order: 1, duration: 6, version: "v3", state: "approved",
    description: "傍晚长公主房门口中景，谢风凌提竹篮入场，肩上带夜风，镜头缓推，人物保持压抑克制。",
    assets: ["谢风凌·夜归造型", "长公主房内·傍晚主位"],
    imageUrl: "/previews/shot-ep04-s01.svg",
    videoUrl: "/previews/video-ep04-s01.mp4",
  },
  {
    id: "S02", order: 2, duration: 5, version: "v3", state: "approved",
    description: "主位反打，李云湘正面略仰机位，神情克制，窗纱透光。",
    assets: ["李云湘·基础核心图", "长公主房内·傍晚主位"],
    imageUrl: "/previews/asset-character-li.svg",
    videoUrl: "/previews/video-ep04-s02.mp4",
  },
  {
    id: "S03", order: 3, duration: 7, version: "v3", state: "rendered",
    description: "俯拍竹篮递呈动作，谢风凌双手持篮低头，李云湘手指轻触篮沿。",
    assets: ["谢风凌·夜归造型", "竹篮"],
    imageUrl: "/previews/shot-ep04-s01.svg",
  },
  {
    id: "S04", order: 4, duration: 5, version: "v2", state: "rendered",
    description: "侧面近景，谢风凌不说话，只用眼神承受试探，脸部轮廓要保持角色核心图一致。",
    assets: ["谢风凌·夜归造型"],
    imageUrl: "/previews/asset-character-xie.svg",
  },
  {
    id: "S05", order: 5, duration: 6, version: "v3", state: "rendered",
    description: "李云湘主位慢推，开口试探，台词：「你这一趟，带回了什么？」",
    assets: ["李云湘·基础核心图", "长公主房内·傍晚主位"],
    imageUrl: "/previews/asset-character-li.svg",
  },
  {
    id: "S06", order: 6, duration: 5, version: "v1", state: "asset_ready",
    description: "顾文池侧殿走位，全景跟拍，深红锦袍飘动，步伐轻缓带试探意味。",
    assets: ["顾文池·侧殿夜间造型", "长廊·夜"],
  },
  {
    id: "S07", order: 7, duration: 8, version: "v3", state: "rendered",
    description: "过肩双人对峙，李云湘与谢风凌正面对峙，机位固定，空气凝固感。",
    assets: ["李云湘·基础核心图", "谢风凌·夜归造型", "长公主房内·傍晚主位"],
    imageUrl: "/previews/asset-scene-room.svg",
  },
  {
    id: "S08", order: 8, duration: 4, version: "—", state: "planned",
    description: "茶杯桌面俯拍特写，白瓷茶盏与水渍，烛光偏冷，作为气氛插镜。",
    assets: ["茶具桌面特写"],
  },
  {
    id: "S09", order: 9, duration: 6, version: "—", state: "planned",
    description: "廊下远景，谢风凌背身走出，月色冷清，镜头固定不追。",
    assets: ["谢风凌·夜归造型", "长廊·夜"],
  },
];

// ─── 分集数据 ────────────────────────────────────────────────

export interface EpisodeDetail {
  id: string;
  number: number;
  title: string;
  summary: string;
  wordCount: number;
  estimatedDuration: number; // 秒
  status: EpisodeStatus;
  currentStep: EpisodeStep;
  shots: Shot[];
  continuityNotes?: string;
}

export const EPISODE_DETAILS: EpisodeDetail[] = [
  {
    id: "EP01", number: 1, title: "风起长公主府",
    summary: "谢风凌夜入府，刺杀未遂后被长公主留下。",
    wordCount: 2400, estimatedDuration: 118,
    status: "completed", currentStep: "done",
    shots: MOCK_SHOTS,
    continuityNotes: "李云湘：墨绿宫装，金簪；谢风凌：黑色武人服，无伤；时间：深夜",
  },
  {
    id: "EP02", number: 2, title: "旧人留用",
    summary: "长公主开始试探谢风凌，皇帝暗中观察。",
    wordCount: 2600, estimatedDuration: 124,
    status: "completed", currentStep: "done",
    shots: MOCK_SHOTS,
    continuityNotes: "李云湘：宫装不变；谢风凌：S01-S03戴蒙眼纱布，S04摘除",
  },
  {
    id: "EP03", number: 3, title: "顾文池布线",
    summary: "旧宠挑拨布局，长公主府内权力再平衡。",
    wordCount: 2500, estimatedDuration: 121,
    status: "completed", currentStep: "done",
    shots: MOCK_SHOTS,
    continuityNotes: "顾文池：深红锦袍首次亮相；谢风凌：黑衣，无障碍",
  },
  {
    id: "EP04", number: 4, title: "夜探与试探",
    summary: "谢风凌归来，李云湘在房内正面试探，气氛升级。",
    wordCount: 2800, estimatedDuration: 128,
    status: "in_progress", currentStep: "storyboard_videos",
    shots: MOCK_SHOTS,
    continuityNotes: "谢风凌：提竹篮归来，黑衣轻尘；李云湘：傍晚宫装；时间：傍晚→入夜",
  },
  {
    id: "EP05", number: 5, title: "皇帝入府",
    summary: "李睿亲至，关系进入更强对撞。",
    wordCount: 2500, estimatedDuration: 120,
    status: "in_progress", currentStep: "storyboard_script",
    shots: MOCK_SHOTS.slice(0, 4),
    continuityNotes: "李睿：帝王冠，白玉佩；承接EP04结尾情绪",
  },
  {
    id: "EP06", number: 6, title: "侧殿布线",
    summary: "顾文池开始在宫中布线，长公主府风向变化。",
    wordCount: 0, estimatedDuration: 0,
    status: "not_started", currentStep: "storyboard_script",
    shots: [],
  },
  {
    id: "EP07", number: 7, title: "（待规划）",
    summary: "",
    wordCount: 0, estimatedDuration: 0,
    status: "not_started", currentStep: "storyboard_script",
    shots: [],
  },
  {
    id: "EP08", number: 8, title: "（待规划）",
    summary: "",
    wordCount: 0, estimatedDuration: 0,
    status: "not_started", currentStep: "storyboard_script",
    shots: [],
  },
];

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

export const PROJECTS: Project[] = [
  {
    id: "long-princess-power-play",
    title: "长公主权谋录",
    genre: "古装权谋短剧",
    format: "VERTICAL 9:16",
    renderedEpisodes: 4,
    episodes: 8,
    stage: "分集制作",
    progress: 68,
    initStatus: "initialized",
    blockers: 2,
    note: "EP04 正在审核，EP05 分镜脚本生成中。",
  },
  {
    id: "reborn-bit",
    title: "重生之Bit",
    genre: "都市逆袭短剧",
    format: "VERTICAL 9:16",
    renderedEpisodes: 0,
    episodes: 5,
    stage: "资产审核",
    progress: 42,
    initStatus: "episodes_confirmed",
    blockers: 3,
    note: "角色造型基本完成，场景资产缺 3 张，待审核后初始化。",
  },
  {
    id: "apocalypse-hero",
    title: "末世：我以为我是废柴",
    genre: "末世成长短剧",
    format: "VERTICAL 9:16",
    renderedEpisodes: 0,
    episodes: 0,
    stage: "剧本上传",
    progress: 10,
    initStatus: "script_uploaded",
    blockers: 1,
    note: "剧本已上传，待点击解析。",
  },
];

export function getProject(projectId: string): Project | undefined {
  return PROJECTS.find((p) => p.id === projectId);
}

export function getEpisodeDetails(projectId: string): EpisodeDetail[] {
  if (projectId === "long-princess-power-play") return EPISODE_DETAILS;
  return EPISODE_DETAILS.slice(0, 3);
}

export function getEpisodeById(projectId: string, episodeId: string): EpisodeDetail | undefined {
  return getEpisodeDetails(projectId).find((e) => e.id === episodeId);
}

export function getFirstInProgressEpisode(projectId: string): EpisodeDetail | undefined {
  const episodes = getEpisodeDetails(projectId);
  return episodes.find((e) => e.status === "in_progress") ?? episodes[0];
}

// ─── 资产数据 ────────────────────────────────────────────────

export const ASSET_TABS = [
  { key: "characters", label: "人物" },
  { key: "scenes",     label: "场景" },
  { key: "props",      label: "道具" },
] as const;

export const ASSET_LIBRARY = {
  characters: [
    {
      id: "asset-char-1",
      name: "李云湘 · 基础核心图",
      type: "人物" as const,
      status: "已生成" as AssetStatus,
      previewUrl: "/previews/asset-character-li.svg",
      prompt: "二十七岁摄政长公主，冷白肤，凤眼，墨绿宫装，金簪，威压强，写实电影感。",
      history: ["v1 初版偏温柔", "v2 五官更凌厉", "v3 当前采用"],
    },
    {
      id: "asset-char-2",
      name: "谢风凌 · 夜归造型",
      type: "人物" as const,
      status: "待确认" as AssetStatus,
      previewUrl: "/previews/asset-character-xie.svg",
      prompt: "青年暗卫，黑衣带风尘，提竹篮入府，克制但压抑，潮湿夜色，写实质感。",
      history: ["v1 可用", "v2 当前采用"],
    },
    {
      id: "asset-char-3",
      name: "顾文池 · 侧殿夜间造型",
      type: "人物" as const,
      status: "需重生" as AssetStatus,
      previewUrl: undefined,
      prompt: "男宠气质，淡泪痣，深红锦袍，夜色中带试探笑意，写实电影光。",
      history: ["v1 泪痣过重", "v2 待生成"],
    },
  ],
  scenes: [
    {
      id: "asset-scene-1",
      name: "长公主房内 · 傍晚主位",
      type: "场景" as const,
      status: "已生成" as AssetStatus,
      previewUrl: "/previews/asset-scene-room.svg",
      prompt: "古代公主卧房，主位视角，傍晚天光，窗纱和屏风形成纵深，电影布光。",
      history: ["v1 空间过窄", "v2 当前采用"],
    },
    {
      id: "asset-scene-2",
      name: "长廊 · 夜",
      type: "场景" as const,
      status: "待确认" as AssetStatus,
      previewUrl: "/previews/asset-scene-room.svg",
      prompt: "宫廷长廊夜景，冷色石地，灯笼光斑，人物背身离开的留白空间。",
      history: ["v1 当前采用"],
    },
    {
      id: "asset-scene-3",
      name: "茶具桌面特写",
      type: "场景" as const,
      status: "缺失" as AssetStatus,
      previewUrl: undefined,
      prompt: "古代木桌俯拍，白瓷茶盏与茶渍，夜色烛光，适合近景插镜。",
      history: ["尚未生成"],
    },
  ],
  props: [
    {
      id: "asset-prop-1",
      name: "竹篮",
      type: "道具" as const,
      status: "已生成" as AssetStatus,
      previewUrl: "/previews/asset-prop-basket.svg",
      prompt: "旧竹编篮，带浅色布巾，适合夜归携带，写实。",
      history: ["v1 被误生为食盒", "v2 当前采用"],
    },
    {
      id: "asset-prop-2",
      name: "金簪",
      type: "道具" as const,
      status: "待确认" as AssetStatus,
      previewUrl: "/previews/asset-prop-basket.svg",
      prompt: "长公主用金簪，细长，冷金属质感，不浮夸。",
      history: ["v1 当前采用"],
    },
  ],
};

export type AssetTabKey = keyof typeof ASSET_LIBRARY;
export type Asset = (typeof ASSET_LIBRARY)[AssetTabKey][number];

export function getAssetLibraryItems(): Asset[] {
  return Object.values(ASSET_LIBRARY).flat();
}

export function getAssetById(assetId: string): Asset | null {
  return getAssetLibraryItems().find((a) => a.id === assetId) ?? null;
}

export function getAssetsByTab(tab: AssetTabKey): Asset[] {
  return ASSET_LIBRARY[tab];
}

// ─── 剧集提示词 Mock ────────────────────────────────────────

export const SERIES_PROMPT_MOCK = `【世界观】
大周王朝末年，皇权旁落，摄政长公主李云湘把持朝政十年。宫廷内外明争暗斗，各方势力以情爱为刀、以权谋为局，在一方锦绣天地里上演生死博弈。

【主要故事情节】
第一幕：前朝刺客谢风凌奉命刺杀长公主，刺杀未遂反被擒。长公主识破背后势力，决定留用谢风凌作为棋子，暗中调查幕后主使。
第二幕：旧宠顾文池察觉地位动摇，在宫中布线，试图借皇帝李睿之手打压长公主势力。谢风凌夹在两方之间，忠诚与生存产生撕裂。
第三幕：皇帝亲至长公主府，三方关系进入最高烈度对撞。长公主以退为进，谢风凌最终选择站队，以一个秘密换取所有人的平衡。

【人物特征】
· 李云湘（长公主）：27岁，摄政十年，冷白肤凤眼，墨绿宫装。外表冷静克制，内藏危机意识极强的生存本能。从不轻信任何人，每一句温柔都是试探。
· 谢风凌：青年暗卫出身，黑衣风尘感，惯于沉默。情感压抑，行事果决但内心极重情义，是整部剧道德矛盾最密集的角色。
· 顾文池：前宠臣，深红锦袍，淡泪痣，笑意里藏刀。擅长利用情感制造裂缝，是推动剧情走向悲剧的关键变量。
· 李睿（皇帝）：表面宽仁，实则藏锋，白玉佩帝王冠，每次出场都能让场内气压骤降。`;

// ─── 初始化流程 Mock 数据 ────────────────────────────────────

export const NEW_PROJECT_MOCK_EPISODES = [
  { id: "EP01", title: "风起长公主府", wordCount: 2400, estimatedDuration: 118, summary: "谢风凌夜入府，刺杀未遂后被长公主留下。" },
  { id: "EP02", title: "旧人留用", wordCount: 2600, estimatedDuration: 124, summary: "长公主开始试探谢风凌，皇帝暗中观察。" },
  { id: "EP03", title: "顾文池布线", wordCount: 2500, estimatedDuration: 121, summary: "旧宠挑拨布局，长公主府内权力再平衡。" },
  { id: "EP04", title: "夜探与试探", wordCount: 2800, estimatedDuration: 128, summary: "谢风凌归来，李云湘在房内正面试探，气氛升级。" },
  { id: "EP05", title: "皇帝入府", wordCount: 2500, estimatedDuration: 120, summary: "李睿亲至，关系进入更强对撞。" },
  { id: "EP06", title: "侧殿布线", wordCount: 2300, estimatedDuration: 115, summary: "顾文池开始在宫中布线，长公主府风向变化。" },
];

// ─── 解析日志 Mock ────────────────────────────────────────────

export const PARSE_LOG_LINES = [
  { delay: 0,    text: "[解析引擎] 正在读取剧本文件…" },
  { delay: 600,  text: "[预处理] 文本分词完成，共 15,832 字" },
  { delay: 1200, text: "[结构识别] 检测到场景标记 48 处" },
  { delay: 1900, text: "[结构识别] 识别对话段落 213 段" },
  { delay: 2600, text: "[AI 模型] 正在调用剧本理解模型（gpt-4o）…" },
  { delay: 3400, text: "[AI 模型] 世界观与时代背景提取完成" },
  { delay: 4100, text: "[AI 模型] 主线情节梳理中…" },
  { delay: 4900, text: "[AI 模型] 识别出 4 位核心角色，8 位次要角色" },
  { delay: 5700, text: "[分集规划] 正在按目标集数拆分剧情段落…" },
  { delay: 6500, text: "[分集规划] 生成分集草案：6 集，总时长预估 12'08\"" },
  { delay: 7200, text: "[连续性分析] 提取角色状态变化节点…" },
  { delay: 8000, text: "[连续性分析] 生成跨集连续性约束 18 条" },
  { delay: 8700, text: "[资产识别] 扫描人物造型描述…" },
  { delay: 9400, text: "[资产识别] 识别出 3 个主要人物资产需求" },
  { delay: 10100, text: "[资产识别] 识别出 3 个场景资产需求" },
  { delay: 10800, text: "[资产识别] 识别出 2 个道具资产需求" },
  { delay: 11500, text: "[生成提示词] 正在生成资产生成提示词…" },
  { delay: 12200, text: "[生成提示词] 剧集总览提示词生成完成（共 487 字）" },
  { delay: 12900, text: "[收尾] 数据打包写入，准备返回结果…" },
  { delay: 13600, text: "✓ 解析完成！共耗时 13.6s，结果已就绪。" },
];

import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload, FileText, ChevronRight, Check, Loader2,
  Edit2, Clock, Hash, Sparkles, Terminal, RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  ASSET_LIBRARY, NEW_PROJECT_MOCK_EPISODES, AssetStatus,
  SERIES_PROMPT_MOCK, PARSE_LOG_LINES,
} from "@/lib/data";
import { cn } from "@/lib/utils";

// 4 个阶段：1 → 1.5（等待解析）→ 2 → 3
type Phase = 1 | 1.5 | 2 | 3;

interface EpisodeDraft {
  id: string;
  title: string;
  wordCount: number;
  estimatedDuration: number;
  summary: string;
}

// 步骤条视觉节点（3个）
const STEP_NODES = [
  { visual: 1, label: "导入剧本" },
  { visual: 2, label: "分集规划" },
  { visual: 3, label: "资产审核" },
];

function StepIndicator({ current }: { current: Phase }) {
  // phase 1 / 1.5 → visual 1; phase 2 → visual 2; phase 3 → visual 3
  const visualCurrent = current < 2 ? 1 : current === 2 ? 2 : 3;

  return (
    <div className="flex items-center gap-2 mb-8">
      {STEP_NODES.map((node, idx) => {
        const isDone   = visualCurrent > node.visual;
        const isActive = visualCurrent === node.visual;
        return (
          <div key={node.visual} className="flex items-center gap-2">
            <div className={cn(
              "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all",
              isDone   && "bg-brand text-white",
              isActive && "bg-brand text-white ring-4 ring-brand/20",
              !isDone && !isActive && "bg-soft text-muted border border-line",
            )}>
              {isDone ? <Check className="w-3.5 h-3.5" /> : node.visual}
            </div>
            <span className={cn(
              "text-sm hidden sm:block",
              isActive ? "font-semibold text-text" : "text-muted"
            )}>
              {node.label}
            </span>
            {idx < STEP_NODES.length - 1 && (
              <ChevronRight className="w-4 h-4 text-line mx-1" />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Phase 1：导入剧本 ─────────────────────────────────────

function Phase1({
  onSubmit,
  uploadedFile,
  setUploadedFile,
}: {
  onSubmit: () => void;
  uploadedFile: File | null;
  setUploadedFile: (f: File | null) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    episodeCount: "8",
    minDuration: "120",
    notes: "",
  });

  const handleFile = (file: File) => setUploadedFile(file);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  // 接口调用成功（即使解析未完成）即跳转到等待页
  const handleSubmit = () => {
    setSubmitting(true);
    setTimeout(() => {
      setSubmitting(false);
      setDialogOpen(false);
      onSubmit();
    }, 500);
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-text mb-1">导入剧本</h2>
        <p className="text-sm text-sub">上传剧本文件，AI 将自动解析分集规划和资产需求。</p>
      </div>

      {/* 上传区域 */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !uploadedFile && fileRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer",
          dragging ? "border-brand bg-brand-soft" : "border-line hover:border-brand/50 hover:bg-soft",
          uploadedFile && "border-brand bg-brand-soft cursor-default"
        )}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".txt,.docx,.pdf"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {uploadedFile ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-brand/10 flex items-center justify-center">
              <FileText className="w-6 h-6 text-brand" />
            </div>
            <div>
              <p className="font-medium text-text text-sm">{uploadedFile.name}</p>
              <p className="text-xs text-muted mt-0.5">{(uploadedFile.size / 1024).toFixed(1)} KB</p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setUploadedFile(null); }}
              className="text-xs text-muted hover:text-danger transition-colors"
            >
              重新上传
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-soft flex items-center justify-center">
              <Upload className="w-6 h-6 text-muted" />
            </div>
            <div>
              <p className="text-sm font-medium text-text">点击或拖拽上传剧本</p>
              <p className="text-xs text-muted mt-1">支持 .txt · .docx · .pdf</p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-6 flex justify-end">
        <Button disabled={!uploadedFile} onClick={() => setDialogOpen(true)}>
          解析剧本 <ChevronRight className="w-4 h-4" />
        </Button>
      </div>

      {/* 解析配置弹窗 */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>配置解析参数</DialogTitle>
            <DialogDescription>
              AI 将根据以下参数拆解剧本，任务提交后将在后台异步运行，通常需要 10–30 秒。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-sub mb-1.5 block">目标集数</label>
                <Input
                  type="number"
                  value={form.episodeCount}
                  onChange={(e) => setForm({ ...form, episodeCount: e.target.value })}
                  placeholder="8"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-sub mb-1.5 block">每集最短时长（秒）</label>
                <Input
                  type="number"
                  value={form.minDuration}
                  onChange={(e) => setForm({ ...form, minDuration: e.target.value })}
                  placeholder="120"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-sub mb-1.5 block">补充说明 / 连续性约束</label>
              <Textarea
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="例如：主角全程不能摘面具；第三集之后出现伤势；人物性格等补充说明…"
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>取消</Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting
                ? <><Loader2 className="w-4 h-4 animate-spin" />提交中…</>
                : <>提交解析任务 <ChevronRight className="w-4 h-4" /></>}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Phase 1.5：智能解析等待 ──────────────────────────────

function PhaseWaiting({ onDone }: { onDone: () => void }) {
  const [logs, setLogs] = useState<string[]>([]);
  const [finished, setFinished] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];

    PARSE_LOG_LINES.forEach(({ delay, text }) => {
      timers.push(setTimeout(() => {
        setLogs((prev) => [...prev, text]);
        if (text.startsWith("✓")) setFinished(true);
      }, delay));
    });

    return () => timers.forEach(clearTimeout);
  }, []);

  // 自动滚动到末尾
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="max-w-xl mx-auto">
      {/* 标题 */}
      <div className="mb-6 flex items-start gap-4">
        <div className={cn(
          "w-12 h-12 rounded-xl flex items-center justify-center shrink-0 transition-colors",
          finished ? "bg-brand-soft" : "bg-primary/5"
        )}>
          {finished
            ? <Sparkles className="w-6 h-6 text-brand" />
            : <Loader2 className="w-6 h-6 text-primary animate-spin" />}
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text mb-1">
            {finished ? "解析完成，结果已就绪" : "AI 正在深度解析剧本"}
          </h2>
          <p className="text-sm text-sub leading-relaxed">
            {finished
              ? "分集规划和资产清单已全部生成，点击下方按钮进入分集规划审核。"
              : "正在理解剧情结构、提取人物关系并规划分集方案，请稍候——通常需要 10–30 秒。"}
          </p>
        </div>
      </div>

      {/* 日志终端 */}
      <div className="rounded-xl border border-line bg-slate-950 overflow-hidden mb-6 shadow-md">
        {/* macOS 风格标题栏 */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 border-b border-slate-800">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/70" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
            <div className="w-3 h-3 rounded-full bg-green-500/70" />
          </div>
          <div className="flex-1 flex items-center justify-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-xs text-slate-500 font-mono">script-parser · live log</span>
          </div>
          {/* 状态指示 */}
          <div className="flex items-center gap-1.5">
            {finished
              ? <span className="text-xs text-green-400 font-mono">done</span>
              : <span className="flex items-center gap-1 text-xs text-yellow-400 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse inline-block" />
                  running
                </span>
            }
          </div>
        </div>

        {/* 日志滚动区 */}
        <div className="p-4 h-72 overflow-y-auto font-mono">
          {logs.map((line, i) => (
            <div
              key={i}
              className={cn(
                "text-xs leading-relaxed mb-0.5 animate-fade-in",
                line.startsWith("✓") ? "text-green-400 font-semibold mt-1" : "text-slate-400"
              )}
            >
              <span className="text-slate-600 mr-2 select-none tabular-nums">
                {String(i + 1).padStart(2, "0")}
              </span>
              {line}
            </div>
          ))}
          {/* 光标 */}
          {!finished && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-1">
              <span className="text-slate-600 mr-2 select-none">
                {String(logs.length + 1).padStart(2, "0")}
              </span>
              <span className="inline-block w-2 h-3.5 bg-slate-500 animate-pulse rounded-sm" />
            </div>
          )}
          <div ref={logEndRef} />
        </div>
      </div>

      {/* 操作 */}
      <div className="flex justify-between items-center">
        <p className="text-xs text-muted">
          {finished
            ? `共 ${logs.length} 条处理日志`
            : `已处理 ${logs.length} / ${PARSE_LOG_LINES.length} 步…`}
        </p>
        <Button onClick={onDone} disabled={!finished}>
          {finished
            ? <>查看分集规划 <ChevronRight className="w-4 h-4" /></>
            : <><Loader2 className="w-4 h-4 animate-spin" />等待解析完成…</>}
        </Button>
      </div>
    </div>
  );
}

// ─── Phase 2：分集规划 ─────────────────────────────────────

function Phase2({
  episodes,
  setEpisodes,
  onNext,
}: {
  episodes: EpisodeDraft[];
  setEpisodes: (eps: EpisodeDraft[]) => void;
  onNext: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);

  const update = (id: string, patch: Partial<EpisodeDraft>) => {
    setEpisodes(episodes.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  };

  const totalDuration = episodes.reduce((s, e) => s + e.estimatedDuration, 0);
  const totalWords = episodes.reduce((s, e) => s + e.wordCount, 0);

  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-text mb-1">分集规划</h2>
          <p className="text-sm text-sub">AI 已根据剧本自动生成分集规划，你可以调整标题和说明。</p>
        </div>
        <div className="flex gap-4 text-right shrink-0">
          <div>
            <div className="text-lg font-semibold text-text">{episodes.length}</div>
            <div className="text-xs text-muted">总集数</div>
          </div>
          <div>
            <div className="text-lg font-semibold text-text">{fmt(totalDuration)}</div>
            <div className="text-xs text-muted">预估总时长</div>
          </div>
          <div>
            <div className="text-lg font-semibold text-text">{(totalWords / 1000).toFixed(1)}k</div>
            <div className="text-xs text-muted">总字数</div>
          </div>
        </div>
      </div>

      <div className="space-y-2 mb-8">
        {episodes.map((ep, idx) => (
          <div
            key={ep.id}
            className="group border border-line rounded-xl p-4 bg-white hover:border-brand/30 hover:shadow-card transition-all"
          >
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-lg bg-soft flex items-center justify-center text-xs font-semibold text-sub shrink-0 mt-0.5">
                {idx + 1}
              </div>
              <div className="flex-1 min-w-0">
                {editingId === ep.id ? (
                  <div className="space-y-2">
                    <Input
                      value={ep.title}
                      onChange={(e) => update(ep.id, { title: e.target.value })}
                      className="text-sm font-medium"
                      autoFocus
                    />
                    <Textarea
                      value={ep.summary}
                      onChange={(e) => update(ep.id, { summary: e.target.value })}
                      rows={2}
                      className="text-xs"
                    />
                    <Button size="sm" onClick={() => setEditingId(null)}>
                      <Check className="w-3.5 h-3.5" />完成
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-text">{ep.title}</span>
                      <button
                        onClick={() => setEditingId(ep.id)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-muted hover:text-brand"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-xs text-sub mt-1 line-clamp-1">{ep.summary}</p>
                  </>
                )}
              </div>
              <div className="flex gap-3 text-xs text-muted shrink-0">
                <span className="flex items-center gap-1">
                  <Hash className="w-3 h-3" />{(ep.wordCount / 1000).toFixed(1)}k字
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />{fmt(ep.estimatedDuration)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <Button onClick={onNext}>
          确认分集规划 <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

// ─── Phase 3：资产审核 ─────────────────────────────────────

type AssetTabKey = "characters" | "scenes" | "props";

function AssetCard({ asset }: { asset: typeof ASSET_LIBRARY.characters[number] }) {
  const [status, setStatus] = useState<AssetStatus>(asset.status);
  const [regenerating, setRegenerating] = useState(false);

  const handleRegenerate = () => {
    setRegenerating(true);
    setTimeout(() => {
      setRegenerating(false);
      setStatus("待确认");
    }, 1500);
  };

  const statusConfig: Record<AssetStatus, {
    label: string;
    variant: "success" | "warning" | "destructive" | "secondary";
  }> = {
    "已生成": { label: "已生成", variant: "success" },
    "待确认": { label: "待确认", variant: "warning" },
    "需重生": { label: "需重生", variant: "destructive" },
    "缺失":   { label: "缺失",   variant: "secondary" },
  };

  const cfg = statusConfig[status];

  return (
    <div className="border border-line rounded-xl overflow-hidden bg-white hover:shadow-card-hover transition-all">
      {/* 预览图 */}
      <div className="aspect-[4/5] bg-soft relative overflow-hidden">
        {asset.previewUrl ? (
          <div className="w-full h-full bg-gradient-to-br from-soft to-line flex items-center justify-center">
            <span className="text-muted text-xs">{asset.name.split("·")[0].trim()}</span>
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-muted text-xs">暂无预览</span>
          </div>
        )}
        <div className="absolute top-2 left-2">
          <Badge variant={cfg.variant}>{cfg.label}</Badge>
        </div>
      </div>
      {/* 信息 */}
      <div className="p-3">
        <p className="text-sm font-medium text-text truncate">{asset.name}</p>
        <p className="text-xs text-muted mt-0.5 line-clamp-2">{asset.prompt}</p>
        <div className="mt-3 flex gap-2">
          <Button
            size="sm"
            variant="outline"
            className="flex-1 text-xs"
            onClick={handleRegenerate}
            disabled={regenerating}
          >
            {regenerating
              ? <><Loader2 className="w-3 h-3 animate-spin" />生成中</>
              : <><RefreshCw className="w-3 h-3" />重新生成</>}
          </Button>
          {status !== "已生成" && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setStatus("已生成")}
              className="text-xs"
            >
              <Check className="w-3 h-3" />确认
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

const MAX_PROMPT = 1000;

function Phase3({ onFinish }: { onFinish: () => void }) {
  const [tab, setTab] = useState<AssetTabKey>("characters");
  const [seriesPrompt, setSeriesPrompt] = useState(SERIES_PROMPT_MOCK);
  const tabLabels: Record<AssetTabKey, string> = {
    characters: "人物",
    scenes: "场景",
    props: "道具",
  };

  const allAssets = Object.values(ASSET_LIBRARY).flat();
  const pendingCount = allAssets.filter((a) => a.status !== "已生成").length;
  const promptLen = seriesPrompt.length;
  const promptOver = promptLen > MAX_PROMPT;

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-text mb-1">资产审核</h2>
          <p className="text-sm text-sub">确认剧集提示词和各类资产，确保后续生成风格一致。</p>
        </div>
        {pendingCount > 0 && (
          <Badge variant="warning">{pendingCount} 项待确认</Badge>
        )}
      </div>

      {/* ── 剧集提示词 ── */}
      <div className="mb-6 rounded-xl border border-line bg-white overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-line bg-soft">
          <div>
            <h3 className="text-sm font-semibold text-text">剧集提示词</h3>
            <p className="text-xs text-muted mt-0.5">
              用于指导所有资产生成的全局提示词，包含世界观、情节和人物特征，不超过 {MAX_PROMPT} 字。
            </p>
          </div>
          <span className={cn(
            "text-xs font-mono font-semibold tabular-nums transition-colors",
            promptOver   ? "text-danger" :
            promptLen > 900 ? "text-warn" : "text-muted"
          )}>
            {promptLen} / {MAX_PROMPT}
          </span>
        </div>
        <div className="p-4">
          <Textarea
            value={seriesPrompt}
            onChange={(e) => setSeriesPrompt(e.target.value)}
            rows={10}
            className={cn(
              "font-mono text-xs resize-none",
              promptOver && "border-danger focus-visible:ring-danger/30"
            )}
            placeholder="描述世界观、主要故事情节、核心人物特征，用于统一全剧视觉风格…"
          />
          {promptOver && (
            <p className="text-xs text-danger mt-1.5">
              已超出 {MAX_PROMPT} 字限制，请精简内容。
            </p>
          )}
        </div>
      </div>

      {/* ── 资产列表 ── */}
      <Tabs value={tab} onValueChange={(v) => setTab(v as AssetTabKey)}>
        <TabsList className="mb-4">
          {(Object.keys(tabLabels) as AssetTabKey[]).map((k) => (
            <TabsTrigger key={k} value={k}>
              {tabLabels[k]}
              <span className="ml-1.5 text-xs text-muted">{ASSET_LIBRARY[k].length}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        {(Object.keys(tabLabels) as AssetTabKey[]).map((k) => (
          <TabsContent key={k} value={k}>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {ASSET_LIBRARY[k].map((asset) => (
                <AssetCard key={asset.id} asset={asset as typeof ASSET_LIBRARY.characters[number]} />
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>

      <Separator className="my-8" />

      <div className="flex items-center justify-between">
        <p className="text-sm text-sub">
          {pendingCount > 0
            ? `还有 ${pendingCount} 个资产未确认，仍可继续初始化。`
            : "所有资产已确认，可以开始制作。"}
        </p>
        <Button onClick={onFinish} disabled={promptOver}>
          确认初始化，开始制作 <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

// ─── 主组件 ───────────────────────────────────────────────────

export default function NewProjectScreen() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>(1);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [episodes, setEpisodes] = useState<EpisodeDraft[]>(
    NEW_PROJECT_MOCK_EPISODES.map((e) => ({ ...e }))
  );

  const handleFinish = () => {
    navigate("/projects/long-princess-power-play");
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-3xl mx-auto px-4 py-10">
        {/* 标题 */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-text">新建项目</h1>
          <p className="text-sm text-sub mt-1">完成以下三步后即可开始分集制作。</p>
        </div>

        <StepIndicator current={phase} />

        {phase === 1 && (
          <Phase1
            onSubmit={() => setPhase(1.5)}
            uploadedFile={uploadedFile}
            setUploadedFile={setUploadedFile}
          />
        )}
        {phase === 1.5 && (
          <PhaseWaiting onDone={() => setPhase(2)} />
        )}
        {phase === 2 && (
          <Phase2
            episodes={episodes}
            setEpisodes={setEpisodes}
            onNext={() => setPhase(3)}
          />
        )}
        {phase === 3 && <Phase3 onFinish={handleFinish} />}
      </div>
    </div>
  );
}

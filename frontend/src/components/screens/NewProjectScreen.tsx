import { useState, useRef, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Upload, FileText, ChevronRight, Check, Loader2,
  Edit2, Clock, Hash, Sparkles, Terminal, RefreshCw, AlertTriangle, Activity,
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
import { AssetStatus } from "@/lib/data";
import type { Project } from "@/lib/data";
import { projectAPI, assetAPI, generateAPI, episodeAPI, pollTask, type ApiAsset, type ApiTaskRecord } from "@/lib/api";
import { useProjects } from "@/lib/ProjectsContext";
import { cn } from "@/lib/utils";

type Phase = 1 | 1.5 | 2 | 3;

interface EpisodeDraft {
  number: number;
  title: string;
  wordCount: number;
  estimatedDuration: number;
  summary: string;
}

const STEP_NODES = [
  { visual: 1, label: "导入剧本" },
  { visual: 2, label: "分集规划" },
  { visual: 3, label: "资产审核" },
];

function StepIndicator({ current, maxReached, onJump }: { current: Phase; maxReached: number; onJump: (phase: Phase) => void }) {
  const visualCurrent = current < 2 ? 1 : current === 2 ? 2 : 3;
  const isWaiting = current === 1.5;
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEP_NODES.map((node, idx) => {
        const isActive = visualCurrent === node.visual;
        // 已解锁：历史最高已到达过该步骤，且不是当前步骤
        const isUnlocked = maxReached >= node.visual && !isActive;
        const isDone = maxReached > node.visual;
        const canClick = isUnlocked && !isWaiting;
        const targetPhase = [1, 2, 3][idx] as Phase;
        return (
          <div key={node.visual} className="flex items-center gap-2">
            <button
              onClick={() => canClick && onJump(targetPhase)}
              disabled={!canClick}
              className={cn(
                "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all",
                isDone   && "bg-brand text-white",
                isActive && "bg-brand text-white ring-4 ring-brand/20",
                !isDone && !isActive && "bg-soft text-muted border border-line",
                canClick && "cursor-pointer hover:opacity-80 hover:ring-2 hover:ring-brand/40",
                !canClick && "cursor-default",
              )}
            >
              {isDone ? <Check className="w-3.5 h-3.5" /> : node.visual}
            </button>
            <span className={cn(
              "text-sm hidden sm:block transition-colors",
              isActive ? "font-semibold text-text" : "text-muted",
              canClick && "cursor-pointer hover:text-brand",
            )}
              onClick={() => canClick && onJump(targetPhase)}
            >
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
  projectId,
  onSubmit,
  uploadedFile,
  setUploadedFile,
}: {
  projectId: string;
  onSubmit: (taskRecordId: string) => void;
  uploadedFile: File | null;
  setUploadedFile: (f: File | null) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ episodeCount: "8", minDuration: "120", notes: "" });

  const handleFile = (file: File) => setUploadedFile(file);

  const handleSubmit = async () => {
    if (!uploadedFile) return;
    setSubmitting(true);
    setError(null);
    try {
      // 1. 上传剧本
      await projectAPI.uploadScript(projectId, uploadedFile);
      // 2. 提交解析任务
      const task = await generateAPI.parseScript(projectId, {
        target_episodes: parseInt(form.episodeCount) || 8,
        min_duration: parseInt(form.minDuration) || 120,
        parse_notes: form.notes,
      });
      setDialogOpen(false);
      onSubmit(task.record_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "提交失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-text mb-1">导入剧本</h2>
        <p className="text-sm text-sub">上传剧本文件，AI 将自动解析分集规划和资产需求。</p>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
        onClick={() => !uploadedFile && fileRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer",
          dragging ? "border-brand bg-brand-soft" : "border-line hover:border-brand/50 hover:bg-soft",
          uploadedFile && "border-brand bg-brand-soft cursor-default"
        )}
      >
        <input ref={fileRef} type="file" accept=".txt,.docx,.pdf" className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
        {uploadedFile ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-brand/10 flex items-center justify-center">
              <FileText className="w-6 h-6 text-brand" />
            </div>
            <div>
              <p className="font-medium text-text text-sm">{uploadedFile.name}</p>
              <p className="text-xs text-muted mt-0.5">{(uploadedFile.size / 1024).toFixed(1)} KB</p>
            </div>
            <button onClick={(e) => { e.stopPropagation(); setUploadedFile(null); }}
              className="text-xs text-muted hover:text-danger transition-colors">重新上传</button>
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>配置解析参数</DialogTitle>
            <DialogDescription>AI 将根据以下参数拆解剧本，通常需要 10–30 秒。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {error && (
              <div className="flex items-center gap-2 text-sm text-danger bg-danger-soft px-3 py-2 rounded-lg">
                <AlertTriangle className="w-4 h-4 shrink-0" />{error}
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-sub mb-1.5 block">目标集数</label>
                <Input type="number" value={form.episodeCount}
                  onChange={(e) => setForm({ ...form, episodeCount: e.target.value })} placeholder="8" />
              </div>
              <div>
                <label className="text-xs font-medium text-sub mb-1.5 block">每集最短时长（秒）</label>
                <Input type="number" value={form.minDuration}
                  onChange={(e) => setForm({ ...form, minDuration: e.target.value })} placeholder="120" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-sub mb-1.5 block">补充说明 / 连续性约束</label>
              <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="例如：主角全程不能摘面具；第三集之后出现伤势…" rows={4} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>取消</Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? <><Loader2 className="w-4 h-4 animate-spin" />提交中…</> : <>提交解析任务 <ChevronRight className="w-4 h-4" /></>}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Phase 1.5：等待解析 ──────────────────────────────────

function PhaseWaiting({
  taskRecordId,
  onDone,
  onRetry,
}: {
  taskRecordId: string;
  onDone: (episodes: EpisodeDraft[]) => void;
  onRetry: () => void;
}) {
  const [logs, setLogs] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const seenLogsRef = useRef<number>(0);

  // 轮询，实时追加新日志
  useEffect(() => {
    pollTask(
      taskRecordId,
      (task: ApiTaskRecord) => {
        setProgress(task.progress ?? 0);
        const incoming = task.logs ?? [];
        const newLines = incoming.slice(seenLogsRef.current);
        if (newLines.length > 0) {
          seenLogsRef.current = incoming.length;
          setLogs((prev) => [...prev, ...newLines]);
        }
      },
      2000,
      180000,
    ).then((task) => {
      // 确保最终日志全部显示
      const finalLogs = task.logs ?? [];
      if (finalLogs.length > seenLogsRef.current) {
        setLogs((prev) => [...prev, ...finalLogs.slice(seenLogsRef.current)]);
        seenLogsRef.current = finalLogs.length;
      }

      const raw = (task.result as Record<string, unknown>);
      const eps = raw?.episodes as Array<Record<string, unknown>> | undefined;
      if (eps && Array.isArray(eps)) {
        const result = eps.map((e, i) => ({
          number: (e.number as number) ?? i + 1,
          title: (e.title as string) ?? `第${i + 1}集`,
          wordCount: (e.word_count as number) ?? 0,
          estimatedDuration: (e.estimated_duration as number) ?? 120,
          summary: (e.summary as string) ?? "",
        }));
        setProgress(100);
        setFinished(true);
        // 自动跳转：1 秒倒计时
        setCountdown(1);
        const tick = setInterval(() => {
          setCountdown((c) => {
            if (c === null || c <= 1) {
              clearInterval(tick);
              onDone(result);
              return null;
            }
            return c - 1;
          });
        }, 1000);
      } else {
        setError("解析结果格式异常，请重试");
        setFinished(true);
      }
    }).catch((err) => {
      setError(err?.message ?? "解析失败");
      setFinished(true);
    });
  }, [taskRecordId]);

  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logs]);

  return (
    <div className="max-w-xl mx-auto">
      <div className="mb-6 flex items-start gap-4">
        <div className={cn(
          "w-12 h-12 rounded-xl flex items-center justify-center shrink-0 transition-colors",
          finished ? (error ? "bg-danger-soft" : "bg-brand-soft") : "bg-primary/5"
        )}>
          {finished
            ? (error ? <AlertTriangle className="w-6 h-6 text-danger" /> : <Sparkles className="w-6 h-6 text-brand" />)
            : <Loader2 className="w-6 h-6 text-primary animate-spin" />}
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text mb-1">
            {finished ? (error ? "解析失败" : "解析完成") : "AI 正在深度解析剧本"}
          </h2>
          <p className="text-sm text-sub leading-relaxed">
            {error ?? (finished
              ? "分集规划和资产清单已全部生成，点击下方按钮进入分集规划审核。"
              : "正在理解剧情结构、提取人物关系并规划分集方案，请稍候——通常需要 10–30 秒。")}
          </p>
        </div>
      </div>

      {/* 进度条 */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-muted mb-1.5">
          <span className="flex items-center gap-1">
            <Activity className="w-3 h-3" />处理进度
          </span>
          <span className="font-mono tabular-nums">{progress}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-soft overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-700",
              error ? "bg-danger" : "bg-brand"
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="rounded-xl border border-line bg-slate-950 overflow-hidden mb-6 shadow-md">
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
          <div className="flex items-center gap-1.5">
            {finished
              ? <span className={cn("text-xs font-mono", error ? "text-red-400" : "text-green-400")}>{error ? "failed" : "done"}</span>
              : <span className="flex items-center gap-1 text-xs text-yellow-400 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse inline-block" />running
                </span>}
          </div>
        </div>
        <div className="p-4 h-64 overflow-y-auto font-mono">
          {logs.length === 0 && !finished && (
            <div className="text-xs text-slate-600 italic">等待任务启动…</div>
          )}
          {logs.map((line, i) => (
            <div key={i} className={cn(
              "text-xs leading-relaxed mb-0.5",
              line.startsWith("✓") ? "text-green-400 font-semibold mt-1"
                : line.startsWith("[error]") ? "text-red-400"
                : "text-slate-400"
            )}>
              <span className="text-slate-600 mr-2 select-none tabular-nums">{String(i + 1).padStart(2, "0")}</span>
              {line}
            </div>
          ))}
          {!finished && logs.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-1">
              <span className="text-slate-600 mr-2 select-none">{String(logs.length + 1).padStart(2, "0")}</span>
              <span className="inline-block w-2 h-3.5 bg-slate-500 animate-pulse rounded-sm" />
            </div>
          )}
          <div ref={logEndRef} />
        </div>
      </div>

      <div className="flex justify-between items-center">
        <p className="text-xs text-muted">{logs.length} 条日志</p>
        {error ? (
          <Button onClick={onRetry} variant="outline">
            <RefreshCw className="w-4 h-4" />重新上传剧本
          </Button>
        ) : finished ? (
          <span className="text-sm text-brand font-medium flex items-center gap-1.5">
            <Check className="w-4 h-4" />
            {countdown !== null ? `${countdown}秒后自动进入分集规划…` : "跳转中…"}
          </span>
        ) : (
          <span className="text-sm text-muted flex items-center gap-1.5">
            <Loader2 className="w-4 h-4 animate-spin" />解析中，请稍候…
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Phase 2：分集规划 ─────────────────────────────────────

function Phase2({
  projectId,
  episodes,
  setEpisodes,
  onNext,
}: {
  projectId: string;
  episodes: EpisodeDraft[];
  setEpisodes: (eps: EpisodeDraft[]) => void;
  onNext: () => void;
}) {
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (idx: number, patch: Partial<EpisodeDraft>) => {
    setEpisodes(episodes.map((e, i) => (i === idx ? { ...e, ...patch } : e)));
  };

  const totalDuration = episodes.reduce((s, e) => s + e.estimatedDuration, 0);
  const totalWords = episodes.reduce((s, e) => s + e.wordCount, 0);
  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await projectAPI.confirmEpisodes(projectId, episodes.map((e) => ({
        number: e.number,
        title: e.title,
        summary: e.summary,
        word_count: e.wordCount,
        estimated_duration: e.estimatedDuration,
      })));
      onNext();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "确认失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-text mb-1">分集规划</h2>
          <p className="text-sm text-sub">AI 已根据剧本自动生成分集规划，你可以调整标题和说明。</p>
        </div>
        <div className="flex gap-4 text-right shrink-0">
          <div><div className="text-lg font-semibold text-text">{episodes.length}</div><div className="text-xs text-muted">总集数</div></div>
          <div><div className="text-lg font-semibold text-text">{fmt(totalDuration)}</div><div className="text-xs text-muted">预估总时长</div></div>
          <div><div className="text-lg font-semibold text-text">{(totalWords / 1000).toFixed(1)}k</div><div className="text-xs text-muted">总字数</div></div>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 text-sm text-danger bg-danger-soft px-3 py-2 rounded-lg">
          <AlertTriangle className="w-4 h-4 shrink-0" />{error}
        </div>
      )}

      <div className="space-y-2 mb-8">
        {episodes.map((ep, idx) => (
          <div key={idx} className="group border border-line rounded-xl p-4 bg-white hover:border-brand/30 hover:shadow-card transition-all">
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-lg bg-soft flex items-center justify-center text-xs font-semibold text-sub shrink-0 mt-0.5">
                {ep.number}
              </div>
              <div className="flex-1 min-w-0">
                {editingIdx === idx ? (
                  <div className="space-y-2">
                    <Input value={ep.title} onChange={(e) => update(idx, { title: e.target.value })} className="text-sm font-medium" autoFocus />
                    <Textarea value={ep.summary} onChange={(e) => update(idx, { summary: e.target.value })} rows={2} className="text-xs" />
                    <Button size="sm" onClick={() => setEditingIdx(null)}><Check className="w-3.5 h-3.5" />完成</Button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-text">{ep.title}</span>
                      <button onClick={() => setEditingIdx(idx)} className="opacity-0 group-hover:opacity-100 transition-opacity text-muted hover:text-brand">
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-xs text-sub mt-1 line-clamp-1">{ep.summary}</p>
                  </>
                )}
              </div>
              <div className="flex gap-3 text-xs text-muted shrink-0">
                <span className="flex items-center gap-1"><Hash className="w-3 h-3" />{(ep.wordCount / 1000).toFixed(1)}k字</span>
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{fmt(ep.estimatedDuration)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <Button onClick={handleConfirm} disabled={submitting}>
          {submitting ? <><Loader2 className="w-4 h-4 animate-spin" />确认中…</> : <>确认分集规划 <ChevronRight className="w-4 h-4" /></>}
        </Button>
      </div>
    </div>
  );
}

// ─── Phase 3：资产审核 ─────────────────────────────────────

const ASSET_STATUS_ZH: Record<string, AssetStatus> = {
  pending: "待确认", approved: "已生成", need_regen: "需重生", missing: "缺失",
};

function AssetCard({
  asset,
  projectId,
  onUpdate,
}: {
  asset: ApiAsset;
  projectId: string;
  onUpdate: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const status: AssetStatus = ASSET_STATUS_ZH[asset.status] ?? "缺失";

  const statusConfig: Record<AssetStatus, { label: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
    "已生成": { label: "已生成", variant: "success" },
    "待确认": { label: "待确认", variant: "warning" },
    "需重生": { label: "需重生", variant: "destructive" },
    "缺失":   { label: "缺失",   variant: "secondary" },
  };
  const cfg = statusConfig[status];

  const handleRegen = async () => {
    setLoading(true);
    try {
      await assetAPI.regen(projectId, asset.id);
      await generateAPI.assetImage(asset.id);
      onUpdate();
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await assetAPI.confirm(projectId, asset.id);
      onUpdate();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border border-line rounded-xl overflow-hidden bg-white hover:shadow-card-hover transition-all">
      <div className="aspect-[4/5] bg-soft relative overflow-hidden">
        {asset.preview_url ? (
          <img src={asset.preview_url} alt={asset.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-muted text-xs">暂无预览</span>
          </div>
        )}
        <div className="absolute top-2 left-2">
          <Badge variant={cfg.variant}>{cfg.label}</Badge>
        </div>
      </div>
      <div className="p-3">
        <p className="text-sm font-medium text-text truncate">{asset.name}</p>
        <p className="text-xs text-muted mt-0.5 line-clamp-2">{asset.prompt}</p>
        <div className="mt-3 flex gap-2">
          <Button size="sm" variant="outline" className="flex-1 text-xs" onClick={handleRegen} disabled={loading}>
            {loading ? <><Loader2 className="w-3 h-3 animate-spin" />处理中</> : <><RefreshCw className="w-3 h-3" />重新生成</>}
          </Button>
          {asset.status !== "approved" && (
            <Button size="sm" variant="secondary" onClick={handleConfirm} disabled={loading} className="text-xs">
              <Check className="w-3 h-3" />确认
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

const MAX_PROMPT = 1000;
const ASSET_TYPE_ZH: Record<string, string> = { character: "人物", scene: "场景", prop: "道具" };

function Phase3({ projectId, onFinish }: { projectId: string; onFinish: () => void }) {
  const [tab, setTab] = useState("character");
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [seriesPrompt, setSeriesPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAssets = () => {
    assetAPI.list(projectId).then(setAssets);
    projectAPI.get(projectId).then((p) => { if (p.series_prompt) setSeriesPrompt(p.series_prompt); });
  };

  useEffect(() => { loadAssets(); }, [projectId]);

  const tabs = [...new Set(assets.map((a) => a.asset_type))].filter((t) => ["character", "scene", "prop"].includes(t));
  const currentAssets = assets.filter((a) => a.asset_type === tab);
  const pendingCount = assets.filter((a) => a.status !== "approved").length;
  const promptLen = seriesPrompt.length;
  const promptOver = promptLen > MAX_PROMPT;

  const handleFinish = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await projectAPI.confirmAssets(projectId);
      onFinish();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "确认失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-text mb-1">资产审核</h2>
          <p className="text-sm text-sub">确认剧集提示词和各类资产，确保后续生成风格一致。</p>
        </div>
        {pendingCount > 0 && <Badge variant="warning">{pendingCount} 项待确认</Badge>}
      </div>

      {/* 剧集提示词 */}
      <div className="mb-6 rounded-xl border border-line bg-white overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-line bg-soft">
          <div>
            <h3 className="text-sm font-semibold text-text">剧集提示词</h3>
            <p className="text-xs text-muted mt-0.5">用于指导所有资产生成的全局提示词，不超过 {MAX_PROMPT} 字。</p>
          </div>
          <span className={cn("text-xs font-mono font-semibold tabular-nums", promptOver ? "text-danger" : promptLen > 900 ? "text-warn" : "text-muted")}>
            {promptLen} / {MAX_PROMPT}
          </span>
        </div>
        <div className="p-4">
          <Textarea value={seriesPrompt} onChange={(e) => setSeriesPrompt(e.target.value)} rows={8}
            className={cn("font-mono text-xs resize-none", promptOver && "border-danger focus-visible:ring-danger/30")}
            placeholder="描述世界观、主要故事情节、核心人物特征…" />
          {promptOver && <p className="text-xs text-danger mt-1.5">已超出 {MAX_PROMPT} 字限制。</p>}
        </div>
      </div>

      {/* 资产列表 */}
      {tabs.length > 0 ? (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="mb-4">
            {tabs.map((k) => (
              <TabsTrigger key={k} value={k}>
                {ASSET_TYPE_ZH[k] ?? k}
                <span className="ml-1.5 text-xs text-muted">{assets.filter((a) => a.asset_type === k).length}</span>
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value={tab}>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {currentAssets.map((a) => (
                <AssetCard key={a.id} asset={a} projectId={projectId} onUpdate={loadAssets} />
              ))}
            </div>
          </TabsContent>
        </Tabs>
      ) : (
        <div className="py-12 text-center text-muted text-sm">
          <Loader2 className="w-5 h-5 animate-spin mx-auto mb-3" />资产生成中，请稍候…
        </div>
      )}

      <Separator className="my-8" />

      {error && (
        <div className="mb-4 flex items-center gap-2 text-sm text-danger bg-danger-soft px-3 py-2 rounded-lg">
          <AlertTriangle className="w-4 h-4 shrink-0" />{error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-sub">
          {pendingCount > 0 ? `还有 ${pendingCount} 个资产未确认，仍可继续初始化。` : "所有资产已确认，可以开始制作。"}
        </p>
        <Button onClick={handleFinish} disabled={promptOver || submitting}>
          {submitting ? <><Loader2 className="w-4 h-4 animate-spin" />初始化中…</> : <>确认初始化，开始制作 <ChevronRight className="w-4 h-4" /></>}
        </Button>
      </div>
    </div>
  );
}

// ─── 主组件 ───────────────────────────────────────────────────

export default function NewProjectScreen({
  project,
  onProjectUpdate,
}: {
  project: Project;
  onProjectUpdate: () => void;
}) {
  const navigate = useNavigate();
  const { reload } = useProjects();

  const [phase, setPhase] = useState<Phase | null>(null); // null = 初始化中
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [taskRecordId, setTaskRecordId] = useState<string>("");
  const [episodes, setEpisodes] = useState<EpisodeDraft[]>([]);
  const [maxReached, setMaxReached] = useState(1);

  // phase 推进时同步 maxReached
  const advanceTo = (p: Phase) => {
    const visual = p < 2 ? 1 : p === 2 ? 2 : 3;
    setMaxReached((prev) => Math.max(prev, visual));
    setPhase(p);
  };

  // 异步初始化：根据 init_status + 最近任务决定从哪个阶段恢复
  useEffect(() => {
    async function resolvePhase() {
      const status = project.initStatus;

      if (status === "episodes_confirmed" || status === "assets_confirmed") {
        advanceTo(3);
        return;
      }

      if (status === "script_uploaded") {
        // 查最近的 parse_script 任务
        try {
          const tasks = await generateAPI.listTasks(project.id, "parse_script");
          const latest = tasks[0];
          if (latest) {
            if (latest.status === "running" || latest.status === "pending") {
              // 任务还在跑，继续轮询
              setTaskRecordId(latest.id);
              advanceTo(1.5);
              return;
            }
            if (latest.status === "success") {
              // 任务已完成，从 result 恢复分集数据
              const raw = latest.result as Record<string, unknown> | undefined;
              // result 只存了 count，需要从 episodes API 加载
              const eps = raw?.episodes as Array<Record<string, unknown>> | undefined;
              if (eps && Array.isArray(eps) && eps.length > 0) {
                setEpisodes(eps.map((e, i) => ({
                  number: (e.number as number) ?? i + 1,
                  title: (e.title as string) ?? `第${i + 1}集`,
                  wordCount: (e.word_count as number) ?? 0,
                  estimatedDuration: (e.estimated_duration as number) ?? 120,
                  summary: (e.summary as string) ?? "",
                })));
                advanceTo(2);
                return;
              }
              // result 里没有完整 episodes，从 episode API 加载
              const apiEps = await episodeAPI.list(project.id);
              if (apiEps.length > 0) {
                setEpisodes(apiEps.map((e) => ({
                  number: e.number,
                  title: e.title,
                  wordCount: e.word_count,
                  estimatedDuration: e.estimated_duration,
                  summary: e.summary,
                })));
                advanceTo(2);
                return;
              }
            }
          }
        } catch {
          // 查任务失败，降级到 Phase 1
        }
        advanceTo(1);
        return;
      }

      // not_started 或其他
      advanceTo(1);
    }
    resolvePhase();
  }, [project.id, project.initStatus]);

  const handleFinish = async () => {
    reload();
    onProjectUpdate();
    navigate(`/projects/${project.id}`);
  };

  // 点击已完成步骤跳转，跳到 Phase 2 时确保有分集数据
  const handleJump = async (target: Phase) => {
    if (target === 2 && episodes.length === 0) {
      try {
        const apiEps = await episodeAPI.list(project.id);
        setEpisodes(apiEps.map((e) => ({
          number: e.number,
          title: e.title,
          wordCount: e.word_count,
          estimatedDuration: e.estimated_duration,
          summary: e.summary,
        })));
      } catch { /* 跳转失败静默处理 */ }
    }
    setPhase(target);
  };

  if (phase === null) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-3xl mx-auto px-4 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-text">{project.title}</h1>
          <p className="text-sm text-sub mt-1">完成以下三步后即可开始分集制作。</p>
        </div>
        <StepIndicator current={phase} maxReached={maxReached} onJump={handleJump} />

        {phase === 1 && (
          <Phase1
            projectId={project.id}
            onSubmit={(recordId) => { setTaskRecordId(recordId); advanceTo(1.5); }}
            uploadedFile={uploadedFile}
            setUploadedFile={setUploadedFile}
          />
        )}
        {phase === 1.5 && (
          <PhaseWaiting
            taskRecordId={taskRecordId}
            onDone={(eps) => { setEpisodes(eps); advanceTo(2); }}
            onRetry={() => advanceTo(1)}
          />
        )}
        {phase === 2 && (
          <Phase2
            projectId={project.id}
            episodes={episodes}
            setEpisodes={setEpisodes}
            onNext={() => advanceTo(3)}
          />
        )}
        {phase === 3 && (
          <Phase3 projectId={project.id} onFinish={handleFinish} />
        )}
      </div>
    </div>
  );
}

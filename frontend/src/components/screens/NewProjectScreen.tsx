import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload, FileText, ChevronLeft, ChevronRight, Check, Loader2,
  Edit2, Clock, Hash, Sparkles, Terminal, RefreshCw,
  AlertTriangle, Activity, X, ZoomIn, Trash2, Play, CheckCircle2,
  MessageCircle, ImagePlus, History, RotateCcw,
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
import { AssetStatus } from "@/lib/data";
import type { Project } from "@/lib/data";
import { projectAPI, assetAPI, generateAPI, episodeAPI, pollTask, type ApiAsset, type ApiTaskRecord, type ApiEpisode } from "@/lib/api";
import AgentDialog from "@/components/AgentDialog";
import { useProjects } from "@/lib/ProjectsContext";
import { useCos } from "@/lib/CosContext";
import { cn } from "@/lib/utils";
import { Sheet } from "@/components/ui/sheet";

// ─── 类型 ─────────────────────────────────────────────────────
type Phase = 1 | 1.5 | 2 | 3;

interface EpisodeDraft {
  id?: string;
  number: number;
  title: string;
  wordCount: number;
  estimatedDuration: number;
  summary: string;
  scriptExcerpt: string;
  sourceStartLine?: number;
  sourceEndLine?: number;
  dialogueCount?: number;
  sourceIntegrity?: string;
}

// ─── 步骤指示器 ───────────────────────────────────────────────
const STEP_NODES = [
  { visual: 1, label: "上传剧本" },
  { visual: 2, label: "分集与资产" },
  { visual: 3, label: "图片确认" },
];

function StepIndicator({ current, maxReached }: { current: Phase; maxReached: number }) {
  const visualCurrent = current <= 1.5 ? 1 : current === 2 ? 2 : 3;
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEP_NODES.map((node, idx) => {
        const isActive = visualCurrent === node.visual;
        const isDone = maxReached > node.visual;
        return (
          <div key={node.visual} className="flex items-center gap-2">
            <div className={cn(
              "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold",
              isDone   && "bg-brand text-white",
              isActive && "bg-brand text-white ring-4 ring-brand/20",
              !isDone && !isActive && "bg-soft text-muted border border-line",
            )}>
              {isDone ? <Check className="w-3.5 h-3.5" /> : node.visual}
            </div>
            <span className={cn(
              "text-sm hidden sm:block",
              isActive ? "font-semibold text-text" : "text-muted",
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

// ─── Phase 1：上传剧本 ────────────────────────────────────────
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
      await projectAPI.uploadScript(projectId, uploadedFile);
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
    <div className="page-panel tech-border max-w-xl mx-auto p-6">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-text mb-1">上传剧本</h2>
        <p className="text-sm text-sub">上传剧本文件，AI 将自动解析分集规划和资产需求。</p>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
        onClick={() => !uploadedFile && fileRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer bg-panel",
          dragging ? "border-brand bg-brand-soft" : "border-line hover:border-brand/50 hover:bg-soft",
          uploadedFile && "border-brand bg-brand-soft cursor-default"
        )}
      >
        <input ref={fileRef} type="file" accept=".txt,.docx,.pdf" className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
        {uploadedFile ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-brand/10 flex items-center justify-center">
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
            <div className="w-12 h-12 rounded-2xl bg-soft flex items-center justify-center">
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

// ─── Phase 1.5：等待解析 ──────────────────────────────────────
function PhaseWaiting({
  taskRecordId,
  projectId,
  onDone,
  onRetry,
}: {
  taskRecordId: string;
  projectId: string;
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
      900000,
    ).then(async (task) => {
      const finalLogs = task.logs ?? [];
      if (finalLogs.length > seenLogsRef.current) {
        setLogs((prev) => [...prev, ...finalLogs.slice(seenLogsRef.current)]);
        seenLogsRef.current = finalLogs.length;
      }
      setProgress(100);
      setFinished(true);

      // 从 DB 加载分集数据
      let result: EpisodeDraft[] | null = null;
      const rawEps = (task.result as Record<string, unknown>)?.episodes;
      if (Array.isArray(rawEps) && rawEps.length > 0) {
        result = (rawEps as Array<Record<string, unknown>>).map((e, i) => ({
          number: (e.number as number) ?? i + 1,
          title: (e.title as string) ?? `第${i + 1}集`,
          wordCount: (e.word_count as number) ?? 0,
          estimatedDuration: (e.estimated_duration as number) ?? 120,
          summary: (e.summary as string) ?? "",
          scriptExcerpt: (e.script_excerpt as string) ?? "",
          sourceStartLine: (e.source_start_line as number) || undefined,
          sourceEndLine: (e.source_end_line as number) || undefined,
          dialogueCount: (e.dialogue_count as number) ?? undefined,
          sourceIntegrity: (e.source_integrity as string) || undefined,
        }));
      }
      if (!result) {
        try {
          const apiEps = await episodeAPI.list(projectId);
          if (apiEps.length > 0) {
            result = apiEps.map((e) => ({
              id: e.id,
              number: e.number,
              title: e.title,
              wordCount: e.word_count,
              estimatedDuration: e.estimated_duration,
              summary: e.summary,
              scriptExcerpt: e.script_excerpt,
              sourceStartLine: e.source_start_line || undefined,
              sourceEndLine: e.source_end_line || undefined,
              dialogueCount: e.dialogue_count ?? undefined,
              sourceIntegrity: e.source_integrity || undefined,
            }));
          }
        } catch { /* ignore */ }
      }
      if (result && result.length > 0) {
        setCountdown(1);
        const tick = setInterval(() => {
          setCountdown((c) => {
            if (c === null || c <= 1) { clearInterval(tick); onDone(result!); return null; }
            return c - 1;
          });
        }, 1000);
      } else {
        setError("解析结果格式异常，请重试");
      }
    }).catch((err) => {
      setError(err?.message ?? "解析失败");
      setFinished(true);
    });
  }, [taskRecordId, projectId]);

  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logs]);

  return (
    <div className="page-panel tech-border max-w-xl mx-auto p-6">
      <div className="mb-6 flex items-start gap-4">
        <div className={cn(
          "w-12 h-12 rounded-xl flex items-center justify-center shrink-0",
          finished ? (error ? "bg-danger-soft" : "bg-brand-soft") : "bg-primary/5"
        )}>
          {finished
            ? (error ? <AlertTriangle className="w-6 h-6 text-danger" /> : <Sparkles className="w-6 h-6 text-brand" />)
            : <Loader2 className="w-6 h-6 text-brand animate-spin" />}
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text mb-1">
            {finished ? (error ? "解析失败" : "解析完成") : "AI 正在深度解析剧本"}
          </h2>
          <p className="text-sm text-sub leading-relaxed">
            {error ?? (finished
              ? "分集规划和资产清单已全部生成，即将进入确认步骤。"
              : "正在理解剧情结构、提取人物关系并规划分集方案，长剧本或多集数项目可能需要数分钟。")}
          </p>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-xs text-muted mb-1.5">
          <span className="flex items-center gap-1"><Activity className="w-3 h-3" />处理进度</span>
          <span className="font-mono tabular-nums">{progress}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-soft overflow-hidden">
          <div className={cn("h-full rounded-full transition-all duration-700", error ? "bg-danger" : "bg-brand")}
            style={{ width: `${progress}%` }} />
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
          {logs.length === 0 && !finished && <div className="text-xs text-slate-600 italic">等待任务启动…</div>}
          {logs.map((line, i) => (
            <div key={i} className={cn("text-xs leading-relaxed mb-0.5",
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
          <Button onClick={onRetry} variant="outline"><RefreshCw className="w-4 h-4" />重新上传剧本</Button>
        ) : finished ? (
          <span className="text-sm text-brand font-medium flex items-center gap-1.5">
            <Check className="w-4 h-4" />
            {countdown !== null ? `${countdown}秒后自动进入下一步…` : "跳转中…"}
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

// ─── Phase 2：分集 + 资产确认 ─────────────────────────────────
const ASSET_TYPE_ZH: Record<string, string> = { character: "人物", scene: "场景", prop: "道具" };

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
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [assetTab, setAssetTab] = useState("character");
  const [agentOpen, setAgentOpen] = useState(false);
  const [apiEpisodes, setApiEpisodes] = useState<ApiEpisode[]>([]);
  const [sheetEp, setSheetEp] = useState<EpisodeDraft | null>(null);
  const [editingAssetId, setEditingAssetId] = useState<string | null>(null);
  const [assetEdits, setAssetEdits] = useState<Record<string, {
    name: string;
    prompt: string;
    voice_profile: string;
    character_name: string;
    asset_package: string;
    face_identity: string;
    scene_scope: string;
    appearance_stage: string;
    view_requirements: string;
  }>>({});
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const update = (idx: number, patch: Partial<EpisodeDraft>) => {
    setEpisodes(episodes.map((e, i) => (i === idx ? { ...e, ...patch } : e)));
  };

  const loadData = async () => {
    try {
      const [epList, assetList] = await Promise.all([
        episodeAPI.list(projectId),
        assetAPI.list(projectId),
      ]);
      setApiEpisodes(epList);
      // 同步 EpisodeDraft 列表（以 DB 为准）
      setEpisodes(epList.map((e) => ({
        id: e.id,
        number: e.number,
        title: e.title,
        wordCount: e.word_count,
        estimatedDuration: e.estimated_duration,
        summary: e.summary,
        scriptExcerpt: e.script_excerpt,
        sourceStartLine: e.source_start_line || undefined,
        sourceEndLine: e.source_end_line || undefined,
        dialogueCount: e.dialogue_count ?? undefined,
        sourceIntegrity: e.source_integrity || undefined,
      })));
      setAssets(assetList);
    } catch { /* ignore */ }
  };

  // 进入时加载，之后每 3s 轮询
  useEffect(() => {
    loadData();
    const startPoll = () => {
      pollTimerRef.current = setTimeout(async () => {
        await loadData();
        startPoll();
      }, 3000);
    };
    startPoll();
    return () => { if (pollTimerRef.current) clearTimeout(pollTimerRef.current); };
  }, [projectId]);

  const totalDuration = episodes.reduce((s, e) => s + e.estimatedDuration, 0);
  const totalDialogues = episodes.reduce((s, e) => s + (e.dialogueCount ?? 0), 0);
  const originalEpisodes = episodes.filter((e) => e.sourceIntegrity === "original").length;
  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
  const lineRange = (ep: EpisodeDraft) =>
    ep.sourceStartLine && ep.sourceEndLine ? `L${ep.sourceStartLine}-${ep.sourceEndLine}` : "未索引";

  const assetTabs = [...new Set(assets.map((a) => a.asset_type))].filter((t) =>
    ["character", "scene", "prop"].includes(t)
  );
  const currentAssets = assets.filter((a) => a.asset_type === assetTab);

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await projectAPI.confirmEpisodes(projectId, episodes.map((e) => ({
        id: e.id,
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
    <div className="page-panel tech-border max-w-6xl mx-auto p-5 sm:p-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between mb-6">
        <div>
          <p className="section-title mb-2">Plan Review</p>
          <h2 className="text-xl font-semibold text-text mb-1">分集与资产确认</h2>
          <p className="text-sm text-sub">确认 AI 生成的分集规划和资产清单。可 inline 编辑，或点击右下角「AI 助手」通过对话调整。</p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 xl:w-[520px]">
          <div className="mini-stat"><div className="text-lg font-semibold text-text">{episodes.length}</div><div className="text-xs text-muted">总集数</div></div>
          <div className="mini-stat"><div className="text-lg font-semibold text-text">{fmt(totalDuration)}</div><div className="text-xs text-muted">预估时长</div></div>
          <div className="mini-stat"><div className="text-lg font-semibold text-text">{totalDialogues}</div><div className="text-xs text-muted">对白行</div></div>
          <div className="mini-stat"><div className="text-lg font-semibold text-text">{originalEpisodes}/{episodes.length || 0}</div><div className="text-xs text-muted">原文回填</div></div>
          <div className="mini-stat"><div className="text-lg font-semibold text-text">{assets.length}</div><div className="text-xs text-muted">资产数</div></div>
        </div>
      </div>

      {error && (
        <div className="status-banner status-banner-danger mb-4 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />{error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        {/* 左侧：分集列表 */}
        <div className="rounded-2xl border border-line bg-elev p-3">
          <div className="mb-3 flex items-center justify-between px-1">
            <h3 className="text-sm font-semibold text-text">分集规划</h3>
            <span className="text-xs text-muted">{episodes.length} 集</span>
          </div>
          <div className="max-h-[620px] space-y-2 overflow-y-auto pr-1">
            {episodes.map((ep, idx) => (
              <div key={idx} className="group media-card p-3 hover:border-brand/30">
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-lg bg-soft flex items-center justify-center text-xs font-semibold text-sub shrink-0 mt-0.5">
                    {ep.number}
                  </div>
                  <div className="flex-1 min-w-0">
                    {editingIdx === idx ? (
                      <div className="space-y-1.5">
                        <Input value={ep.title} onChange={(e) => update(idx, { title: e.target.value })} className="text-sm" autoFocus />
                        <Textarea value={ep.summary} onChange={(e) => update(idx, { summary: e.target.value })} rows={2} className="text-xs" />
                        <Button size="sm" onClick={() => setEditingIdx(null)}><Check className="w-3.5 h-3.5" />完成</Button>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm text-text truncate">{ep.title}</span>
                          <button onClick={() => setEditingIdx(idx)} className="opacity-0 group-hover:opacity-100 transition-opacity text-muted hover:text-brand shrink-0">
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        <p className="text-xs text-sub mt-0.5 line-clamp-1">{ep.summary}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                          <span className="rounded bg-soft px-1.5 py-0.5">原文 {lineRange(ep)}</span>
                          <span className="rounded bg-soft px-1.5 py-0.5">对白 {ep.dialogueCount ?? 0}</span>
                          {ep.sourceIntegrity && (
                            <span className={cn(
                              "rounded px-1.5 py-0.5",
                              ep.sourceIntegrity === "original" ? "bg-brand-soft text-brand" : "bg-warn/10 text-warn"
                            )}>
                              {ep.sourceIntegrity === "original" ? "原文完整" : ep.sourceIntegrity}
                            </span>
                          )}
                        </div>
                        <div
                          className="mt-1.5 text-xs text-muted bg-soft rounded px-2 py-1.5 line-clamp-3 cursor-pointer hover:bg-line/50 transition-colors whitespace-pre-wrap"
                          onClick={() => setSheetEp(ep)}
                        >
                          {ep.scriptExcerpt || "（暂无剧本原文，重新解析后可见）"}
                        </div>
                      </>
                    )}
                  </div>
                  <div className="flex gap-2 text-xs text-muted shrink-0">
                    <span className="flex items-center gap-0.5"><Hash className="w-3 h-3" />{(ep.wordCount / 1000).toFixed(1)}k</span>
                    <span className="flex items-center gap-0.5"><Clock className="w-3 h-3" />{fmt(ep.estimatedDuration)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 右侧：资产列表 */}
        <div className="rounded-2xl border border-line bg-elev p-3">
          <div className="mb-3 flex items-center justify-between px-1">
            <h3 className="text-sm font-semibold text-text">资产清单</h3>
            <span className="text-xs text-muted">{currentAssets.length} 项</span>
          </div>
          {assets.length === 0 ? (
            <div className="empty-state-panel py-8">
              <Loader2 className="w-4 h-4 animate-spin mx-auto mb-2" />资产加载中…
            </div>
          ) : (
            <Tabs value={assetTab} onValueChange={setAssetTab}>
              <TabsList className="mb-3">
                {assetTabs.map((k) => (
                  <TabsTrigger key={k} value={k}>
                    {ASSET_TYPE_ZH[k] ?? k}
                    <span className="ml-1.5 text-xs text-muted">{assets.filter((a) => a.asset_type === k).length}</span>
                  </TabsTrigger>
                ))}
              </TabsList>
              <TabsContent value={assetTab}>
                <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
                  {currentAssets.map((a) => {
                    const isEditing = editingAssetId === a.id;
                    const draft = assetEdits[a.id] ?? {
                      name: a.name,
                      prompt: a.prompt ?? "",
                      voice_profile: a.voice_profile ?? "",
                      character_name: a.character_name ?? "",
                      asset_package: a.asset_package ?? a.character_name ?? "",
                      face_identity: a.face_identity ?? "",
                      scene_scope: a.scene_scope ?? "",
                      appearance_stage: a.appearance_stage ?? "",
                      view_requirements: a.view_requirements ?? "",
                    };
                    return (
                      <div key={a.id} className="group media-card p-3 hover:border-brand/30">
                        {isEditing ? (
                          <div className="space-y-2">
                            <Input
                              value={draft.name}
                              onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, name: e.target.value } }))}
                              className="text-sm"
                              autoFocus
                              placeholder="资产名称"
                            />
                            <Textarea
                              value={draft.prompt}
                              onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, prompt: e.target.value } }))}
                              rows={4}
                              className="text-xs"
                              placeholder="Seedream 生成提示词"
                            />
                            {a.asset_type === "character" && (
                              <>
                                <div className="grid grid-cols-2 gap-2">
                                  <Input
                                    value={draft.character_name}
                                    onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, character_name: e.target.value } }))}
                                    className="text-xs"
                                    placeholder="角色本名"
                                  />
                                  <Input
                                    value={draft.asset_package}
                                    onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, asset_package: e.target.value } }))}
                                    className="text-xs"
                                    placeholder="人物资产包"
                                  />
                                </div>
                                <Textarea
                                  value={draft.face_identity}
                                  onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, face_identity: e.target.value } }))}
                                  rows={2}
                                  className="text-xs"
                                  placeholder="共享面部基准：同一人物资产包内保持同一脸型、骨相、五官比例"
                                />
                                <div className="grid grid-cols-2 gap-2">
                                  <Input
                                    value={draft.appearance_stage}
                                    onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, appearance_stage: e.target.value } }))}
                                    className="text-xs"
                                    placeholder="剧情/造型阶段"
                                  />
                                  <Input
                                    value={draft.scene_scope}
                                    onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, scene_scope: e.target.value } }))}
                                    className="text-xs"
                                    placeholder="适用场景"
                                  />
                                </div>
                                <Input
                                  value={draft.view_requirements}
                                  onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, view_requirements: e.target.value } }))}
                                  className="text-xs"
                                  placeholder="视角要求：面部特写、全身形象、侧面视角"
                                />
                                <Textarea
                                  value={draft.voice_profile}
                                  onChange={(e) => setAssetEdits((prev) => ({ ...prev, [a.id]: { ...draft, voice_profile: e.target.value } }))}
                                  rows={3}
                                  className="text-xs"
                                  placeholder="角色固定音色：年龄感、音色质感、语速、情绪基线、禁止变化项"
                                />
                              </>
                            )}
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                onClick={async () => {
                                  await assetAPI.update(projectId, a.id, {
                                    name: draft.name,
                                    prompt: draft.prompt,
                                    voice_profile: draft.voice_profile,
                                    character_name: draft.character_name,
                                    asset_package: draft.asset_package,
                                    face_identity: draft.face_identity,
                                    scene_scope: draft.scene_scope,
                                    appearance_stage: draft.appearance_stage,
                                    view_requirements: draft.view_requirements,
                                  });
                                  setEditingAssetId(null);
                                  setAssetEdits((prev) => { const n = { ...prev }; delete n[a.id]; return n; });
                                  loadData();
                                }}
                              >
                                <Check className="w-3.5 h-3.5" />保存
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setEditingAssetId(null);
                                  setAssetEdits((prev) => { const n = { ...prev }; delete n[a.id]; return n; });
                                }}
                              >
                                取消
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <div className="flex items-center gap-1">
                              <p className="text-sm font-medium text-text truncate">{a.name}</p>
                              <button
                                onClick={() => {
                                  setAssetEdits((prev) => ({
                                    ...prev,
                                    [a.id]: {
                                      name: a.name,
                                      prompt: a.prompt ?? "",
                                      voice_profile: a.voice_profile ?? "",
                                      character_name: a.character_name ?? "",
                                      asset_package: a.asset_package ?? a.character_name ?? "",
                                      face_identity: a.face_identity ?? "",
                                      scene_scope: a.scene_scope ?? "",
                                      appearance_stage: a.appearance_stage ?? "",
                                      view_requirements: a.view_requirements ?? "",
                                    },
                                  }));
                                  setEditingAssetId(a.id);
                                }}
                                className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-muted hover:text-brand rounded shrink-0"
                              >
                                <Edit2 className="w-3 h-3" />
                              </button>
                              <button
                                onClick={async () => {
                                  await assetAPI.delete(projectId, a.id);
                                  loadData();
                                }}
                                className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-muted hover:text-danger rounded shrink-0"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                            <p className="text-xs text-muted mt-1 line-clamp-3 leading-relaxed">{a.prompt || "（暂无提示词）"}</p>
                            {a.asset_type === "character" && (
                              <div className="mt-1 flex flex-wrap gap-1">
                                {a.character_name && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">角色：{a.character_name}</span>}
                                {(a.asset_package || a.character_name) && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">资产包：{a.asset_package || a.character_name}</span>}
                                {a.scene_scope && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">场景：{a.scene_scope}</span>}
                                {a.appearance_stage && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">阶段：{a.appearance_stage}</span>}
                                {(a.view_requirements || "面部特写、全身形象、侧面视角") && (
                                  <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">
                                    视角：{a.view_requirements || "面部特写、全身形象、侧面视角"}
                                  </span>
                                )}
                              </div>
                            )}
                            {a.asset_type === "character" && a.face_identity && (
                              <p className="text-xs text-sub mt-1 line-clamp-2 leading-relaxed">面部基准：{a.face_identity}</p>
                            )}
                            {a.asset_type === "character" && a.voice_profile && (
                              <p className="text-xs text-sub mt-1 line-clamp-2 leading-relaxed">音色：{a.voice_profile}</p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>

      <div className="sticky-action-bar">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button variant="outline" onClick={() => setAgentOpen(true)} className="flex items-center gap-1.5">
            <MessageCircle className="w-4 h-4" />返工修改
          </Button>
          <p className="text-sm text-sub">确认后进入图片确认阶段，不会自动生成图片；需手动生成全部或单个资产。</p>
        </div>
        <Button onClick={handleConfirm} disabled={submitting || episodes.length === 0}>
          {submitting ? <><Loader2 className="w-4 h-4 animate-spin" />确认中…</> : <>确认分集与资产 <ChevronRight className="w-4 h-4" /></>}
        </Button>
      </div>

      <AgentDialog
        open={agentOpen}
        onOpenChange={setAgentOpen}
        targetType="project"
        targetId={projectId}
        projectId={projectId}
        title="AI 助手 · 调整分集与资产"
        onTaskStarted={loadData}
        initialPrompt={`当前共 ${episodes.length} 集，${assets.length} 个资产（${assets.filter(a => a.asset_type === "character").length} 人物 / ${assets.filter(a => a.asset_type === "scene").length} 场景 / ${assets.filter(a => a.asset_type === "prop").length} 道具）。告诉我你想怎么调整。`}
      />

      <Sheet
        open={sheetEp !== null}
        onClose={() => setSheetEp(null)}
        title={sheetEp ? `第 ${sheetEp.number} 集《${sheetEp.title}》· 原始剧本` : ""}
        width="w-[560px]"
      >
        {sheetEp && (
          <pre className="text-xs text-text leading-relaxed whitespace-pre-wrap font-sans">
            {sheetEp.scriptExcerpt}
          </pre>
        )}
      </Sheet>
    </div>
  );
}

// ─── Phase 3：图片生成 + 确认 ─────────────────────────────────
const ASSET_STATUS_ZH: Record<string, AssetStatus> = {
  pending: "待确认", approved: "已生成", need_regen: "需重生", missing: "缺失",
  generating: "生成中", queued: "排队中",
};

const CHARACTER_VIEW_META = [
  { key: "face", label: "面部" },
  { key: "full_body", label: "全身" },
  { key: "side", label: "侧面" },
] as const;

type AssetFilter = "all" | "need_generate" | "generating" | "pending_confirm" | "approved";
type AssetGroup = { key: string; label: string; assets: ApiAsset[] };
type AssetLightboxItem = { url: string; label: string };

const ASSET_FILTERS: Array<{ key: AssetFilter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "need_generate", label: "待生成" },
  { key: "generating", label: "生成中" },
  { key: "pending_confirm", label: "待确认" },
  { key: "approved", label: "已确认" },
];

const isAssetImageReady = (asset: ApiAsset) => {
  if (asset.asset_type !== "character") return Boolean(asset.preview_url);
  return CHARACTER_VIEW_META.every((view) => Boolean(asset.view_urls?.[view.key]));
};

const getAssetPreviewUrl = (asset: ApiAsset) => {
  if (asset.asset_type !== "character") return asset.preview_url;
  return asset.view_urls?.full_body || asset.view_urls?.face || asset.view_urls?.side || asset.preview_url;
};

const getAssetMainPreviewUrl = (asset: ApiAsset) => {
  if (asset.asset_type !== "character") return getAssetPreviewUrl(asset);
  return asset.view_urls?.face || asset.preview_url || asset.view_urls?.full_body || asset.view_urls?.side;
};

const isAssetRunning = (asset: ApiAsset) => asset.status === "generating" || asset.status === "queued";

const matchesAssetFilter = (asset: ApiAsset, filter: AssetFilter) => {
  if (filter === "all") return true;
  if (filter === "need_generate") return !isAssetImageReady(asset) && !isAssetRunning(asset);
  if (filter === "generating") return isAssetRunning(asset);
  if (filter === "pending_confirm") return isAssetImageReady(asset) && asset.status !== "approved";
  if (filter === "approved") return asset.status === "approved";
  return true;
};

const baseAssetName = (name: string) => {
  const [base] = name.split(/[·\-—_｜|]/);
  return (base || name).trim();
};

const getAssetGroupKey = (asset: ApiAsset) => {
  if (asset.asset_type === "character") return asset.asset_package || asset.character_name || baseAssetName(asset.name);
  return baseAssetName(asset.name);
};

const getAssetGroupLabel = (asset: ApiAsset) => getAssetGroupKey(asset) || asset.name;

const buildAssetGroups = (list: ApiAsset[]) => Object.values(
  list.reduce<Record<string, AssetGroup>>((acc, asset) => {
    const key = getAssetGroupKey(asset);
    if (!acc[key]) acc[key] = { key, label: getAssetGroupLabel(asset), assets: [] };
    acc[key].assets.push(asset);
    return acc;
  }, {})
);

const getGroupPreviewAsset = (group: AssetGroup) =>
  group.assets.find((asset) => asset.asset_type === "character" && Boolean(asset.view_urls?.face)) ||
  group.assets.find((asset) => Boolean(getAssetMainPreviewUrl(asset))) ||
  group.assets.find(isAssetImageReady) ||
  group.assets[0];

const getAssetGroupStats = (group: AssetGroup) => {
  const generated = group.assets.filter(isAssetImageReady).length;
  const running = group.assets.filter(isAssetRunning).length;
  const approved = group.assets.filter((asset) => asset.status === "approved").length;
  return {
    generated,
    running,
    approved,
    total: group.assets.length,
    pendingGenerate: group.assets.length - generated,
    readyToConfirm: group.assets.filter((asset) => isAssetImageReady(asset) && asset.status !== "approved").length,
  };
};

const getAssetImageSlotCount = (asset: ApiAsset) => {
  if (asset.asset_type === "character") return CHARACTER_VIEW_META.length;
  return 1;
};

const isSingleImageAssetGroup = (group: AssetGroup) =>
  group.assets.length === 1 && getAssetImageSlotCount(group.assets[0]) === 1;

const getAssetLightboxItems = (asset: ApiAsset): AssetLightboxItem[] => {
  if (asset.asset_type === "character") {
    return CHARACTER_VIEW_META.flatMap((view) => {
      const url = asset.view_urls?.[view.key];
      return url ? [{ url, label: `${asset.name} · ${view.label}` }] : [];
    });
  }
  return asset.preview_url ? [{ url: asset.preview_url, label: asset.name }] : [];
};

const getAssetGroupLightboxItems = (group: AssetGroup): AssetLightboxItem[] =>
  group.assets.flatMap(getAssetLightboxItems);

function AssetCard({
  asset,
  projectId,
  onUpdate,
  layout = "grid",
  onViewPrompt,
  lightboxItems,
}: {
  asset: ApiAsset;
  projectId: string;
  onUpdate: () => void;
  layout?: "grid" | "stage";
  onViewPrompt?: (asset: ApiAsset) => void;
  lightboxItems?: AssetLightboxItem[];
}) {
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [agentOpen, setAgentOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [restoringVersion, setRestoringVersion] = useState<string | null>(null);
  const [activeLightboxItems, setActiveLightboxItems] = useState<AssetLightboxItem[]>([]);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const { cosUrl } = useCos();

  const isQueued = asset.status === "queued";
  const isGenerating = asset.status === "generating" || isQueued;
  const isReady = isAssetImageReady(asset);
  const previewUrl = getAssetPreviewUrl(asset);
  const hasCharacterViews = CHARACTER_VIEW_META.some((view) => Boolean(asset.view_urls?.[view.key]));
  const status: AssetStatus = ASSET_STATUS_ZH[asset.status] ?? "缺失";
  const promptPreview = asset.prompt || "（暂无提示词）";
  const assetVersions = asset.versions ?? [];
  const localLightboxItems = getAssetLightboxItems(asset);
  const sharedLightboxItems = lightboxItems?.length ? lightboxItems : localLightboxItems;
  const currentLightboxItem = lightboxIndex === null ? null : activeLightboxItems[lightboxIndex];
  const canPageLightbox = activeLightboxItems.length > 1;

  const statusConfig: Record<AssetStatus, { label: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
    "已生成": { label: "已生成", variant: "success" },
    "待确认": { label: "待确认", variant: "warning" },
    "需重生": { label: "需重生", variant: "destructive" },
    "缺失":   { label: "缺失",   variant: "secondary" },
    "生成中": { label: "生成中", variant: "secondary" },
    "排队中": { label: "排队中", variant: "secondary" },
  };
  const cfg = statusConfig[status];

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await assetAPI.confirm(projectId, asset.id);
      onUpdate();
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await generateAPI.assetImage(asset.id);
      onUpdate();
    } finally {
      setGenerating(false);
    }
  };

  const handleRestoreVersion = async (version: string) => {
    setRestoringVersion(version);
    try {
      await assetAPI.restoreVersion(projectId, asset.id, version);
      onUpdate();
    } finally {
      setRestoringVersion(null);
    }
  };

  const openLightbox = (url: string, label: string, source: AssetLightboxItem[] = sharedLightboxItems) => {
    const items = source.length > 0 ? source : [{ url, label }];
    const index = items.findIndex((item) => item.url === url);
    setActiveLightboxItems(items);
    setLightboxIndex(index >= 0 ? index : 0);
  };

  const closeLightbox = () => {
    setLightboxIndex(null);
    setActiveLightboxItems([]);
  };

  const pageLightbox = (delta: number) => {
    setLightboxIndex((current) => {
      if (current === null || activeLightboxItems.length === 0) return current;
      return (current + delta + activeLightboxItems.length) % activeLightboxItems.length;
    });
  };

  useEffect(() => {
    if (!currentLightboxItem) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowLeft") pageLightbox(-1);
      if (e.key === "ArrowRight") pageLightbox(1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentLightboxItem, activeLightboxItems.length]);

  const viewStrip = (
    <div className={cn("grid grid-cols-3 gap-2", layout === "grid" ? "h-full gap-px bg-line" : "h-28 sm:h-32")}>
      {CHARACTER_VIEW_META.map((view) => {
        const url = asset.view_urls?.[view.key];
        return (
          <button
            key={view.key}
            type="button"
            className={cn(
              "relative overflow-hidden bg-soft border border-line group/view",
              layout === "grid" ? "border-0 rounded-none" : "rounded-lg"
            )}
            onClick={() => url ? openLightbox(url, `${asset.name} · ${view.label}`) : handleGenerate()}
            title={url ? `查看${view.label}图` : `生成${view.label}图`}
          >
            {url ? (
              <img src={cosUrl(url)} alt={`${asset.name}-${view.label}`} className="w-full h-full object-contain" />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center gap-1 text-muted">
                <ImagePlus className="w-4 h-4" />
                <span className="text-[11px]">生成</span>
              </div>
            )}
            <span className="absolute left-1 bottom-1 rounded bg-black/55 px-1.5 py-0.5 text-[11px] text-white">
              {view.label}
            </span>
            {url && (
              <ZoomIn className="absolute right-1 bottom-1 w-3.5 h-3.5 text-white opacity-0 group-hover/view:opacity-100 transition-opacity" />
            )}
          </button>
        );
      })}
    </div>
  );

  const singlePreview = (
    <div className="w-full h-full bg-soft relative overflow-hidden group">
      {previewUrl ? (
        <>
          <img
            src={cosUrl(previewUrl)}
            alt={asset.name}
            className="w-full h-full object-contain cursor-zoom-in"
            onClick={() => openLightbox(previewUrl, asset.name)}
          />
          <div
            className="absolute bottom-2 right-2 bg-black/50 rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity cursor-zoom-in"
            onClick={() => openLightbox(previewUrl, asset.name)}
          >
            <ZoomIn className="w-3.5 h-3.5 text-white" />
          </div>
        </>
      ) : (
        <div
          className="w-full h-full flex flex-col items-center justify-center gap-2 cursor-pointer hover:bg-line/40 transition-colors"
          onClick={handleGenerate}
          title="点击生成资产图"
        >
          {generating ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin text-brand" />
              <span className="text-muted text-xs">提交中…</span>
            </>
          ) : (
            <>
              <ImagePlus className="w-5 h-5 text-muted" />
              <span className="text-muted text-xs">点击生成</span>
            </>
          )}
        </div>
      )}
    </div>
  );

  const actions = (
    <div className="flex gap-1.5 justify-end">
      <Button
        size="sm" variant="outline" className="w-8 h-8 p-0"
        onClick={handleGenerate}
        disabled={isGenerating || generating}
        title={isReady ? "重新生成资产图" : "生成资产图"}
      >
        {generating || isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImagePlus className="w-3.5 h-3.5" />}
      </Button>
      <Button
        size="sm" variant="outline" className="w-8 h-8 p-0"
        onClick={() => onViewPrompt?.(asset)}
        title="查看完整提示词"
      >
        <FileText className="w-3.5 h-3.5" />
      </Button>
      <Button
        size="sm" variant="outline" className="w-8 h-8 p-0"
        onClick={() => setAgentOpen(true)}
        disabled={isGenerating}
        title={isGenerating ? (isQueued ? "排队中" : "生成中") : "AI 修改"}
      >
        {isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <MessageCircle className="w-3.5 h-3.5" />}
      </Button>
      <Button
        size="sm" variant="outline" className="w-8 h-8 p-0"
        onClick={() => setHistoryOpen(true)}
        disabled={assetVersions.length === 0}
        title={assetVersions.length === 0 ? "暂无历史版本" : "历史版本"}
      >
        <History className="w-3.5 h-3.5" />
      </Button>
      {asset.status !== "approved" && !isGenerating && isReady && (
        <Button
          size="sm" variant="secondary" className="w-8 h-8 p-0"
          onClick={handleConfirm} disabled={loading}
          title="确认资产"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
        </Button>
      )}
    </div>
  );

  const historyDialog = (
    <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>{asset.name} · 历史版本回选</DialogTitle>
          <DialogDescription>对比多次生成结果，选择一个历史版本回写到当前资产。</DialogDescription>
        </DialogHeader>
        {assetVersions.length > 0 ? (
          <div className="grid max-h-[70vh] grid-cols-1 gap-3 overflow-y-auto pr-1 md:grid-cols-2 lg:grid-cols-3">
            {assetVersions.slice().reverse().map((item) => {
              const isCurrent = item.url === asset.preview_url || Object.values(asset.view_urls ?? {}).includes(item.url);
              const versionLightboxItems = assetVersions
                .filter((version) => Boolean(version.url))
                .map((version) => ({
                  url: version.url,
                  label: `${asset.name} · ${version.version}${version.note ? ` · ${version.note}` : ""}`,
                }));
              return (
                <div key={item.version} className="rounded-xl border border-line bg-panel p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-text">{item.version}</p>
                      <p className="text-xs text-muted">
                        {item.note || item.view_type || "资产图"} · {item.created_at ? new Date(item.created_at).toLocaleString() : "未知时间"}
                      </p>
                    </div>
                    {isCurrent && <Badge variant="success">当前</Badge>}
                  </div>
                  <button
                    type="button"
                    className="h-44 w-full overflow-hidden rounded-lg border border-line bg-soft"
                    onClick={() => openLightbox(item.url, `${asset.name} · ${item.version}`, versionLightboxItems)}
                    title="点击放大预览"
                  >
                    <img src={cosUrl(item.url)} alt={`${asset.name}-${item.version}`} className="h-full w-full object-contain" />
                  </button>
                  <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-sub">{item.prompt || "（暂无提示词）"}</p>
                  <div className="mt-3 flex justify-end">
                    <Button
                      size="sm"
                      variant={isCurrent ? "secondary" : "outline"}
                      onClick={() => handleRestoreVersion(item.version)}
                      disabled={isCurrent || restoringVersion === item.version}
                    >
                      {restoringVersion === item.version
                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />回选中…</>
                        : <><RotateCcw className="w-3.5 h-3.5" />回选此版本</>
                      }
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state-panel">暂无历史版本。重新生成后会自动记录。</div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => setHistoryOpen(false)}>关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const lightboxOverlay = currentLightboxItem && (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-6" onClick={closeLightbox}>
      <button className="absolute right-4 top-4 text-white/70 transition-colors hover:text-white" onClick={closeLightbox}>
        <X className="w-7 h-7" />
      </button>
      {canPageLightbox && (
        <button
          type="button"
          className="absolute left-4 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/15 text-white backdrop-blur transition-colors hover:bg-white/25"
          onClick={(e) => {
            e.stopPropagation();
            pageLightbox(-1);
          }}
          title="上一张"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>
      )}
      <div className="flex max-h-[92vh] max-w-[92vw] flex-col items-center gap-3" onClick={(e) => e.stopPropagation()}>
        <img
          src={cosUrl(currentLightboxItem.url)}
          alt={currentLightboxItem.label}
          className="max-h-[86vh] max-w-[92vw] rounded-lg object-contain shadow-2xl"
        />
        <div className="rounded-full bg-black/45 px-3 py-1 text-xs text-white/85">
          {currentLightboxItem.label}
          {canPageLightbox && lightboxIndex !== null && (
            <span className="ml-2 text-white/60">{lightboxIndex + 1} / {activeLightboxItems.length}</span>
          )}
        </div>
      </div>
      {canPageLightbox && (
        <button
          type="button"
          className="absolute right-4 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/15 text-white backdrop-blur transition-colors hover:bg-white/25"
          onClick={(e) => {
            e.stopPropagation();
            pageLightbox(1);
          }}
          title="下一张"
        >
          <ChevronRight className="w-6 h-6" />
        </button>
      )}
    </div>
  );

  if (layout === "stage") {
    return (
      <>
        {lightboxOverlay}
        <div className="border border-line rounded-xl bg-panel p-3 hover:shadow-card-hover transition-all">
          <div className="flex flex-col lg:flex-row gap-4">
            <div className="lg:w-[280px] shrink-0">
              {isGenerating ? (
                <div className="h-28 sm:h-32 rounded-lg bg-soft flex flex-col items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin text-brand" />
                  <span className="text-xs text-muted">{isQueued ? "排队等待…" : "生成中…"}</span>
                </div>
              ) : asset.asset_type === "character" ? viewStrip : (
                <div className="h-28 sm:h-32 rounded-lg overflow-hidden border border-line">{singlePreview}</div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-text truncate">{asset.appearance_stage || asset.name}</p>
                <Badge variant={cfg.variant}>{cfg.label}</Badge>
                {isReady && asset.status !== "approved" && <Badge variant="warning">待确认</Badge>}
              </div>
              <p className="text-xs text-muted mt-1 line-clamp-2">{promptPreview}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {asset.scene_scope && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">场景：{asset.scene_scope}</span>}
                {asset.face_identity && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">继承面部基准</span>}
                {isReady ? (
                  <span className="text-xs text-brand bg-brand-soft px-1.5 py-0.5 rounded">
                    {asset.asset_type === "character" ? "三视角完整" : "已生成"}
                  </span>
                ) : (
                  <span className="text-xs text-warn bg-warn/10 px-1.5 py-0.5 rounded">
                    {asset.asset_type === "character" ? "三视角未完整" : "未生成"}
                  </span>
                )}
              </div>
              {asset.face_identity && <p className="text-xs text-sub mt-2 line-clamp-2">面部基准：{asset.face_identity}</p>}
            </div>
            <div className="lg:w-36 shrink-0 flex lg:flex-col gap-2 justify-end lg:justify-start">
              {actions}
            </div>
          </div>
        </div>
        <AgentDialog
          open={agentOpen}
          onOpenChange={setAgentOpen}
          targetType="asset"
          targetId={asset.id}
          projectId={projectId}
          title={`AI 修改 · ${asset.name}`}
          onTaskStarted={onUpdate}
          initialPrompt={asset.prompt}
        />
        {historyDialog}
      </>
    );
  }

  return (
    <>
      {lightboxOverlay}
      <div className="flex h-full flex-col overflow-hidden rounded-xl border border-line bg-panel transition-all hover:shadow-card-hover">
        <div className="aspect-[4/3] bg-soft relative overflow-hidden group">
          {isGenerating ? (
            <div className="w-full h-full flex flex-col items-center justify-center gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-brand" />
              <span className="text-xs text-muted">{isQueued ? "排队等待…" : "生成中…"}</span>
            </div>
          ) : asset.asset_type === "character" && hasCharacterViews ? viewStrip : singlePreview}
          <div className="absolute top-2 left-2">
            <Badge variant={cfg.variant}>{cfg.label}</Badge>
          </div>
        </div>
        <div className="flex min-h-[210px] flex-1 flex-col p-4">
          <p className="text-sm font-medium text-text truncate">{asset.name}</p>
          <p className="text-xs text-muted mt-0.5 line-clamp-2">{promptPreview}</p>
          {asset.asset_type === "character" && (
            <div className="mt-1 flex flex-wrap gap-1">
              {(asset.asset_package || asset.character_name) && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">资产包：{asset.asset_package || asset.character_name}</span>}
              {asset.scene_scope && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">场景：{asset.scene_scope}</span>}
              {asset.appearance_stage && <span className="text-xs text-sub bg-soft px-1.5 py-0.5 rounded">阶段：{asset.appearance_stage}</span>}
            </div>
          )}
          {asset.asset_type === "character" && asset.face_identity && (
            <p className="text-xs text-sub mt-1 line-clamp-2">面部基准：{asset.face_identity}</p>
          )}
          {asset.asset_type === "character" && asset.voice_profile && (
            <p className="text-xs text-sub mt-1 line-clamp-2">音色：{asset.voice_profile}</p>
          )}
          <div className="mt-auto pt-3">{actions}</div>
        </div>
      </div>

      <AgentDialog
        open={agentOpen}
        onOpenChange={setAgentOpen}
        targetType="asset"
        targetId={asset.id}
        projectId={projectId}
        title={`AI 修改 · ${asset.name}`}
        onTaskStarted={onUpdate}
        initialPrompt={asset.prompt}
      />
      {historyDialog}
    </>
  );
}

function AssetGroupCard({
  group,
  type,
  onOpen,
}: {
  group: AssetGroup;
  type: string;
  onOpen: () => void;
}) {
  const { cosUrl } = useCos();
  const previewAsset = getGroupPreviewAsset(group);
  const previewUrl = previewAsset ? getAssetMainPreviewUrl(previewAsset) : undefined;
  const stats = getAssetGroupStats(group);
  const typeLabel = ASSET_TYPE_ZH[type] ?? type;
  const completeLabel = type === "character" ? "三视角" : "图片";
  const stageSummary = group.assets
    .map((asset) => asset.appearance_stage || asset.scene_scope || asset.name)
    .filter(Boolean)
    .slice(0, 3)
    .join(" / ");

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-line bg-panel transition-all hover:shadow-card-hover">
      <button type="button" className="flex h-full w-full flex-col text-left" onClick={onOpen}>
        <div className="relative aspect-[4/3] bg-soft overflow-hidden">
          {previewUrl ? (
            <img
              src={cosUrl(previewUrl)}
              alt={previewAsset?.name || group.label}
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-muted">
              <ImagePlus className="w-7 h-7" />
              <span className="text-sm">待生成主预览图</span>
            </div>
          )}
          <div className="absolute top-3 left-3 flex flex-wrap gap-1.5">
            <Badge variant="secondary">{typeLabel}资产包</Badge>
            {stats.running > 0 && <Badge variant="secondary">{stats.running} 生成中</Badge>}
            {stats.readyToConfirm > 0 && <Badge variant="warning">{stats.readyToConfirm} 待确认</Badge>}
          </div>
          {type === "character" && previewAsset?.view_urls && (
            <div className="absolute left-3 right-3 bottom-3 grid grid-cols-3 gap-1.5">
              {CHARACTER_VIEW_META.map((view) => {
                const url = previewAsset.view_urls?.[view.key];
                return (
                  <div key={view.key} className="h-12 rounded-md overflow-hidden border border-white/70 bg-black/25">
                    {url ? (
                      <img src={cosUrl(url)} alt={view.label} className="w-full h-full object-contain" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[10px] text-white/70">{view.label}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          <div className="absolute bottom-3 right-3 rounded-full bg-black/55 p-1.5 text-white">
            <ZoomIn className="w-4 h-4" />
          </div>
        </div>

        <div className="p-4 flex flex-col min-h-[210px] flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-base font-semibold text-text truncate">{group.label}</p>
              <p className="text-xs text-sub mt-1">
                {group.assets.length} 个{typeLabel}资产 · {stats.generated}/{stats.total} 已生成{completeLabel}
              </p>
            </div>
            <ChevronRight className="w-5 h-5 text-muted shrink-0 mt-0.5" />
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2">
            <div className="rounded-lg bg-soft px-2 py-2">
              <div className="text-sm font-semibold text-text">{stats.generated}</div>
              <div className="text-[11px] text-muted">已生成</div>
            </div>
            <div className="rounded-lg bg-soft px-2 py-2">
              <div className="text-sm font-semibold text-text">{stats.approved}</div>
              <div className="text-[11px] text-muted">已确认</div>
            </div>
            <div className="rounded-lg bg-soft px-2 py-2">
              <div className="text-sm font-semibold text-text">{stats.pendingGenerate}</div>
              <div className="text-[11px] text-muted">待生成</div>
            </div>
          </div>

          <p className="mt-3 text-xs text-sub line-clamp-2 min-h-[32px]">
            {stageSummary || previewAsset?.prompt || "点击查看资产明细、提示词和生成状态。"}
          </p>

          <div className="mt-auto pt-3 flex items-center justify-between text-xs text-muted">
            <span>点击打开预览</span>
            {stats.generated === stats.total && stats.total > 0 && (
              <span className="text-brand">图片完整</span>
            )}
          </div>
        </div>
      </button>
    </div>
  );
}

export function Phase3({ projectId, onFinish, manageMode = false }: { projectId: string; onFinish: () => void; manageMode?: boolean }) {
  const [tab, setTab] = useState("character");
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAssetGroup, setSelectedAssetGroup] = useState<{ key: string; type: string } | null>(null);
  const [assetFilter, setAssetFilter] = useState<AssetFilter>("all");
  const [promptAsset, setPromptAsset] = useState<ApiAsset | null>(null);
  const [assetPromptDraft, setAssetPromptDraft] = useState("");
  const [savingAssetPrompt, setSavingAssetPrompt] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [pollKey, setPollKey] = useState(0);

  const loadAssets = async () => {
    const list = await assetAPI.list(projectId);
    setAssets(list);
    return list;
  };

  const scheduleNextPoll = (tickFn: () => void) => {
    pollTimerRef.current = setTimeout(tickFn, 3000);
  };

  useEffect(() => {
    let cancelled = false;
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);

    const tick = async () => {
      const list = await loadAssets();
      if (cancelled) return;

      const stillRunning = list.some((a) => a.status === "generating" || a.status === "queued");
      if (!cancelled && stillRunning) {
        scheduleNextPoll(tick);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [projectId, pollKey]);

  useEffect(() => {
    setAssetPromptDraft(promptAsset?.prompt ?? "");
  }, [promptAsset]);

  const tabs = [...new Set(assets.map((a) => a.asset_type))].filter((t) => ["character", "scene", "prop"].includes(t));
  const filteredAssets = assets.filter((a) => matchesAssetFilter(a, assetFilter));
  const currentGroups = buildAssetGroups(filteredAssets.filter((a) => a.asset_type === tab));
  const selectedGroup = selectedAssetGroup
    ? buildAssetGroups(assets.filter((a) => a.asset_type === selectedAssetGroup.type)).find((group) => group.key === selectedAssetGroup.key)
    : null;
  const pendingCount = assets.filter((a) => a.status !== "approved").length;
  const generatingCount = assets.filter((a) => a.status === "generating" || a.status === "queued").length;
  const needGenerateCount = assets.filter((a) =>
    !isAssetImageReady(a) && a.status !== "generating" && a.status !== "queued"
  ).length;
  const readyToConfirmCount = assets.filter((a) => isAssetImageReady(a) && a.status !== "approved").length;
  const approvedCount = assets.filter((a) => a.status === "approved").length;
  const characterGroupCount = buildAssetGroups(assets.filter((a) => a.asset_type === "character")).length;
  const characterAssetCount = assets.filter((a) => a.asset_type === "character").length;
  const sceneAssetCount = assets.filter((a) => a.asset_type === "scene").length;
  const propAssetCount = assets.filter((a) => a.asset_type === "prop").length;
  const filterCounts: Record<AssetFilter, number> = {
    all: assets.length,
    need_generate: assets.filter((a) => matchesAssetFilter(a, "need_generate")).length,
    generating: assets.filter((a) => matchesAssetFilter(a, "generating")).length,
    pending_confirm: assets.filter((a) => matchesAssetFilter(a, "pending_confirm")).length,
    approved: assets.filter((a) => matchesAssetFilter(a, "approved")).length,
  };

  const handleGenerateAll = async () => {
    const needGen = assets.filter((a) =>
      !isAssetImageReady(a) && a.status !== "generating" && a.status !== "queued"
    );
    if (needGen.length === 0) return;

    setBatchGenerating(true);
    setError(null);
    try {
      await Promise.allSettled(needGen.map((a) => generateAPI.assetImage(a.id)));
      await loadAssets();
      setPollKey((k) => k + 1);
    } finally {
      setBatchGenerating(false);
    }
  };

  const handleConfirmReady = async () => {
    const readyAssets = assets.filter((a) => isAssetImageReady(a) && a.status !== "approved" && !isAssetRunning(a));
    if (readyAssets.length === 0) return;

    setSubmitting(true);
    setError(null);
    try {
      await Promise.allSettled(readyAssets.map((a) => assetAPI.confirm(projectId, a.id)));
      await loadAssets();
      setPollKey((k) => k + 1);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveAssetPrompt = async () => {
    if (!promptAsset) return;
    setSavingAssetPrompt(true);
    setError(null);
    try {
      const updated = await assetAPI.update(projectId, promptAsset.id, { prompt: assetPromptDraft });
      setPromptAsset(updated);
      setAssets((prev) => prev.map((asset) => asset.id === updated.id ? updated : asset));
      setPollKey((k) => k + 1);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "保存资产提示词失败");
    } finally {
      setSavingAssetPrompt(false);
    }
  };

  const handleFinish = async () => {
    if (!manageMode) {
      // 拦截：有资产仍在生成中或尚未生成图片
      const notReady = assets.filter(
        (a) => a.status === "generating" || a.status === "queued" || !isAssetImageReady(a)
      );
      if (notReady.length > 0) {
        setError(`还有 ${notReady.length} 个资产尚未生成完毕，请等待生成完成后再确认。`);
        return;
      }
    }
    setSubmitting(true);
    setError(null);
    try {
      if (!manageMode) await projectAPI.confirmAssets(projectId);
      onFinish();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "确认失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="page-panel tech-border mb-5 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="section-title mb-2">Asset Review</p>
            <h2 className="text-xl font-semibold text-text mb-1">图片确认</h2>
            <p className="text-sm text-sub">先检查资产包一致性，再生成图片并确认。人物、场景、道具如有不同阶段资产，均按资产组卡片预览。</p>
          </div>
          <div className="flex flex-wrap gap-2 items-center shrink-0">
            <Button
              size="sm"
              onClick={handleGenerateAll}
              disabled={batchGenerating || needGenerateCount === 0}
              variant="outline"
              title={needGenerateCount === 0 ? "没有待生成资产" : `生成 ${needGenerateCount} 个未生成资产`}
            >
              {batchGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImagePlus className="w-3.5 h-3.5" />}
              生成全部资产
            </Button>
            <Button
              size="sm"
              onClick={handleConfirmReady}
              disabled={submitting || readyToConfirmCount === 0}
              variant="outline"
              title={readyToConfirmCount === 0 ? "没有可确认资产" : `确认 ${readyToConfirmCount} 个已生成资产`}
            >
              {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              确认全部已生成
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 mb-4">
        {[
          ["人物包", characterGroupCount],
          ["阶段造型", characterAssetCount],
          ["场景", sceneAssetCount],
          ["道具", propAssetCount],
          ["待生成", needGenerateCount],
          ["生成中", generatingCount],
          ["已确认", approvedCount],
        ].map(([label, value]) => (
          <div key={label} className="mini-stat">
            <div className="text-lg font-semibold text-text">{value}</div>
            <div className="text-xs text-muted">{label}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 mb-5">
        {ASSET_FILTERS.map((filter) => (
          <button
            key={filter.key}
            type="button"
            onClick={() => setAssetFilter(filter.key)}
            className={cn(
              "h-8 rounded-full border px-3 text-xs font-medium transition-colors",
              assetFilter === filter.key
                ? "border-brand bg-brand text-white"
                : "border-line bg-panel text-sub hover:border-brand/40 hover:text-text"
            )}
          >
            {filter.label}
            <span className={cn("ml-1", assetFilter === filter.key ? "text-white/75" : "text-muted")}>
              {filterCounts[filter.key]}
            </span>
          </button>
        ))}
      </div>

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
            {currentGroups.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 items-stretch">
                {currentGroups.map((group) => {
                  if (isSingleImageAssetGroup(group)) {
                    const [asset] = group.assets;
                    return (
                      <AssetCard
                        key={group.key}
                        asset={asset}
                        projectId={projectId}
                        lightboxItems={getAssetGroupLightboxItems(group)}
                        onViewPrompt={setPromptAsset}
                        onUpdate={() => setPollKey((k) => k + 1)}
                      />
                    );
                  }

                  return (
                    <AssetGroupCard
                      key={group.key}
                      group={group}
                      type={tab}
                      onOpen={() => setSelectedAssetGroup({ key: group.key, type: tab })}
                    />
                  );
                })}
              </div>
            ) : (
              <div className="empty-state-panel">
                当前筛选条件下没有资产。
              </div>
            )}
          </TabsContent>
        </Tabs>
      ) : (
        <div className="empty-state-panel">
          暂无资产，请返回分集与资产确认页检查资产清单。
        </div>
      )}

      {error && (
        <div className="status-banner status-banner-danger mt-6 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />{error}
        </div>
      )}

      <Dialog open={Boolean(selectedAssetGroup && selectedGroup)} onOpenChange={(open) => !open && setSelectedAssetGroup(null)}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>{selectedGroup?.label || "资产包预览"}</DialogTitle>
            <DialogDescription>
              {selectedGroup
                ? `${selectedGroup.assets.length} 个${ASSET_TYPE_ZH[selectedAssetGroup?.type || ""] ?? "资产"}，可在这里查看不同阶段、生成提示词和确认状态。`
                : "查看资产包明细。"}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-y-auto pr-1">
            <div className="space-y-3">
              {selectedGroup?.assets.map((asset) => (
                <AssetCard
                  key={asset.id}
                  asset={asset}
                  projectId={projectId}
                  layout="stage"
                  lightboxItems={getAssetGroupLightboxItems(selectedGroup)}
                  onViewPrompt={setPromptAsset}
                  onUpdate={() => setPollKey((k) => k + 1)}
                />
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedAssetGroup(null)}>关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={promptAsset !== null} onOpenChange={(open) => !open && setPromptAsset(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{promptAsset?.name || "资产提示词"}</DialogTitle>
            <DialogDescription>当前资产记录中保存的生成提示词，可人工修改并保存，下一次生成资产图会使用保存后的内容。</DialogDescription>
          </DialogHeader>
          <Textarea
            value={assetPromptDraft}
            onChange={(e) => setAssetPromptDraft(e.target.value)}
            rows={16}
            className="min-h-[45vh] text-xs leading-relaxed font-sans"
            placeholder="可在这里人工修改资产生成提示词"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setPromptAsset(null)}>关闭</Button>
            <Button onClick={handleSaveAssetPrompt} disabled={!promptAsset || savingAssetPrompt}>
              {savingAssetPrompt ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />保存中…</> : <><Check className="w-3.5 h-3.5" />保存提示词</>}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="sticky-action-bar">
        <p className="text-sm text-sub">
          {manageMode
            ? (pendingCount > 0 ? `${pendingCount} 个资产未确认。` : "所有资产已确认。")
            : (generatingCount > 0
                ? `${generatingCount} 个资产生成中，请等待完成后再确认。`
                : needGenerateCount > 0
                  ? `还有 ${needGenerateCount} 个资产未生成，请先生成资产图。`
                : pendingCount > 0
                  ? `还有 ${pendingCount} 个资产未确认，仍可继续初始化。`
                  : "所有资产已确认，可以开始制作。")}
        </p>
        <Button
          onClick={handleFinish}
          disabled={submitting || (!manageMode && generatingCount > 0)}
          variant={manageMode ? "outline" : "default"}
          title={!manageMode && generatingCount > 0 ? `${generatingCount} 个资产仍在生成中，请等待` : undefined}
        >
          {submitting
            ? <><Loader2 className="w-4 h-4 animate-spin" />处理中…</>
            : manageMode
              ? "关闭"
              : <>完成初始化，开始制作 <ChevronRight className="w-4 h-4" /></>}
        </Button>
      </div>
    </div>
  );
}

// ─── 主组件 ────────────────────────────────────────────────────
export default function NewProjectScreen({
  project,
  onProjectUpdate,
}: {
  project: Project;
  onProjectUpdate: () => void;
}) {
  const navigate = useNavigate();
  const { reload } = useProjects();

  const [phase, setPhase] = useState<Phase | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [taskRecordId, setTaskRecordId] = useState<string>("");
  const [episodes, setEpisodes] = useState<EpisodeDraft[]>([]);
  const [maxReached, setMaxReached] = useState(1);

  const advanceTo = (p: Phase) => {
    const visual = p <= 1.5 ? 1 : p === 2 ? 2 : 3;
    setMaxReached((prev) => Math.max(prev, visual));
    setPhase(p);
  };

  // 根据 init_status 恢复到正确的步骤
  useEffect(() => {
    async function resolvePhase() {
      const status = project.initStatus;

      if (status === "episodes_confirmed" || status === "assets_confirmed") {
        advanceTo(3);
        return;
      }

      if (status === "script_uploaded") {
        try {
          const tasks = await generateAPI.listTasks({ project_id: project.id, task_type: "parse_script" });
          const latest = tasks[0];
          if (latest) {
            if (latest.status === "running" || latest.status === "pending") {
              setTaskRecordId(latest.id);
              advanceTo(1.5);
              return;
            }
            if (latest.status === "success") {
              // 解析已完成，从 DB 加载分集
              const apiEps = await episodeAPI.list(project.id);
              if (apiEps.length > 0) {
                setEpisodes(apiEps.map((e) => ({
                  id: e.id,
                  number: e.number,
                  title: e.title,
                  wordCount: e.word_count,
                  estimatedDuration: e.estimated_duration,
                  summary: e.summary,
                  scriptExcerpt: e.script_excerpt,
                  sourceStartLine: e.source_start_line || undefined,
                  sourceEndLine: e.source_end_line || undefined,
                  dialogueCount: e.dialogue_count ?? undefined,
                  sourceIntegrity: e.source_integrity || undefined,
                })));
                advanceTo(2);
                return;
              }
            }
          }
        } catch { /* 降级到 Phase 1 */ }
        advanceTo(1);
        return;
      }

      advanceTo(1);
    }
    resolvePhase();
  }, [project.id, project.initStatus]);

  const handleFinish = async () => {
    reload();
    onProjectUpdate();
    navigate(`/projects/${project.id}`);
  };

  if (phase === null) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="page-shell py-8">
        <div className="page-header mb-8">
          <p className="section-title mb-2">Project Initialization</p>
          <h1 className="text-2xl font-semibold text-text">{project.title}</h1>
          <p className="text-sm text-sub mt-1">完成以下三步后即可开始分集制作。</p>
        </div>
        <StepIndicator current={phase} maxReached={maxReached} />

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
            projectId={project.id}
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

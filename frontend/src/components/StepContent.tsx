import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  CheckCircle2, RefreshCw, Loader2, Play, Volume2,
  Film, Layers, Clock, Tag, Edit3, Check, FileText, MessageCircle, History, RotateCcw, AlertTriangle, Images,
} from "lucide-react";
import AgentDialog from "@/components/AgentDialog";
import { Sheet } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { EpisodeStep, EpisodeDetail, Shot, ShotState, getStepIndex } from "@/lib/data";
import { cn } from "@/lib/utils";
import { generateAPI, shotAPI, episodeAPI, type ApiGenResponse } from "@/lib/api";
import { buildShotGroups, segmentTitle, shotNumberLabel } from "@/lib/shot-groups";
import { useCos } from "@/lib/CosContext";

interface StepContentProps {
  step: EpisodeStep;
  episode: EpisodeDetail;
  projectId: string;
}

/** 当前浏览的步骤是否已经过去（episode 已推进到更后面的步骤） */
function calcIsPastStep(activeStep: EpisodeStep, currentStep: EpisodeStep): boolean {
  return getStepIndex(activeStep) < getStepIndex(currentStep);
}

// ─── 分镜状态配置 ────────────────────────────────────────────

const shotStateCfg: Record<ShotState, {
  label: string;
  variant: "success" | "warning" | "secondary" | "outline";
}> = {
  approved:      { label: "已通过",    variant: "success" },
  rendered:      { label: "待审批",    variant: "warning" },
  review_failed: { label: "未通过",    variant: "warning" },
  rendering:     { label: "视频生成中", variant: "secondary" },
  asset_ready:   { label: "资产就绪",  variant: "secondary" },
  generating:    { label: "图片生成中", variant: "secondary" },
  planned:       { label: "待生成",    variant: "outline" },
};

// ─── 顶部审批操作栏 ──────────────────────────────────────────

interface ApprovalBarProps {
  approved: number;
  total: number;
  onApproveAll: () => void;
  onRegenerate?: () => void;
  regenerateLabel?: string;
  allApproved?: boolean;
  approving?: boolean;
  regenerating?: boolean;
  notReady?: boolean;
  notReadyTip?: string;
  compact?: boolean;
}

function ApprovalBar({
  approved, total, onApproveAll, onRegenerate, regenerateLabel, allApproved, approving,
  regenerating, notReady, notReadyTip, compact,
}: ApprovalBarProps) {
  return (
    <div className={cn(
      "flex flex-col gap-3 rounded-xl border border-line bg-panel/95 px-4 shadow-xs sm:flex-row sm:items-center sm:gap-4",
      compact ? "py-2.5" : "mb-5 py-3"
    )}>
      <div className="w-full flex-1">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-sub">审批进度</span>
          <span className={cn(
            "text-xs font-bold tabular-nums",
            approved === total ? "text-success" : "text-text"
          )}>
            {approved} / {total}
          </span>
        </div>
        <div className="h-1.5 bg-line rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-signal to-success rounded-full transition-all duration-500"
            style={{ width: total > 0 ? `${(approved / total) * 100}%` : "0%" }}
          />
        </div>
        {notReady && notReadyTip && (
          <p className="text-xs text-muted mt-1">{notReadyTip}</p>
        )}
        {regenerating && (
          <p className="text-xs text-muted mt-1">后台重新生成中，你可以继续其他操作</p>
        )}
      </div>
      <div className="grid w-full grid-cols-1 gap-2 sm:flex sm:w-auto sm:shrink-0 sm:items-center">
        {onRegenerate && !allApproved && (
          <Button size="sm" className="w-full sm:w-auto" variant="outline" onClick={onRegenerate} disabled={regenerating}>
            {regenerating
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />重新生成中…</>
              : <><RefreshCw className="w-3.5 h-3.5" />{regenerateLabel ?? "打回重新生成"}</>
            }
          </Button>
        )}
        <Button
          size="sm"
          className="w-full sm:w-auto"
          onClick={onApproveAll}
          disabled={allApproved || approving || notReady || regenerating}
        >
          {approving ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" />提交中…</>
          ) : allApproved ? (
            <><Check className="w-3.5 h-3.5" />已全部通过</>
          ) : (
            <><CheckCircle2 className="w-3.5 h-3.5" />全部审批通过</>
          )}
        </Button>
      </div>
    </div>
  );
}

function LazyVideo({ src, className }: { src: string; className?: string }) {
  const [loaded, setLoaded] = useState(false);
  const [errored, setErrored] = useState(false);
  const [key, setKey] = useState(0);
  const lastSrcRef = useRef(src);
  useEffect(() => {
    if (lastSrcRef.current !== src) {
      lastSrcRef.current = src;
      setLoaded(false);
      setErrored(false);
      setKey((k) => k + 1);
    }
  }, [src]);
  return (
    <div className="relative w-full h-full">
      {!loaded && !errored && (
        <div className="absolute inset-0 flex items-center justify-center bg-soft rounded-2xl">
          <Loader2 className="w-6 h-6 text-brand animate-spin" />
        </div>
      )}
      {errored && (
        <div className="absolute inset-0 flex items-center justify-center bg-soft rounded-2xl">
          <Film className="w-6 h-6 text-line" />
        </div>
      )}
      <video
        key={key} src={src} controls
        className={cn(className, !loaded && "opacity-0")}
        onLoadedData={() => setLoaded(true)}
        onError={() => setErrored(true)}
      />
    </div>
  );
}

// ─── Step 1：分镜脚本 ────────────────────────────────────────

function StepScript({
  episode, projectId, isPast,
}: { episode: EpisodeDetail; projectId: string; isPast?: boolean }) {
  const shots = episode.shots;
  const generated = shots.length > 0;
  const shotGroups = buildShotGroups(shots);

  // 派生：所有 shot 都是 approved 时，脚本已通过
  const allShotsApproved = shots.length > 0 && shots.every((s) => s.state === "approved");
  const approved = isPast || allShotsApproved;

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [regenDialogOpen, setRegenDialogOpen] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentTarget, setAgentTarget] = useState<string | null>(null);
  const [promptShot, setPromptShot] = useState<Shot | null>(null);
  const [scriptPromptDraft, setScriptPromptDraft] = useState("");
  const [savingScriptPrompt, setSavingScriptPrompt] = useState(false);

  // 由后端 running_tasks 派生，刷新后状态自动恢复
  const generating = episode.runningTasks.includes("gen_shot_script");

  const handleGenerate = async () => {
    setError(null);
    try {
      await generateAPI.shotScript(episode.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "生成失败");
    }
  };

  const handleStartEdit = (shot: Shot) => {
    setEditingId(shot.id);
    setEditText(shot.description);
  };

  const handleSaveEdit = async (id: string) => {
    try {
      await shotAPI.update(projectId, episode.id, id, { description: editText } as never);
    } catch { /* 静默 */ }
    setEditingId(null);
  };

  const handleApproveAll = async () => {
    setApproving(true);
    setError(null);
    try {
      const reviews = shots.map((s) => ({ shot_id: s.id, approved: true }));
      await shotAPI.batchReview(projectId, episode.id, reviews);
      await episodeAPI.setStep(projectId, episode.id, "storyboard_videos");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "审批失败");
    } finally {
      setApproving(false);
    }
  };

  const buildShotScriptPrompt = (shot: Shot) => {
    const lines = [
      `镜头编号：${shot.shotCode}`,
      `所属片段：${shot.segmentCode || "无"} ${shot.segmentName || ""}`.trim(),
      `片段功能：${shot.segmentFunction || "无"}`,
      `镜头功能：${shot.shotFunction || "无"}`,
      `视频时长：${shot.duration}秒`,
      `与上一镜衔接：${shot.transitionIn || "无"}`,
      `与下一镜衔接：${shot.transitionOut || "无"}`,
      `转场类型：${shot.transitionType || "hard_cut"}`,
      `起始状态：${shot.startState || "无"}`,
      `结束状态：${shot.endState || "无"}`,
      `画面方向/空间轴线：${shot.screenDirection || "无"}`,
      `连续性约束：${shot.continuityNotes || "无"}`,
      `是否使用上一镜尾帧：${shot.usePrevLastFrame ? "是" : "否"}`,
      `连续性刷新状态：${shot.continuityDirty ? (shot.continuityDirtyReason || "需刷新后续承接") : "正常"}`,
      "",
      "分镜描述：",
      shot.description || "无",
      "",
      "绑定资产：",
      shot.assets.length > 0 ? shot.assets.join("、") : "无",
      "",
      "台词与表演：",
      shot.dialogues.length > 0
        ? shot.dialogues.map((line, i) => [
            `${i + 1}. ${line.speaker ? `${line.speaker}：` : ""}${line.text}`,
            `   情绪：${line.emotion || "无"}`,
            `   语气：${line.delivery || "无"}`,
            `   动作：${line.action || "无"}`,
            `   表情：${line.expression || "无"}`,
          ].join("\n")).join("\n")
        : "无台词",
    ];
    if (shot.submittedPrompt || shot.prompt) {
      lines.push("", "原始提示词/提交内容：", shot.submittedPrompt || shot.prompt || "");
    }
    return lines.join("\n");
  };

  useEffect(() => {
    setScriptPromptDraft(promptShot ? (promptShot.submittedPrompt || promptShot.prompt || buildShotScriptPrompt(promptShot)) : "");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promptShot]);

  const promptShotIndex = promptShot ? shots.findIndex((s) => s.id === promptShot.id) : -1;
  const promptShotLabel = promptShotIndex >= 0 ? shotNumberLabel(promptShotIndex) : "镜头";
  const agentShot = agentTarget ? shots.find((s) => s.id === agentTarget) : undefined;
  const agentShotIndex = agentShot ? shots.findIndex((s) => s.id === agentShot.id) : -1;
  const agentShotLabel = agentShotIndex >= 0 ? shotNumberLabel(agentShotIndex) : "镜头";

  const handleSaveScriptPrompt = async () => {
    if (!promptShot) return;
    setSavingScriptPrompt(true);
    setError(null);
    try {
      await shotAPI.update(projectId, episode.id, promptShot.id, {
        prompt: scriptPromptDraft,
        submitted_prompt: scriptPromptDraft,
      } as never);
      setPromptShot({
        ...promptShot,
        prompt: scriptPromptDraft,
        submittedPrompt: scriptPromptDraft,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "保存提示词失败");
    } finally {
      setSavingScriptPrompt(false);
    }
  };

  if (!generated) {
    return (
      <div className="page-panel tech-border flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-14 h-14 rounded-2xl bg-soft flex items-center justify-center">
          <Layers className="w-7 h-7 text-muted" />
        </div>
        <div className="text-center">
          <p className="font-medium text-text">尚未生成分镜脚本</p>
          <p className="text-sm text-sub mt-1 max-w-sm">
            AI 将根据本集剧本和连续性约束自动生成分镜脚本及资产绑定。
          </p>
        </div>
        {episode.continuityNotes && (
          <div className="max-w-md w-full rounded-xl border border-line bg-soft p-4">
            <p className="text-xs font-semibold text-sub mb-1.5">连续性约束</p>
            <p className="text-xs text-muted">{episode.continuityNotes}</p>
          </div>
        )}
        {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
        <Button onClick={handleGenerate} disabled={generating}>
          {generating
            ? <><Loader2 className="w-4 h-4 animate-spin" />AI 生成中，请稍候…</>
            : "生成分镜脚本"}
        </Button>
        {generating && <p className="text-xs text-muted">后台生成中，你可以继续其他操作</p>}
      </div>
    );
  }

  return (
    <div>
      {episode.continuityNotes && (
        <div className="mb-4 rounded-xl border border-warn/30 bg-warn-soft p-3">
          <span className="text-xs font-semibold text-warn">连续性约束：</span>
          <span className="text-xs text-warn/80 ml-1">{episode.continuityNotes}</span>
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-xl border border-danger/20 bg-danger-soft p-3">
          <p className="text-xs text-danger">{error}</p>
        </div>
      )}

      <ApprovalBar
        approved={approved ? shots.length : shots.filter((s) => s.state === "approved").length}
        total={shots.length}
        onApproveAll={handleApproveAll}
        onRegenerate={() => setRegenDialogOpen(true)}
        regenerateLabel="打回重新生成"
        allApproved={approved}
        approving={approving}
        regenerating={generating}
      />

      <div className="space-y-4">
        {shotGroups.map((group, groupIdx) => (
          <section key={group.key} className="rounded-2xl border border-line/80 bg-panel/60 p-3">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2.5 py-1 text-xs font-semibold text-brand">
                <Layers className="w-3 h-3" />{segmentTitle(group, groupIdx)}
              </span>
              {group.segmentFunction && (
                <span className="rounded-full bg-soft px-2 py-1 text-xs text-sub">{group.segmentFunction}</span>
              )}
              <span className="text-xs text-muted">{group.items.length} 个镜头</span>
            </div>
            <div className="space-y-3">
              {group.items.map(({ shot, index }) => {
                const cfg = shotStateCfg[shot.state];
                const isEditing = editingId === shot.id;

                return (
                  <div
                    key={shot.id}
                    className={cn(
                      "media-card p-3 sm:p-4",
                      approved ? "border-brand/30 bg-brand/5" : "border-line",
                    )}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-soft text-xs font-black text-text ring-1 ring-line/80">
                        {index + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-2">
                          <span className="text-sm font-semibold text-text">{shotNumberLabel(index)}</span>
                          {shot.shotCode && <span className="text-xs text-muted">原编号 {shot.shotCode}</span>}
                          <Badge variant={approved ? "success" : cfg.variant}>
                            {approved ? "已通过" : cfg.label}
                          </Badge>
                          {shot.shotFunction && (
                            <span className="text-xs text-brand bg-brand-soft px-2 py-0.5 rounded-full">
                              {shot.shotFunction}
                            </span>
                          )}
                          <span className="flex items-center gap-1 text-xs text-muted">
                            <Clock className="w-3 h-3" />{shot.duration}s
                          </span>
                          <span className="text-xs text-muted">{shot.version}</span>
                        </div>

                        {isEditing ? (
                          <div className="space-y-2">
                            <Textarea
                              value={editText}
                              onChange={(e) => setEditText(e.target.value)}
                              rows={3}
                              className="text-xs"
                              autoFocus
                            />
                            <div className="flex gap-2">
                              <Button size="sm" onClick={() => handleSaveEdit(shot.id)}>
                                <Check className="w-3.5 h-3.5" />保存
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                                取消
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="group/desc flex flex-col gap-2 sm:flex-row sm:items-start">
                            <p className="text-xs text-sub leading-relaxed flex-1">{shot.description}</p>
                            <div className="flex shrink-0 items-center gap-2 sm:gap-1.5">
                              <button
                                onClick={() => setPromptShot(shot)}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-panel text-muted transition-colors hover:bg-soft hover:text-brand sm:h-8 sm:w-8"
                                title="查看完整提交提示词"
                                aria-label="查看完整提交提示词"
                              >
                                <FileText className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleStartEdit(shot)}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-panel text-muted transition-colors hover:bg-soft hover:text-brand sm:h-8 sm:w-8"
                                title="编辑描述"
                                aria-label="编辑描述"
                              >
                                <Edit3 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => setAgentTarget(shot.id)}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-panel text-muted transition-colors hover:bg-soft hover:text-brand sm:h-8 sm:w-8"
                                title="AI 修改"
                                aria-label="AI 修改"
                              >
                                <MessageCircle className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        )}

                        {shot.assets.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {shot.assets.map((a) => (
                              <span key={a} className="flex items-center gap-1 text-xs bg-soft text-sub px-2 py-0.5 rounded-full">
                                <Tag className="w-2.5 h-2.5" />{a}
                              </span>
                            ))}
                          </div>
                        )}

                        {shot.dialogues.length > 0 && (
                          <div className="mt-2 flex flex-col gap-1">
                            {shot.dialogues.map((line, i) => (
                              <div key={i} className="px-2 py-1.5 bg-soft rounded text-xs text-text leading-relaxed border-l-2 border-brand/40">
                                {line.speaker && <span className="font-medium text-brand mr-1">{line.speaker}：</span>}
                                {line.text}
                                {(line.emotion || line.delivery || line.action || line.expression) && (
                                  <div className="mt-1 text-[11px] leading-relaxed text-muted">
                                    {line.emotion && <span>情绪：{line.emotion}；</span>}
                                    {line.delivery && <span>语气：{line.delivery}；</span>}
                                    {line.action && <span>动作：{line.action}；</span>}
                                    {line.expression && <span>表情：{line.expression}</span>}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      {/* 打回重新生成 — AgentDialog，AI 工具调用触发 Celery 任务，状态由轮询驱动 */}
      <AgentDialog
        open={regenDialogOpen}
        onOpenChange={(v) => setRegenDialogOpen(v)}
        targetType="episode"
        targetId={episode.id}
        projectId={projectId}
        title="AI 重新生成分镜脚本"
      />

      <Sheet
        open={!!promptShot}
        onClose={() => setPromptShot(null)}
        title={`${promptShotLabel} · 完整提交提示词`}
      >
        <div className="space-y-3">
          <Textarea
            value={scriptPromptDraft}
            onChange={(e) => setScriptPromptDraft(e.target.value)}
            rows={22}
            className="min-h-[60vh] text-xs leading-relaxed font-sans"
            placeholder="可在这里人工修改分镜脚本阶段的完整提交提示词"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setPromptShot(null)}>关闭</Button>
            <Button onClick={handleSaveScriptPrompt} disabled={!promptShot || savingScriptPrompt}>
              {savingScriptPrompt ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />保存中…</> : <><Check className="w-3.5 h-3.5" />保存提示词</>}
            </Button>
          </div>
        </div>
      </Sheet>

      {/* 单镜 AI 修改对话 — 绑定 episode，让 AI 知道上下文 */}
      {agentTarget && (
        <AgentDialog
          open={!!agentTarget}
          onOpenChange={(v) => !v && setAgentTarget(null)}
          targetType="episode"
          targetId={episode.id}
          projectId={projectId}
          title="AI 修改 · 镜头描述"
          initialPrompt={`请修改${agentShotLabel}的描述：${agentShot?.description ?? ""}`}
        />
      )}
    </div>
  );
}

// ─── Step 2：分镜视频（含审批）──────────────────────────────

type WatchedVideoTask = {
  recordId: string;
  label: string;
  shotId?: string;
  shotIds?: string[];
};

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

function isShotWarning(shot?: Shot): boolean {
  if (!shot) return false;
  return !shot.videoUrl && (shot.state === "review_failed" || !!shot.continuityDirty);
}

function shotWarningText(shot?: Shot): string {
  return shot?.reviewComment
    || shot?.continuityDirtyReason
    || "该镜头生成异常，需要检查提示词、资产引用后重新生成。";
}

function StepVideos({
  episode, projectId, isPast,
}: { episode: EpisodeDetail; projectId: string; isPast?: boolean }) {
  const { cosUrl } = useCos();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const shots = episode.shots;
  const shotParam = searchParams.get("shot");
  const selected = Math.max(0, shots.findIndex((s) => s.id === shotParam));

  // 派生（视频审批：只有有 videoUrl 的 shot 才算在审批范围内）
  const videoShots = shots.filter((s) => s.videoUrl);
  const approvedCount = isPast ? shots.length : videoShots.filter((s) => s.state === "approved").length;
  const allApproved = isPast || (videoShots.length > 0 && videoShots.length === shots.length && approvedCount === shots.length);

  // 本地 loading 状态
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());
  const [agentTarget, setAgentTarget] = useState<string | null>(null);
  const [scriptSheetOpen, setScriptSheetOpen] = useState(false);
  const [promptSheetOpen, setPromptSheetOpen] = useState(false);
  const [historySheetOpen, setHistorySheetOpen] = useState(false);
  const [videoPromptDraft, setVideoPromptDraft] = useState("");
  const [savingVideoPrompt, setSavingVideoPrompt] = useState(false);
  const [restoringVersion, setRestoringVersion] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watchedVideoTasks, setWatchedVideoTasks] = useState<WatchedVideoTask[]>([]);
  const [ensureAllActive, setEnsureAllActive] = useState(false);
  const autoEnqueueRef = useRef(false);

  // 由后端 running_tasks 派生，刷新后状态自动恢复
  const batchGenerating = episode.runningTasks.includes("gen_shot_video");

  // shot state 变为非 rendering 时，清除本地 loading
  useEffect(() => {
    setLoadingIds((prev) => {
      if (prev.size === 0) return prev;
      const next = new Set(prev);
      for (const id of prev) {
        const shot = shots.find((s) => s.id === id);
        if (!shot || (shot.state !== "rendering" && shot.state !== "planned")) next.delete(id);
      }
      return next.size === prev.size ? prev : next;
    });
  }, [shots]);

  const missingVideoCount = shots.filter((s) => !s.videoUrl).length;
  const warningShotCount = shots.filter((s) => !s.videoUrl && isShotWarning(s)).length;
  const pendingMissingCount = Math.max(0, missingVideoCount - warningShotCount);
  const hasUngenerated = missingVideoCount > 0;
  const shot = shots[selected] ?? shots[0];
  const selectedShotLabel = shot ? shotNumberLabel(selected) : "镜头";
  const submittedPrompt = shot?.submittedPrompt;
  const shotBusy = !!shot && (loadingIds.has(shot.id) || shot.state === "rendering");
  const shotWarn = isShotWarning(shot);
  const shotApproved = !!shot && (isPast || (!!shot.videoUrl && shot.state === "approved"));
  const shotVersions = shot?.versions ?? [];
  const agentShot = agentTarget ? shots.find((s) => s.id === agentTarget) : undefined;
  const agentShotIndex = agentShot ? shots.findIndex((s) => s.id === agentShot.id) : -1;
  const agentShotLabel = agentShotIndex >= 0 ? shotNumberLabel(agentShotIndex) : "镜头";

  const getBatchTargets = useCallback((includeWarningShots: boolean) => {
    return shots.filter((s) => {
      if (s.videoUrl || loadingIds.has(s.id) || s.state === "rendering") return false;
      if (!includeWarningShots && isShotWarning(s)) return false;
      return true;
    });
  }, [loadingIds, shots]);
  const activeVideoWork = batchGenerating
    || watchedVideoTasks.length > 0
    || loadingIds.size > 0
    || shots.some((s) => s.state === "rendering");
  const sourceLineRange = episode.sourceStartLine && episode.sourceEndLine
    ? `L${episode.sourceStartLine}-${episode.sourceEndLine}`
    : "未索引";
  const shotTotalDuration = shots.reduce((sum, item) => sum + (item.duration || 0), 0);
  const displayDuration = shotTotalDuration > 0 ? shotTotalDuration : episode.estimatedDuration;
  const displayDurationText = `${Math.floor(displayDuration / 60)}:${(displayDuration % 60).toString().padStart(2, "0")}`;
  const displayDurationLabel = shotTotalDuration > 0 ? "分镜总时长" : "预估时长";
  const approvalNotReady = shots.length === 0 || shots.some((s) => !s.videoUrl || loadingIds.has(s.id) || s.state === "rendering");
  const generationText = hasUngenerated
    ? `${missingVideoCount} 个分镜尚未生成视频${warningShotCount > 0 ? ` · ${warningShotCount} 个异常` : ""}`
    : "本集镜头视频已全部生成";

  useEffect(() => {
    if (!promptSheetOpen) return;
    setVideoPromptDraft(submittedPrompt || shot?.prompt || "");
  }, [promptSheetOpen, submittedPrompt, shot?.prompt, shot?.id]);

  const watchVideoTask = useCallback((response: ApiGenResponse, task: Omit<WatchedVideoTask, "recordId">) => {
    const recordId = response.record_id;
    if (!recordId) return;
    setWatchedVideoTasks((prev) => {
      if (prev.some((item) => item.recordId === recordId)) return prev;
      return [...prev, { ...task, recordId }];
    });
  }, []);

  const enqueueVideoTargets = useCallback(async (targets: Shot[], mode: "manual" | "auto") => {
    if (targets.length === 0) return 0;
    setLoadingIds((prev) => new Set([...prev, ...targets.map((s) => s.id)]));
    try {
      const response = await generateAPI.episodeShotVideos(episode.id);
      const taskRefs = (response.records ?? []).filter((item) => item.record_id);
      const queuedShotIds = new Set<string>();

      if (taskRefs.length > 0) {
        taskRefs.forEach((item) => {
          const chainShotIds = item.shot_ids?.length ? item.shot_ids : (item.shot_id ? [item.shot_id] : []);
          chainShotIds.forEach((id) => queuedShotIds.add(id));
          const targetShot = shots.find((s) => s.id === chainShotIds[0]);
          const targetIndex = targetShot ? shots.findIndex((s) => s.id === targetShot.id) : -1;
          const targetLabel = item.chain
            ? `${item.segment_code || item.shot_code || "片段"}视频生成`
            : (targetIndex >= 0 ? `${shotNumberLabel(targetIndex)}视频生成` : `${item.shot_code || "镜头"}视频生成`);
          watchVideoTask(
            { task_id: item.task_id, record_id: item.record_id },
            chainShotIds.length > 1
              ? { label: targetLabel, shotIds: chainShotIds }
              : { label: targetLabel, shotId: chainShotIds[0] }
          );
        });
      } else if (response.record_id) {
        targets.forEach((s) => queuedShotIds.add(s.id));
        watchVideoTask(response, { label: "批量视频生成", shotIds: targets.map((s) => s.id) });
      }

      const queuedCount = response.queued ?? queuedShotIds.size ?? taskRefs.length;
      if (queuedCount === 0) {
        const reason = response.reason || "没有新的镜头入队，可能已有镜头正在生成或已生成。";
        setError(mode === "auto" ? `持续补齐暂停：${reason}` : reason);
        setLoadingIds((prev) => {
          const next = new Set(prev);
          targets.forEach((s) => next.delete(s.id));
          return next;
        });
        setEnsureAllActive(false);
        return 0;
      }

      if (queuedShotIds.size > 0) {
        setLoadingIds((prev) => {
          const next = new Set(prev);
          targets.forEach((s) => {
            if (!queuedShotIds.has(s.id)) next.delete(s.id);
          });
          return next;
        });
      }
      return queuedCount;
    } catch (e: unknown) {
      setError(errorMessage(e, mode === "auto" ? "持续补齐失败" : "批量生成失败"));
      setLoadingIds((prev) => {
        const next = new Set(prev);
        targets.forEach((s) => next.delete(s.id));
        return next;
      });
      if (mode === "auto") setEnsureAllActive(false);
      return 0;
    }
  }, [episode.id, shots, watchVideoTask]);

  useEffect(() => {
    if (watchedVideoTasks.length === 0) return;
    let stopped = false;

    const poll = async () => {
      const settled = new Set<string>();
      for (const task of watchedVideoTasks) {
        try {
          const record = await generateAPI.getTask(task.recordId);
          if (record.status === "failed") {
            const msg = record.error || "后端视频生成任务失败，但未返回具体错误。";
            setError(`${task.label}失败：${msg}`);
            setLoadingIds((prev) => {
              if (prev.size === 0) return prev;
              const next = new Set(prev);
              if (task.shotId) next.delete(task.shotId);
              task.shotIds?.forEach((id) => next.delete(id));
              return next;
            });
            settled.add(task.recordId);
          } else if (record.status === "success" || record.status === "cancelled") {
            const failedCount = Number(record.result?.failed ?? 0);
            if (record.status === "success" && failedCount > 0) {
              setError(`${task.label}完成，但 ${failedCount} 个镜头生成异常，已在镜头列表标记警告。`);
            }
            settled.add(task.recordId);
          }
        } catch (err: unknown) {
          setError(`获取视频生成任务状态失败：${errorMessage(err, "请求失败")}`);
        }
      }
      if (!stopped && settled.size > 0) {
        setWatchedVideoTasks((prev) => prev.filter((item) => !settled.has(item.recordId)));
      }
    };

    poll();
    const id = window.setInterval(poll, 2500);
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
  }, [watchedVideoTasks]);

  useEffect(() => {
    if (!ensureAllActive) return;

    const targets = getBatchTargets(false);
    if (targets.length === 0) {
      if (!activeVideoWork) {
        setEnsureAllActive(false);
        if (warningShotCount > 0) {
          setError(`已补齐可继续生成的镜头，${warningShotCount} 个镜头生成异常，请查看警告标识后单独处理。`);
        }
      }
      return;
    }

    if (activeVideoWork || autoEnqueueRef.current) return;
    autoEnqueueRef.current = true;
    const timer = window.setTimeout(() => {
      enqueueVideoTargets(targets, "auto").finally(() => {
        autoEnqueueRef.current = false;
      });
    }, 800);

    return () => {
      window.clearTimeout(timer);
      autoEnqueueRef.current = false;
    };
  }, [activeVideoWork, enqueueVideoTargets, ensureAllActive, getBatchTargets, warningShotCount]);

  const handleBatchGenerate = async () => {
    const targets = getBatchTargets(true);
    if (targets.length === 0) return;
    setEnsureAllActive(true);
    setError(null);
    await enqueueVideoTargets(targets, "manual");
  };

  const handleRegen = async (shotId: string) => {
    setLoadingIds((prev) => new Set([...prev, shotId]));
    setError(null);
    try {
      const target = shots.find((s) => s.id === shotId);
      const targetIndex = target ? shots.findIndex((s) => s.id === target.id) : -1;
      const targetLabel = targetIndex >= 0 ? shotNumberLabel(targetIndex) : "镜头";
      const response = await generateAPI.shotVideo(shotId);
      watchVideoTask(response, { label: `${targetLabel}视频生成`, shotId });
    } catch (e: unknown) {
      setError(errorMessage(e, "重新生成失败"));
      setLoadingIds((prev) => { const n = new Set(prev); n.delete(shotId); return n; });
    }
  };

  const handleApprove = async (shotId: string) => {
    setError(null);
    try {
      await shotAPI.review(projectId, episode.id, shotId, { approved: true });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "审批失败");
    }
  };

  const handleApproveAll = async () => {
    setApproving(true);
    setError(null);
    try {
      const reviews = shots.map((s) => ({ shot_id: s.id, approved: true }));
      await shotAPI.batchReview(projectId, episode.id, reviews);
      await episodeAPI.setStep(projectId, episode.id, "dubbing");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "批量审批失败");
    } finally {
      setApproving(false);
    }
  };

  const handleSaveVideoPrompt = async () => {
    if (!shot) return;
    setSavingVideoPrompt(true);
    setError(null);
    try {
      await shotAPI.update(projectId, episode.id, shot.id, {
        prompt: videoPromptDraft,
        submitted_prompt: videoPromptDraft,
      } as never);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "保存提示词失败");
    } finally {
      setSavingVideoPrompt(false);
    }
  };

  const handleRestoreShotVersion = async (version: string) => {
    if (!shot) return;
    setRestoringVersion(version);
    setError(null);
    try {
      await shotAPI.restoreVersion(projectId, episode.id, shot.id, version);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "回选历史版本失败");
    } finally {
      setRestoringVersion(null);
    }
  };

  return (
    <div className="space-y-2">
      {error && (
        <div className="rounded-xl border border-danger/20 bg-danger-soft px-3 py-2">
          <p className="text-xs text-danger">{error}</p>
        </div>
      )}

      <div className="page-panel tech-border px-3 py-2.5 sm:px-4">
        <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="min-w-0 break-words text-lg font-black text-text sm:text-xl">
                第 {episode.number} 集 · {episode.title}
              </h2>
              <Badge
                variant={allApproved ? "success" : hasUngenerated ? "warning" : "outline"}
                className="shrink-0"
              >
                {allApproved ? "已完成" : hasUngenerated ? "制作中" : "待审批"}
              </Badge>
            </div>
            {episode.summary && (
              <p className="mt-1 line-clamp-1 text-xs text-sub">{episode.summary}</p>
            )}
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] font-semibold text-muted">
              <span className="rounded-md bg-soft px-2 py-0.5">原文 {sourceLineRange}</span>
              <span className="rounded-md bg-soft px-2 py-0.5">对白 {episode.dialogueCount ?? 0}</span>
              {episode.sourceIntegrity && (
                <span className={cn(
                  "rounded-md px-2 py-0.5",
                  episode.sourceIntegrity === "original" ? "bg-brand-soft text-brand" : "bg-warn/10 text-warn"
                )}>
                  {episode.sourceIntegrity === "original" ? "原文完整" : episode.sourceIntegrity}
                </span>
              )}
              <span className={cn(
                "rounded-md px-2 py-0.5",
                hasUngenerated ? "bg-warn/10 text-warn" : "bg-brand-soft text-brand"
              )}>
                {ensureAllActive ? `持续补齐中 · 剩余 ${pendingMissingCount}` : generationText}
              </span>
            </div>
          </div>

          <div className="grid w-full gap-2 sm:grid-cols-[auto_auto_auto] xl:w-auto xl:items-center">
            {episode.scriptExcerpt && (
              <Button size="sm" variant="outline" className="w-full sm:w-auto" onClick={() => setScriptSheetOpen(true)}>
                <FileText className="h-3.5 w-3.5" />查看剧本
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              className="w-full sm:w-auto"
              onClick={() => navigate(`/projects/${projectId}?view=assets`)}
            >
              <Images className="h-3.5 w-3.5" />资产库
            </Button>
            <div className="flex items-center justify-between gap-4 rounded-xl border border-line bg-elev px-3 py-1.5 text-right sm:min-w-[128px]">
              {displayDuration > 0 && (
                <div>
                  <div className="text-base font-black leading-none text-text">{displayDurationText}</div>
                  <div className="mt-0.5 text-[10px] font-semibold text-muted">{displayDurationLabel}</div>
                </div>
              )}
              <div>
                <div className="text-base font-black leading-none text-text">{shots.length}</div>
                <div className="mt-0.5 text-[10px] font-semibold text-muted">分镜数</div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-2 grid gap-2 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div>
            <div className="mb-1 flex items-center justify-between text-[11px] font-semibold">
              <span className="text-muted">审批进度</span>
              <span className={cn("tabular-nums", allApproved ? "text-success" : "text-text")}>
                {approvedCount} / {shots.length}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full bg-gradient-to-r from-signal to-success transition-all duration-500"
                style={{ width: shots.length > 0 ? `${(approvedCount / shots.length) * 100}%` : "0%" }}
              />
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[300px]">
            <Button size="sm" onClick={handleBatchGenerate} disabled={activeVideoWork || ensureAllActive || !hasUngenerated}>
              {activeVideoWork || ensureAllActive ? (
                <><Loader2 className="h-3.5 w-3.5 animate-spin" />生成中… {episode.taskProgress["gen_shot_video"] ? `${episode.taskProgress["gen_shot_video"]}%` : ""}</>
              ) : hasUngenerated ? (
                <><Play className="h-3.5 w-3.5" />生成所有镜头</>
              ) : (
                <><CheckCircle2 className="h-3.5 w-3.5" />已生成全部镜头</>
              )}
            </Button>
            <Button
              size="sm"
              variant={allApproved ? "secondary" : "outline"}
              onClick={handleApproveAll}
              disabled={allApproved || approving || approvalNotReady}
            >
              {approving ? (
                <><Loader2 className="h-3.5 w-3.5 animate-spin" />提交中…</>
              ) : allApproved ? (
                <><Check className="h-3.5 w-3.5" />已全部通过</>
              ) : (
                <><CheckCircle2 className="h-3.5 w-3.5" />全部审批通过</>
              )}
            </Button>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        {/* 中央预览 */}
        {shot && (
          <div className="studio-work-area tech-border p-2.5 sm:p-3">
            <div className="grid items-start gap-3 lg:grid-cols-[minmax(280px,1fr)_minmax(160px,210px)]">
              <div className="min-w-0">
                <div className="mb-2 flex items-center justify-between gap-3 rounded-xl border border-line bg-elev px-3 py-1.5">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-text">{selectedShotLabel}</p>
                    <p className="text-xs text-muted">
                      {shot.segmentName || shot.segmentCode || "未分段"} · {shot.duration}s
                      {shot.shotCode ? ` · 原编号 ${shot.shotCode}` : ""}
                    </p>
                  </div>
                  <Badge variant={shotBusy || shotWarn ? "warning" : shotApproved || shot.videoUrl ? "success" : "outline"} className="shrink-0">
                    {shotBusy ? "生成中" : shotWarn ? "异常" : shotApproved ? "已通过" : shot.videoUrl ? "已生成" : "待生成"}
                  </Badge>
                </div>
                <div className="relative mx-auto mb-2 flex aspect-[9/16] w-full max-w-[300px] items-center justify-center overflow-hidden rounded-2xl border border-line bg-black shadow-lg sm:max-w-[360px] lg:h-[clamp(380px,58vh,650px)] lg:w-auto lg:max-w-full">
                  {shot.videoUrl ? (
                    <LazyVideo src={cosUrl(shot.videoUrl)} className="w-full h-full object-contain rounded-2xl" />
                  ) : (loadingIds.has(shot.id) || shot.state === "rendering") ? (
                    <div className="flex flex-col items-center gap-2">
                      <Loader2 className="w-8 h-8 text-warn animate-spin" />
                      <p className="text-xs text-muted">视频生成中…</p>
                    </div>
                  ) : (
                    <div className="text-center">
                      <Film className="w-10 h-10 text-line mx-auto mb-2" />
                      <p className="text-xs text-muted">尚未生成</p>
                    </div>
                  )}
                  {shotApproved && shot.videoUrl && (
                    <div className="pointer-events-none absolute right-2 top-2 flex items-center gap-1 rounded-full bg-brand/90 px-2 py-1 text-[11px] font-medium text-white shadow-sm">
                      <CheckCircle2 className="w-3 h-3" />
                      已通过
                    </div>
                  )}
                  {shotWarn ? (
                    <div className="pointer-events-none absolute left-2 top-2 flex items-center gap-1 rounded-full bg-warn/95 px-2 py-1 text-[11px] font-medium text-white shadow-sm">
                      <AlertTriangle className="h-3 w-3" />生成异常
                    </div>
                  ) : shotBusy && shot.videoUrl ? (
                    <div className="pointer-events-none absolute left-2 top-2 flex items-center gap-1 rounded-full bg-warn/95 px-2 py-1 text-[11px] font-medium text-white shadow-sm">
                      <Loader2 className="h-3 w-3 animate-spin" />正在生成新版
                    </div>
                  ) : shot.continuityDirty && shot.videoUrl && (
                    <div className="pointer-events-none absolute left-2 top-2 rounded-full bg-warn/95 px-2 py-1 text-[11px] font-medium text-white shadow-sm">
                      连续性需刷新
                    </div>
                  )}
                </div>

                <p className="rounded-xl bg-elev px-3 py-1.5 text-xs text-sub text-center leading-relaxed line-clamp-1">{shot.description}</p>
                {(shotWarn || shot.continuityDirty) && (
                  <p className="mt-1.5 rounded-xl border border-warn/20 bg-warn-soft px-3 py-1.5 text-xs text-warn line-clamp-2">
                    {shotWarn ? shotWarningText(shot) : (shot.continuityDirtyReason || "依赖的上一镜尾帧已变化，建议重新生成本镜头。")}
                  </p>
                )}
              </div>

              <div className="lg:pt-[44px]">
                <div className="rounded-2xl border border-line bg-panel/90 p-2 shadow-xs">
                  <button
                    onClick={() => setPromptSheetOpen(true)}
                    className="mb-1.5 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-line px-2 py-1.5 text-xs text-muted transition-colors hover:border-brand/30 hover:bg-brand-soft hover:text-brand"
                  >
                    <FileText className="w-3.5 h-3.5" />编辑最终提交提示词
                  </button>

                  {!shotBusy ? (
                    <div className="grid grid-cols-2 gap-1.5">
                      <Button
                        size="sm"
                        variant={shot.videoUrl ? "outline" : "default"}
                        className="col-span-2"
                        onClick={() => handleRegen(shot.id)}
                      >
                        {shot.videoUrl ? (
                          <><RefreshCw className="w-3.5 h-3.5" />重新生成</>
                        ) : (
                          <><Play className="w-3.5 h-3.5" />生成视频</>
                        )}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setAgentTarget(shot.id)}>
                        <MessageCircle className="w-3.5 h-3.5" />AI 修改
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setHistorySheetOpen(true)} disabled={shotVersions.length === 0}>
                        <History className="w-3.5 h-3.5" />历史
                      </Button>
                      <Button size="sm" className="col-span-2" onClick={() => handleApprove(shot.id)} disabled={!shot.videoUrl || shotApproved}>
                        <Check className="w-3.5 h-3.5" />{shotApproved ? "已审批" : "审批通过"}
                      </Button>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-warn/25 bg-warn-soft px-3 py-3 text-center text-xs font-medium text-warn">
                      视频生成中…
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

      </div>

      <Sheet
        open={scriptSheetOpen}
        onClose={() => setScriptSheetOpen(false)}
        title={`第 ${episode.number} 集《${episode.title}》· 原始剧本`}
        width="sm:w-[560px]"
      >
        {episode.scriptExcerpt && (
          <pre className="text-xs text-text leading-relaxed whitespace-pre-wrap font-sans">
            {episode.scriptExcerpt}
          </pre>
        )}
      </Sheet>

      <Sheet
        open={promptSheetOpen}
        onClose={() => setPromptSheetOpen(false)}
        title={`${selectedShotLabel} · 最终提交提示词`}
      >
        <div className="space-y-3">
          <Textarea
            value={videoPromptDraft}
            onChange={(e) => setVideoPromptDraft(e.target.value)}
            rows={22}
            className="min-h-[60vh] text-xs leading-relaxed font-sans"
            placeholder="可在这里人工修改视频生成最终提交提示词；保存后重新生成会带入该提示词。"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setPromptSheetOpen(false)}>关闭</Button>
            <Button onClick={handleSaveVideoPrompt} disabled={!shot || savingVideoPrompt}>
              {savingVideoPrompt ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />保存中…</> : <><Check className="w-3.5 h-3.5" />保存提示词</>}
            </Button>
          </div>
        </div>
      </Sheet>

      <Sheet
        open={historySheetOpen}
        onClose={() => setHistorySheetOpen(false)}
        title={`${selectedShotLabel} · 历史版本回选`}
        width="sm:w-[720px]"
      >
        <div className="space-y-4">
          {shot?.videoUrl && (
            <div className="rounded-xl border border-line bg-elev p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium text-sub">当前使用版本</span>
                <Badge variant="success">{shot.version}</Badge>
              </div>
              <div className="mx-auto h-72 aspect-[9/16] max-w-full overflow-hidden rounded-xl bg-black">
                <LazyVideo src={cosUrl(shot.videoUrl)} className="w-full h-full object-contain" />
              </div>
            </div>
          )}

          {shotVersions.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {shotVersions.slice().reverse().map((item) => {
                const isCurrent = item.videoUrl === shot?.videoUrl || item.version === shot?.version;
                return (
                  <div key={item.version} className="rounded-xl border border-line bg-panel p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-text">{item.version}</p>
                        <p className="text-xs text-muted">
                          {item.createdAt ? new Date(item.createdAt).toLocaleString() : "未知时间"}
                        </p>
                      </div>
                      {isCurrent && <Badge variant="success">当前</Badge>}
                    </div>
                    <div className="mx-auto h-64 aspect-[9/16] max-w-full overflow-hidden rounded-lg bg-black">
                      <LazyVideo src={cosUrl(item.videoUrl)} className="w-full h-full object-contain" />
                    </div>
                    {item.description && (
                      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-sub">{item.description}</p>
                    )}
                    <div className="mt-3 flex justify-end">
                      <Button
                        size="sm"
                        variant={isCurrent ? "secondary" : "outline"}
                        onClick={() => handleRestoreShotVersion(item.version)}
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
        </div>
      </Sheet>

      {agentTarget && (
        <AgentDialog
          open={!!agentTarget}
          onOpenChange={(v) => !v && setAgentTarget(null)}
          targetType="shot_video"
          targetId={agentTarget}
          projectId={projectId}
          title="AI 修改 · 镜头视频"
          initialPrompt={`${agentShotLabel}：${agentShot?.prompt || agentShot?.description || ""}`}
        />
      )}
    </div>
  );
}

// ─── Step 4：配音 ────────────────────────────────────────────

function StepDubbing({ episode, projectId, isPast }: { episode: EpisodeDetail; projectId: string; isPast?: boolean }) {
  const [advancing, setAdvancing] = useState(false);

  const handleSkip = async () => {
    setAdvancing(true);
    try {
      await episodeAPI.setStep(projectId, episode.id, "merge");
    } finally {
      setAdvancing(false);
    }
  };

  return (
    <div className="page-panel tech-border flex flex-col items-center justify-center py-20 gap-4">
      <div className="w-14 h-14 rounded-2xl bg-soft flex items-center justify-center">
        <Volume2 className="w-7 h-7 text-muted" />
      </div>
      <div className="text-center">
        <p className="font-medium text-text">配音功能开发中</p>
        <p className="text-sm text-sub mt-1 max-w-sm">
          配音模块尚未上线，敬请期待。当前共 {episode.shots.length} 个分镜待配音。
        </p>
      </div>
      {!isPast && (
        <Button variant="outline" onClick={handleSkip} disabled={advancing}>
          {advancing ? <><Loader2 className="w-4 h-4 animate-spin" />跳过中…</> : "跳过配音，进入合并"}
        </Button>
      )}
    </div>
  );
}

// ─── Step 5：合并 ────────────────────────────────────────────

function StepMerge({
  episode, projectId, isPast,
}: { episode: EpisodeDetail; projectId: string; isPast?: boolean }) {
  // 派生：finalVideoUrl 存在说明合并完成
  const done = !!episode.finalVideoUrl;
  // 由后端 running_tasks 派生，刷新后状态自动恢复
  const merging = episode.runningTasks.includes("merge_episode");

  const [progress, setProgress] = useState(done ? 100 : 0);
  const [error, setError] = useState<string | null>(null);
  const animTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startProgressAnim = () => {
    let p = 0;
    animTimerRef.current = setInterval(() => {
      p = Math.min(p + 3, 90);
      setProgress(p);
    }, 500);
  };

  const stopProgressAnim = () => {
    if (animTimerRef.current) {
      clearInterval(animTimerRef.current);
      animTimerRef.current = null;
    }
  };

  // merging 变为 true 时启动进度动画；变为 false 或完成时停止
  useEffect(() => {
    if (merging) {
      startProgressAnim();
    } else {
      stopProgressAnim();
      if (done) setProgress(100);
    }
    return stopProgressAnim;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [merging, done]);

  useEffect(() => () => stopProgressAnim(), []);

  const handleMerge = async () => {
    setError(null);
    try {
      await generateAPI.mergeEpisode(episode.id);
      // merging 状态由轮询驱动，无需本地管理
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "合并失败");
    }
  };

  const totalDuration = episode.shots.reduce((s, sh) => s + sh.duration, 0);
  const m = Math.floor(totalDuration / 60);
  const sec = totalDuration % 60;
  const missingVideoCount = episode.shots.filter((shot) => !shot.videoUrl).length;
  const unapprovedCount = episode.shots.filter((shot) => shot.videoUrl && shot.state !== "approved").length;
  const canMerge = episode.shots.length > 0 && missingVideoCount === 0 && unapprovedCount === 0;
  const mergeBlockedText = missingVideoCount > 0
    ? `还有 ${missingVideoCount} 个镜头未生成视频，生成完成后才能合并。`
    : unapprovedCount > 0
      ? `还有 ${unapprovedCount} 个镜头未审批通过，审批完成后才能合并。`
      : "当前分集还没有分镜，无法合并。";

  return (
    <div className="page-panel max-w-md mx-auto p-8">
      <div className="text-center mb-8">
        <div className="w-16 h-16 rounded-2xl bg-brand-soft flex items-center justify-center mx-auto mb-4">
          <Film className="w-8 h-8 text-brand" />
        </div>
        <h3 className="text-lg font-semibold text-text">合并成片</h3>
        <p className="text-sm text-sub mt-1">
          共 {episode.shots.length} 个分镜，预估时长 {m}:{sec.toString().padStart(2, "0")}
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-danger/20 bg-danger-soft p-3 text-center">
          <p className="text-xs text-danger">{error}</p>
        </div>
      )}

      {done ? (
        <div className="text-center">
          <CheckCircle2 className="w-12 h-12 text-brand mx-auto mb-3" />
          <p className="font-medium text-text">合并完成！</p>
          <p className="text-sm text-sub mt-1">可前往「完成」步骤查看成片。</p>
        </div>
      ) : merging ? (
        <div>
          <div className="h-2 bg-soft rounded-full overflow-hidden mb-2">
            <div className="h-full bg-brand transition-all duration-500 rounded-full" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-xs text-center text-muted">合并中 {progress}%</p>
        </div>
      ) : (
        <div className="space-y-4">
          {!canMerge && (
            <div className="rounded-xl border border-warn/20 bg-warn-soft px-3 py-2 text-center">
              <p className="text-xs text-warn">{mergeBlockedText}</p>
            </div>
          )}
          <div className="flex justify-center">
            <Button onClick={handleMerge} disabled={!canMerge}>
              开始合并
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Step 6：完成 ────────────────────────────────────────────

function StepDone({ episode, projectId }: { episode: EpisodeDetail; projectId: string }) {
  const { cosUrl } = useCos();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const totalDuration = episode.shots.reduce((s, sh) => s + sh.duration, 0);
  const m = Math.floor(totalDuration / 60);
  const sec = totalDuration % 60;
  const unresolvedShots = episode.shots.filter((shot) => !shot.videoUrl || shot.state !== "approved").length;
  const repairStep: EpisodeStep = unresolvedShots > 0 ? "storyboard_videos" : "merge";

  const goToRepairStep = () => {
    const params = new URLSearchParams(searchParams);
    params.set("episode", episode.id);
    params.set("step", repairStep);
    navigate(`/projects/${projectId}?${params.toString()}`);
  };

  return (
    <div className="page-panel max-w-md mx-auto p-8 text-center">
      {episode.finalVideoUrl ? (
        <CheckCircle2 className="w-16 h-16 text-brand mx-auto mb-4" />
      ) : (
        <AlertTriangle className="w-16 h-16 text-warn mx-auto mb-4" />
      )}
      <h3 className="text-xl font-semibold text-text mb-1">
        {episode.finalVideoUrl ? `第 ${episode.number} 集制作完成` : `第 ${episode.number} 集成片缺失`}
      </h3>
      <p className="text-sm text-sub mb-6">
        {episode.finalVideoUrl
          ? episode.title
          : unresolvedShots > 0
            ? `${episode.title} · 还有 ${unresolvedShots} 个镜头未生成或未审批`
            : `${episode.title} · 需要重新合并成片`
        }
      </p>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="metric-tile">
          <div className="text-lg font-semibold text-text">{episode.shots.length}</div>
          <div className="text-xs text-muted mt-0.5">分镜数</div>
        </div>
        <div className="metric-tile">
          <div className="text-lg font-semibold text-text">{m}:{sec.toString().padStart(2, "0")}</div>
          <div className="text-xs text-muted mt-0.5">时长</div>
        </div>
        <div className="metric-tile">
          <div className="text-lg font-semibold text-text">100%</div>
          <div className="text-xs text-muted mt-0.5">完成度</div>
        </div>
      </div>

      {episode.finalVideoUrl ? (
        <div className="mb-6 max-w-[200px] aspect-[9/16] mx-auto rounded-2xl border border-line overflow-hidden bg-black">
          <LazyVideo src={cosUrl(episode.finalVideoUrl)} className="w-full h-full object-contain rounded-2xl" />
        </div>
      ) : (
        <div className="aspect-[9/16] max-w-[160px] mx-auto bg-soft rounded-2xl border border-line flex items-center justify-center mb-6">
          <div className="text-center">
            <Play className="w-8 h-8 text-muted mx-auto mb-1" />
            <p className="text-xs text-muted">暂无成片</p>
          </div>
        </div>
      )}

      {episode.finalVideoUrl ? (
        <a href={cosUrl(episode.finalVideoUrl)} download target="_blank" rel="noreferrer">
          <Button>下载成片</Button>
        </a>
      ) : (
        <Button onClick={goToRepairStep}>
          {unresolvedShots > 0 ? "返回分镜视频" : "返回合并"}
        </Button>
      )}
    </div>
  );
}

// ─── 主组件 ───────────────────────────────────────────────────

export default function StepContent({ step, episode, projectId }: StepContentProps) {
  const isPast = calcIsPastStep(step, episode.currentStep);

  const stepComponents: Record<EpisodeStep, React.ReactNode> = {
    storyboard_script: <StepScript episode={episode} projectId={projectId} isPast={isPast} />,
    storyboard_videos: <StepVideos episode={episode} projectId={projectId} isPast={isPast} />,
    dubbing:           <StepDubbing episode={episode} projectId={projectId} isPast={isPast} />,
    merge:             <StepMerge episode={episode} projectId={projectId} isPast={isPast} />,
    done:              <StepDone episode={episode} projectId={projectId} />,
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {stepComponents[step]}
    </div>
  );
}

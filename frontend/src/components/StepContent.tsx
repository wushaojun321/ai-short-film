import { useState } from "react";
import {
  CheckCircle2, RefreshCw, Loader2, Play, Volume2,
  Film, Layers, Clock, Tag, Edit3, Check, MessageSquare,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { EpisodeStep, EpisodeDetail, Shot, ShotState } from "@/lib/data";
import { cn } from "@/lib/utils";

interface StepContentProps {
  step: EpisodeStep;
  episode: EpisodeDetail;
}

// ─── 分镜状态配置 ────────────────────────────────────────────

const shotStateCfg: Record<ShotState, {
  label: string;
  variant: "success" | "warning" | "secondary" | "outline";
}> = {
  approved:    { label: "已通过",   variant: "success" },
  rendered:    { label: "待审批",   variant: "warning" },
  asset_ready: { label: "资产就绪", variant: "secondary" },
  planned:     { label: "待生成",   variant: "outline" },
};

// ─── 共用：重新生成意见弹窗 ──────────────────────────────────

interface RegenerateDialogProps {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  onConfirm: (feedback: string) => void;
  loading?: boolean;
}

function RegenerateDialog({
  open, title, description, onClose, onConfirm, loading,
}: RegenerateDialogProps) {
  const [feedback, setFeedback] = useState("");

  const handleConfirm = () => {
    onConfirm(feedback);
    setFeedback("");
  };

  const handleClose = () => {
    if (!loading) {
      setFeedback("");
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="py-2">
          <label className="text-xs font-medium text-sub mb-1.5 block">
            修改意见 / 重新生成要求
          </label>
          <Textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="请描述需要调整的方向，AI 将参考此意见重新生成…"
            rows={4}
            autoFocus
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={loading}>取消</Button>
          <Button onClick={handleConfirm} disabled={loading || !feedback.trim()}>
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" />生成中…</> : "确认重新生成"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── 顶部审批操作栏 ──────────────────────────────────────────

interface ApprovalBarProps {
  approved: number;
  total: number;
  onApproveAll: () => void;
  onRegenerate?: () => void;
  regenerateLabel?: string;
  allApproved?: boolean;
}

function ApprovalBar({
  approved, total, onApproveAll, onRegenerate, regenerateLabel, allApproved,
}: ApprovalBarProps) {
  return (
    <div className="flex items-center gap-4 mb-5 py-3 px-4 bg-soft rounded-xl border border-line">
      {/* 进度 */}
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-sub">审批进度</span>
          <span className={cn(
            "text-xs font-bold tabular-nums",
            approved === total ? "text-brand" : "text-text"
          )}>
            {approved} / {total}
          </span>
        </div>
        <div className="h-1.5 bg-line rounded-full overflow-hidden">
          <div
            className="h-full bg-brand rounded-full transition-all duration-500"
            style={{ width: total > 0 ? `${(approved / total) * 100}%` : "0%" }}
          />
        </div>
      </div>
      {/* 操作 */}
      <div className="flex items-center gap-2 shrink-0">
        {onRegenerate && (
          <Button size="sm" variant="outline" onClick={onRegenerate}>
            <RefreshCw className="w-3.5 h-3.5" />
            {regenerateLabel ?? "打回重新生成"}
          </Button>
        )}
        <Button
          size="sm"
          onClick={onApproveAll}
          disabled={allApproved}
        >
          {allApproved ? (
            <><Check className="w-3.5 h-3.5" />已全部通过</>
          ) : (
            <><CheckCircle2 className="w-3.5 h-3.5" />全部审批通过</>
          )}
        </Button>
      </div>
    </div>
  );
}

// ─── Step 1：分镜脚本 ────────────────────────────────────────

function StepScript({ episode }: { episode: EpisodeDetail }) {
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(episode.shots.length > 0);
  const [shots, setShots] = useState(episode.shots);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [regenDialog, setRegenDialog] = useState(false);
  const [regenLoading, setRegenLoading] = useState(false);
  const [approved, setApproved] = useState(false);

  const handleGenerate = () => {
    setGenerating(true);
    setTimeout(() => {
      setGenerating(false);
      setGenerated(true);
    }, 1800);
  };

  const handleStartEdit = (shot: Shot) => {
    setEditingId(shot.id);
    setEditText(shot.description);
  };

  const handleSaveEdit = (id: string) => {
    setShots((prev) => prev.map((s) => s.id === id ? { ...s, description: editText } : s));
    setEditingId(null);
  };

  const handleRegen = (feedback: string) => {
    setRegenLoading(true);
    setTimeout(() => {
      // Mock：轻微更新描述模拟重新生成
      setShots((prev) => prev.map((s) => ({
        ...s,
        description: s.description + "（已按意见调整）",
        version: `v${parseInt(s.version.replace("v", "") || "1") + 1}`,
      })));
      setRegenLoading(false);
      setRegenDialog(false);
      setApproved(false);
    }, 2200);
  };

  const handleApproveAll = () => setApproved(true);

  // 空状态：未生成
  if (!generated) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-14 h-14 rounded-full bg-soft flex items-center justify-center">
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
        <Button onClick={handleGenerate} disabled={generating}>
          {generating
            ? <><Loader2 className="w-4 h-4 animate-spin" />生成中…</>
            : "生成分镜脚本"}
        </Button>
      </div>
    );
  }

  return (
    <div>
      {/* 连续性约束提示 */}
      {episode.continuityNotes && (
        <div className="mb-4 rounded-xl border border-warn/30 bg-warn-soft p-3">
          <span className="text-xs font-semibold text-warn">连续性约束：</span>
          <span className="text-xs text-warn/80 ml-1">{episode.continuityNotes}</span>
        </div>
      )}

      {/* 审批操作栏 */}
      <ApprovalBar
        approved={approved ? shots.length : 0}
        total={shots.length}
        onApproveAll={handleApproveAll}
        onRegenerate={() => setRegenDialog(true)}
        regenerateLabel="打回重新生成"
        allApproved={approved}
      />

      {/* 脚本列表 */}
      <div className="space-y-3">
        {shots.map((shot, idx) => {
          const cfg = shotStateCfg[shot.state];
          const isEditing = editingId === shot.id;

          return (
            <div
              key={shot.id}
              className={cn(
                "border rounded-xl p-4 bg-white transition-all",
                approved ? "border-brand/30" : "border-line hover:shadow-card",
              )}
            >
              <div className="flex items-start gap-3">
                {/* 序号 */}
                <div className="w-8 h-8 rounded-lg bg-soft flex items-center justify-center text-xs font-semibold text-sub shrink-0">
                  {idx + 1}
                </div>

                <div className="flex-1 min-w-0">
                  {/* 顶部信息行 */}
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <span className="text-sm font-medium text-text">镜头 {shot.id}</span>
                    <Badge variant={approved ? "success" : cfg.variant}>
                      {approved ? "已通过" : cfg.label}
                    </Badge>
                    <span className="flex items-center gap-1 text-xs text-muted">
                      <Clock className="w-3 h-3" />{shot.duration}s
                    </span>
                    <span className="text-xs text-muted">{shot.version}</span>
                  </div>

                  {/* 描述（可编辑） */}
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
                    <div className="group/desc flex items-start gap-2">
                      <p className="text-xs text-sub leading-relaxed flex-1">{shot.description}</p>
                      {!approved && (
                        <button
                          onClick={() => handleStartEdit(shot)}
                          className="opacity-0 group-hover/desc:opacity-100 transition-opacity shrink-0 p-1 rounded hover:bg-soft text-muted hover:text-primary"
                          title="编辑描述"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  )}

                  {/* 资产标签 */}
                  {shot.assets.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {shot.assets.map((a) => (
                        <span key={a} className="flex items-center gap-1 text-xs bg-soft text-sub px-2 py-0.5 rounded-full">
                          <Tag className="w-2.5 h-2.5" />{a}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 打回重新生成弹窗 */}
      <RegenerateDialog
        open={regenDialog}
        title="打回重新生成分镜脚本"
        description="AI 将重新生成本集全部分镜脚本，请描述需要调整的方向。"
        onClose={() => setRegenDialog(false)}
        onConfirm={handleRegen}
        loading={regenLoading}
      />

      {/* 全局生成中遮罩 */}
      {regenLoading && (
        <div className="fixed inset-0 bg-white/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl shadow-lg p-8 flex flex-col items-center gap-4">
            <Loader2 className="w-10 h-10 text-brand animate-spin" />
            <p className="text-sm font-medium text-text">AI 正在重新生成分镜脚本…</p>
            <p className="text-xs text-muted">请稍候，通常需要 10–30 秒</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Step 2：分镜剧照（含审批）────────────────────────────────

function StepImages({ episode }: { episode: EpisodeDetail }) {
  const [shots, setShots] = useState(
    episode.shots.map((s) => ({
      ...s,
      imageApproved: s.state === "approved",
      loadingRegen: false,
    }))
  );
  const [regenTarget, setRegenTarget] = useState<string | null>(null);
  const [allApproved, setAllApproved] = useState(false);

  const approvedCount = shots.filter((s) => s.imageApproved || allApproved).length;

  const handleRegen = (shotId: string, _feedback: string) => {
    setShots((prev) => prev.map((s) =>
      s.id === shotId ? { ...s, loadingRegen: true } : s
    ));
    setRegenTarget(null);
    setTimeout(() => {
      setShots((prev) => prev.map((s) =>
        s.id === shotId
          ? { ...s, loadingRegen: false, imageUrl: s.imageUrl ?? "/previews/regen.svg", imageApproved: false }
          : s
      ));
    }, 1800);
  };

  const handleApprove = (shotId: string) => {
    setShots((prev) => prev.map((s) =>
      s.id === shotId ? { ...s, imageApproved: true } : s
    ));
  };

  const handleApproveAll = () => setAllApproved(true);

  return (
    <div>
      <ApprovalBar
        approved={approvedCount}
        total={shots.length}
        onApproveAll={handleApproveAll}
        allApproved={allApproved}
      />

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
        {shots.map((shot, idx) => {
          const isApproved = shot.imageApproved || allApproved;

          return (
            <div key={shot.id} className={cn(
              "border rounded-xl overflow-hidden transition-all",
              isApproved ? "border-brand/40" : "border-line",
            )}>
              {/* 图片预览区 */}
              <div className="aspect-[9/16] bg-soft relative">
                {shot.loadingRegen ? (
                  <div className="w-full h-full flex items-center justify-center">
                    <Loader2 className="w-6 h-6 text-brand animate-spin" />
                  </div>
                ) : shot.imageUrl ? (
                  <div className="w-full h-full bg-gradient-to-br from-soft to-line flex items-center justify-center relative">
                    <span className="text-xs text-muted">镜头 {idx + 1}</span>
                    {isApproved && (
                      <div className="absolute inset-0 bg-brand/10 flex items-center justify-center">
                        <CheckCircle2 className="w-10 h-10 text-brand drop-shadow" />
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="w-full h-full flex items-center justify-center flex-col gap-1">
                    <Film className="w-5 h-5 text-line" />
                    <span className="text-2xs text-muted">待生成</span>
                  </div>
                )}
                {/* 序号 badge */}
                <div className="absolute top-2 left-2">
                  <span className="text-xs bg-black/50 text-white rounded px-1.5 py-0.5">{idx + 1}</span>
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="p-2 flex gap-1.5">
                <button
                  onClick={() => !isApproved && setRegenTarget(shot.id)}
                  disabled={isApproved || shot.loadingRegen}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-medium transition-colors",
                    isApproved
                      ? "bg-soft text-muted cursor-not-allowed"
                      : "bg-soft text-sub hover:bg-warn-soft hover:text-warn"
                  )}
                >
                  <RefreshCw className="w-3 h-3" />重新生成
                </button>
                <button
                  onClick={() => !isApproved && handleApprove(shot.id)}
                  disabled={isApproved || !shot.imageUrl || shot.loadingRegen}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-medium transition-colors",
                    isApproved
                      ? "bg-brand/10 text-brand cursor-default"
                      : !shot.imageUrl
                        ? "bg-soft text-muted cursor-not-allowed"
                        : "bg-soft text-sub hover:bg-brand/10 hover:text-brand"
                  )}
                >
                  <Check className="w-3 h-3" />通过
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* 重新生成弹窗 */}
      <RegenerateDialog
        open={!!regenTarget}
        title={`重新生成镜头 ${regenTarget ?? ""} 剧照`}
        description="请描述需要调整的方向，AI 将仅重新生成此镜头的剧照。"
        onClose={() => setRegenTarget(null)}
        onConfirm={(feedback) => regenTarget && handleRegen(regenTarget, feedback)}
      />
    </div>
  );
}

// ─── Step 3：分镜视频（含审批）──────────────────────────────

function StepVideos({ episode }: { episode: EpisodeDetail }) {
  const [selected, setSelected] = useState(0);
  const [shots, setShots] = useState(
    episode.shots.map((s) => ({
      ...s,
      videoApproved: s.state === "approved",
      videoGenerated: !!s.videoUrl,
      loadingRegen: false,
    }))
  );
  const [regenTarget, setRegenTarget] = useState<string | null>(null);
  const [allApproved, setAllApproved] = useState(false);

  const approvedCount = shots.filter((s) => s.videoApproved || allApproved).length;
  const shot = shots[selected];

  const handleRegen = (shotId: string, _feedback: string) => {
    setShots((prev) => prev.map((s) =>
      s.id === shotId ? { ...s, loadingRegen: true } : s
    ));
    setRegenTarget(null);
    setTimeout(() => {
      setShots((prev) => prev.map((s) =>
        s.id === shotId
          ? { ...s, loadingRegen: false, videoGenerated: true, videoApproved: false }
          : s
      ));
    }, 2000);
  };

  const handleApprove = (shotId: string) => {
    setShots((prev) => prev.map((s) =>
      s.id === shotId ? { ...s, videoApproved: true } : s
    ));
  };

  const handleApproveAll = () => setAllApproved(true);

  return (
    <div>
      <ApprovalBar
        approved={approvedCount}
        total={shots.length}
        onApproveAll={handleApproveAll}
        allApproved={allApproved}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* 左侧列表 */}
        <div className="space-y-1.5 lg:col-span-1">
          {shots.map((s, idx) => {
            const isApproved = s.videoApproved || allApproved;
            return (
              <button
                key={s.id}
                onClick={() => setSelected(idx)}
                className={cn(
                  "w-full flex items-center gap-3 p-2.5 rounded-xl border text-left transition-all",
                  selected === idx ? "border-primary bg-primary-soft" : "border-line hover:bg-soft"
                )}
              >
                {/* 缩略图 */}
                <div className="w-10 h-14 rounded-lg bg-soft shrink-0 flex items-center justify-center border border-line overflow-hidden">
                  {s.loadingRegen ? (
                    <Loader2 className="w-4 h-4 text-brand animate-spin" />
                  ) : s.videoGenerated ? (
                    <div className="w-full h-full bg-gradient-to-b from-soft to-line flex items-center justify-center">
                      <Play className="w-3 h-3 text-sub" />
                    </div>
                  ) : (
                    <Film className="w-4 h-4 text-line" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-text truncate">镜头 {s.id}</div>
                  <div className="text-xs text-muted mt-0.5">{s.duration}s</div>
                </div>
                {/* 状态图标 */}
                {isApproved ? (
                  <CheckCircle2 className="w-4 h-4 text-brand shrink-0" />
                ) : s.videoGenerated ? (
                  <div className="w-1.5 h-1.5 rounded-full bg-warn shrink-0" />
                ) : (
                  <div className="w-1.5 h-1.5 rounded-full bg-line shrink-0" />
                )}
              </button>
            );
          })}
        </div>

        {/* 右侧预览 */}
        <div className="lg:col-span-2">
          {shot && (
            <div>
              {/* 视频预览 */}
              <div className="aspect-[9/16] max-w-xs mx-auto bg-soft rounded-2xl border border-line flex items-center justify-center mb-4 relative overflow-hidden">
                {shot.loadingRegen ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-8 h-8 text-brand animate-spin" />
                    <p className="text-xs text-muted">重新生成中…</p>
                  </div>
                ) : shot.videoGenerated ? (
                  <div className="w-full h-full bg-gradient-to-b from-slate-800 to-slate-900 flex items-center justify-center">
                    <div className="text-center">
                      <Play className="w-12 h-12 text-white/60 mx-auto mb-2" />
                      <p className="text-xs text-white/40">镜头 {selected + 1} 预览</p>
                    </div>
                  </div>
                ) : (
                  <div className="text-center">
                    <Film className="w-10 h-10 text-line mx-auto mb-2" />
                    <p className="text-xs text-muted">尚未生成</p>
                  </div>
                )}
                {/* 通过标记遮罩 */}
                {(shot.videoApproved || allApproved) && (
                  <div className="absolute inset-0 bg-brand/20 flex items-center justify-center">
                    <CheckCircle2 className="w-14 h-14 text-brand drop-shadow-lg" />
                  </div>
                )}
              </div>

              {/* 描述 */}
              <div className="max-w-xs mx-auto">
                <p className="text-xs text-sub text-center mb-4 px-2 leading-relaxed">{shot.description}</p>

                {/* 操作按钮 */}
                {!(shot.videoApproved || allApproved) && (
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => setRegenTarget(shot.id)}
                      disabled={shot.loadingRegen}
                    >
                      <RefreshCw className="w-4 h-4" />重新生成
                    </Button>
                    <Button
                      className="flex-1"
                      onClick={() => handleApprove(shot.id)}
                      disabled={!shot.videoGenerated || shot.loadingRegen}
                    >
                      <Check className="w-4 h-4" />审批通过
                    </Button>
                  </div>
                )}
                {(shot.videoApproved || allApproved) && (
                  <div className="flex justify-center">
                    <Badge variant="success" className="text-sm px-4 py-1.5">
                      <CheckCircle2 className="w-4 h-4 mr-1.5" />已审批通过
                    </Badge>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 重新生成弹窗 */}
      <RegenerateDialog
        open={!!regenTarget}
        title={`重新生成镜头 ${regenTarget ?? ""} 视频`}
        description="请描述需要调整的方向，AI 将仅重新生成此镜头的视频。"
        onClose={() => setRegenTarget(null)}
        onConfirm={(feedback) => regenTarget && handleRegen(regenTarget, feedback)}
      />
    </div>
  );
}

// ─── Step 4：配音 ────────────────────────────────────────────

function StepDubbing({ episode }: { episode: EpisodeDetail }) {
  const [generating, setGenerating] = useState(false);
  const [done, setDone] = useState(false);

  return (
    <div>
      <div className="rounded-xl border border-line p-4 mb-6 bg-soft">
        <p className="text-xs font-semibold text-sub mb-3">音色设定</p>
        <div className="grid grid-cols-2 gap-3">
          {[
            { name: "李云湘", voice: "冷静、低缓、克制、威压感强" },
            { name: "谢风凌", voice: "低沉、克制、寡言" },
            { name: "顾文池", voice: "温柔、带笑意、轻讽" },
            { name: "李睿",   voice: "平静、贵气、藏锋" },
          ].map((c) => (
            <div key={c.name} className="bg-white rounded-lg border border-line p-3">
              <div className="text-xs font-medium text-text">{c.name}</div>
              <div className="text-xs text-muted mt-0.5">{c.voice}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-sub">AI 将按音色设定自动生成各角色配音。</p>
        <Button
          size="sm"
          onClick={() => { setGenerating(true); setTimeout(() => { setGenerating(false); setDone(true); }, 2000); }}
          disabled={generating || done}
        >
          {generating
            ? <><Loader2 className="w-4 h-4 animate-spin" />配音中</>
            : done ? "配音完成" : "开始配音"}
        </Button>
      </div>

      <div className="space-y-2">
        {episode.shots.slice(0, 5).map((shot, idx) => (
          <div key={shot.id} className="flex items-center gap-4 p-3 rounded-xl border border-line bg-white">
            <div className="w-8 h-8 rounded-full bg-soft flex items-center justify-center">
              <Volume2 className="w-4 h-4 text-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate">镜头 {idx + 1} · {shot.duration}s</div>
            </div>
            {done
              ? <Badge variant="success">已配音</Badge>
              : <Badge variant="secondary">待配音</Badge>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Step 5：合并 ────────────────────────────────────────────

function StepMerge({ episode }: { episode: EpisodeDetail }) {
  const [merging, setMerging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);

  const handleMerge = () => {
    setMerging(true);
    let p = 0;
    const timer = setInterval(() => {
      p += 10;
      setProgress(p);
      if (p >= 100) {
        clearInterval(timer);
        setMerging(false);
        setDone(true);
      }
    }, 200);
  };

  const totalDuration = episode.shots.reduce((s, sh) => s + sh.duration, 0);
  const m = Math.floor(totalDuration / 60);
  const sec = totalDuration % 60;

  return (
    <div className="max-w-md mx-auto py-8">
      <div className="text-center mb-8">
        <div className="w-16 h-16 rounded-full bg-brand-soft flex items-center justify-center mx-auto mb-4">
          <Film className="w-8 h-8 text-brand" />
        </div>
        <h3 className="text-lg font-semibold text-text">合并成片</h3>
        <p className="text-sm text-sub mt-1">
          共 {episode.shots.length} 个分镜，预估时长 {m}:{sec.toString().padStart(2, "0")}
        </p>
      </div>

      {done ? (
        <div className="text-center">
          <CheckCircle2 className="w-12 h-12 text-brand mx-auto mb-3" />
          <p className="font-medium text-text">合并完成！</p>
          <p className="text-sm text-sub mt-1">可前往「完成」步骤查看成片。</p>
        </div>
      ) : merging ? (
        <div>
          <div className="h-2 bg-soft rounded-full overflow-hidden mb-2">
            <div
              className="h-full bg-brand transition-all duration-200 rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-center text-muted">合并中 {progress}%</p>
        </div>
      ) : (
        <div className="flex justify-center">
          <Button onClick={handleMerge}>开始合并</Button>
        </div>
      )}
    </div>
  );
}

// ─── Step 6：完成 ────────────────────────────────────────────

function StepDone({ episode }: { episode: EpisodeDetail }) {
  const totalDuration = episode.shots.reduce((s, sh) => s + sh.duration, 0);
  const m = Math.floor(totalDuration / 60);
  const sec = totalDuration % 60;

  return (
    <div className="max-w-md mx-auto py-8 text-center">
      <CheckCircle2 className="w-16 h-16 text-brand mx-auto mb-4" />
      <h3 className="text-xl font-semibold text-text mb-1">
        第 {episode.number} 集制作完成
      </h3>
      <p className="text-sm text-sub mb-6">{episode.title}</p>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="border border-line rounded-xl p-4">
          <div className="text-lg font-semibold text-text">{episode.shots.length}</div>
          <div className="text-xs text-muted mt-0.5">分镜数</div>
        </div>
        <div className="border border-line rounded-xl p-4">
          <div className="text-lg font-semibold text-text">{m}:{sec.toString().padStart(2, "0")}</div>
          <div className="text-xs text-muted mt-0.5">时长</div>
        </div>
        <div className="border border-line rounded-xl p-4">
          <div className="text-lg font-semibold text-text">100%</div>
          <div className="text-xs text-muted mt-0.5">完成度</div>
        </div>
      </div>

      <div className="aspect-[9/16] max-w-[160px] mx-auto bg-soft rounded-2xl border border-line flex items-center justify-center mb-6">
        <div className="text-center">
          <Play className="w-8 h-8 text-muted mx-auto mb-1" />
          <p className="text-xs text-muted">成片预览</p>
        </div>
      </div>

      <Button>下载成片</Button>
    </div>
  );
}

// ─── 主组件 ───────────────────────────────────────────────────

export default function StepContent({ step, episode }: StepContentProps) {
  const stepComponents: Record<EpisodeStep, React.ReactNode> = {
    storyboard_script:  <StepScript episode={episode} />,
    storyboard_images:  <StepImages episode={episode} />,
    storyboard_videos:  <StepVideos episode={episode} />,
    dubbing:            <StepDubbing episode={episode} />,
    merge:              <StepMerge episode={episode} />,
    done:               <StepDone episode={episode} />,
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      {stepComponents[step]}
    </div>
  );
}

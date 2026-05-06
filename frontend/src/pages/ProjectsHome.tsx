import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle, CheckCircle2, ChevronRight, Clock,
  Layers, Loader2, Play, Plus, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Project } from "@/lib/data";
import { projectAPI } from "@/lib/api";
import { useProjects } from "@/lib/ProjectsContext";
import { cn } from "@/lib/utils";

const initStatusConfig: Record<Project["initStatus"], {
  label: string;
  variant: "success" | "warning" | "secondary" | "outline" | "primary";
  dot: string;
}> = {
  initialized:        { label: "制作中",   variant: "success",  dot: "bg-success" },
  assets_confirmed:   { label: "资产审核", variant: "warning",  dot: "bg-warn animate-pulse" },
  episodes_confirmed: { label: "分集规划", variant: "warning",  dot: "bg-warn animate-pulse" },
  script_uploaded:    { label: "待解析",   variant: "secondary",dot: "bg-slate-400" },
  not_started:        { label: "未初始化", variant: "outline",  dot: "bg-slate-300" },
};

function ProjectCard({ project }: { project: Project }) {
  const navigate = useNavigate();
  const { reload } = useProjects();
  const cfg = initStatusConfig[project.initStatus];
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDelete = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await projectAPI.delete(project.id);
      setDeleteOpen(false);
      reload();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "删除项目失败，请稍后重试");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <div
        onClick={() => navigate(`/projects/${project.id}`)}
        className={cn(
          "group media-card tech-border relative flex h-full min-h-[300px] cursor-pointer flex-col overflow-hidden p-4 sm:min-h-[328px]",
          "animate-fade-in"
        )}
      >
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary via-signal to-transparent opacity-80" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_24%_0%,rgba(52,211,153,0.08),transparent_30%),linear-gradient(135deg,rgba(255,255,255,0.040),transparent_38%)] opacity-70 transition-opacity duration-200 group-hover:opacity-100" />
        <div className="relative mb-4 min-h-[104px]">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-xs ring-1 ring-white/10",
              project.initStatus === "initialized"
                ? "bg-primary text-white shadow-brand"
                : "bg-soft text-sub"
            )}>
              <Play className="w-4 h-4" />
            </div>

            <div className="flex min-w-0 shrink-0 items-center gap-1">
              <div className={cn("w-1.5 h-1.5 rounded-full", cfg.dot)} />
              <Badge variant={cfg.variant} className="max-w-[84px] shrink-0 whitespace-nowrap">
                {cfg.label}
              </Badge>
              <button
                type="button"
                title="删除项目"
                aria-label="删除项目"
                onClick={(e) => {
                  e.stopPropagation();
                  setDeleteError(null);
                  setDeleteOpen(true);
                }}
                className={cn(
                  "ml-1 inline-flex h-8 w-8 items-center justify-center rounded-lg border border-transparent",
                  "text-muted opacity-70 transition-all hover:border-danger/30 hover:bg-danger-soft hover:text-danger",
                  "focus:outline-none focus:ring-2 focus:ring-danger/20"
                )}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <h3
            title={project.title}
            className="min-h-[3rem] break-words pr-1 text-lg font-black leading-tight text-text transition-colors line-clamp-2 group-hover:text-brand sm:min-h-[3.25rem] sm:text-xl"
          >
            {project.title}
          </h3>
          <p className="mt-1 text-xs text-muted truncate">{project.format}</p>
        </div>

        <div className="relative mb-3 min-h-[43px]">
          {project.initStatus === "initialized" ? (
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-muted">制作进度</span>
              <span className="text-xs font-black text-brand tabular-nums">{project.progress}%</span>
            </div>
          ) : (
            <div className="mb-1.5 flex items-center justify-between opacity-0">
              <span className="text-xs font-semibold">进度占位</span>
              <span className="text-xs font-black tabular-nums">0%</span>
            </div>
          )}
          {project.initStatus === "initialized" ? (
            <div className="h-2 bg-soft rounded-full overflow-hidden ring-1 ring-line/70">
              <div
                className="h-full bg-gradient-to-r from-primary to-signal rounded-full shadow-brand transition-all duration-500"
                style={{ width: `${project.progress}%` }}
              />
            </div>
          ) : (
            <div className="h-2 rounded-full bg-soft/40 opacity-0 ring-1 ring-line/70" />
          )}
        </div>

        <div className="relative grid grid-cols-3 gap-2 mb-3">
          <div className="rounded-xl border border-line/70 bg-elev/85 p-3 text-center min-h-[72px]">
            <div className="text-xl font-black text-text tabular-nums">{project.renderedEpisodes}</div>
            <div className="text-2xs text-muted mt-0.5">已完成</div>
          </div>
          <div className="rounded-xl border border-line/70 bg-elev/85 p-3 text-center min-h-[72px]">
            <div className="text-xl font-black text-text tabular-nums">{project.episodes || "—"}</div>
            <div className="text-2xs text-muted mt-0.5">最低集数</div>
          </div>
          <div className={cn(
            "rounded-xl border border-line/70 p-3 text-center min-h-[72px]",
            project.blockers && project.blockers > 0 ? "border-danger/20 bg-danger-soft" : "bg-elev"
          )}>
            <div className={cn(
              "text-xl font-black tabular-nums",
              project.blockers && project.blockers > 0 ? "text-danger" : "text-text"
            )}>
              {project.blockers ?? 0}
            </div>
            <div className="text-2xs text-muted mt-0.5">阻塞</div>
          </div>
        </div>

        <div className="relative min-h-[45px]">
          {project.note && (
            <div className={cn(
              "flex min-h-[45px] items-start gap-2 rounded-xl border px-3 py-2 text-xs",
              project.blockers && project.blockers > 0 ? "bg-warn-soft text-warn" : "bg-elev text-sub"
            )}>
              {project.blockers && project.blockers > 0
                ? <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                : <Clock className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted" />
              }
              <span className="line-clamp-2">{project.note}</span>
            </div>
          )}
        </div>

        <div className="relative mt-auto flex items-center justify-between border-t border-line pt-3">
          <span className="min-w-0 truncate text-xs text-muted">{project.stage}</span>
          <span className="text-xs font-black text-brand flex items-center gap-1 rounded-lg bg-brand-soft px-2.5 py-1 transition-colors group-hover:text-brand">
            进入项目 <ChevronRight className="w-3.5 h-3.5" />
          </span>
        </div>
      </div>

      <Dialog open={deleteOpen} onOpenChange={(open) => !deleting && setDeleteOpen(open)}>
        <DialogContent className="sm:max-w-md" onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-danger" />
              删除项目
            </DialogTitle>
            <DialogDescription>
              将删除「{project.title}」以及它的分集、资产、分镜和任务记录。此操作无法撤销。
            </DialogDescription>
          </DialogHeader>
          {deleteError && (
            <div className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
              {deleteError}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)} disabled={deleting}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  删除中...
                </>
              ) : (
                <>
                  <Trash2 className="w-4 h-4" />
                  确认删除
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function EmptyState() {
  const navigate = useNavigate();
  return (
    <div className="col-span-full flex flex-col items-center justify-center py-28 gap-6 animate-fade-in">
      <div className="w-24 h-24 rounded-3xl border border-line bg-elev flex items-center justify-center shadow-card">
        <Layers className="w-10 h-10 text-brand" />
      </div>
      <div className="text-center">
        <p className="text-2xl font-black text-text">还没有项目</p>
        <p className="text-base text-sub mt-2 max-w-sm">上传剧本，AI 自动完成分集规划和资产生成，快速开始制作。</p>
      </div>
      <Button size="lg" onClick={() => navigate("/projects/new")}>
        <Plus className="w-4 h-4" />
        创建第一个项目
      </Button>
    </div>
  );
}

export default function ProjectsHome() {
  const navigate = useNavigate();
  const { projects, loading, error } = useProjects();

  const initialized = projects.filter((p) => p.initStatus === "initialized").length;
  const inProgress  = projects.filter((p) => ["assets_confirmed", "episodes_confirmed", "script_uploaded"].includes(p.initStatus)).length;

  return (
    <div className="min-h-screen">
      <div className="page-shell py-5 sm:py-7">
        <div className="page-header">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="section-title mb-2">Production Workspace</p>
              <h1 className="text-2xl font-black text-text tracking-tight sm:text-3xl">我的项目</h1>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
                {initialized > 0 && (
                  <div className="flex items-center gap-1.5 text-sm text-sub">
                    <CheckCircle2 className="w-4 h-4 text-brand" />
                    <span className="tabular-nums font-medium">{initialized}</span> 个制作中
                  </div>
                )}
                {inProgress > 0 && (
                  <div className="flex items-center gap-1.5 text-sm text-sub">
                    <Clock className="w-4 h-4 text-warn" />
                    <span className="tabular-nums font-medium">{inProgress}</span> 个初始化中
                  </div>
                )}
                {!loading && projects.length === 0 && (
                  <span className="text-sm text-muted">点击右侧按钮创建第一个项目</span>
                )}
              </div>
            </div>
            <Button size="lg" className="w-full sm:w-auto" onClick={() => navigate("/projects/new")}>
              <Plus className="w-4 h-4" />
              新建项目
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-6 px-4 py-3 rounded-xl bg-danger-soft text-danger text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}
        {loading ? (
          <div className="mt-5 grid auto-rows-fr grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="page-panel h-[328px] p-4">
                <div className="flex items-start gap-3">
                  <div className="skeleton h-10 w-10 rounded-xl" />
                  <div className="flex-1 space-y-2">
                    <div className="skeleton h-4 w-2/3" />
                    <div className="skeleton h-3 w-1/3" />
                  </div>
                </div>
                <div className="mt-8 skeleton h-2 w-full rounded-full" />
                <div className="mt-5 grid grid-cols-3 gap-2">
                  <div className="skeleton h-16 rounded-xl" />
                  <div className="skeleton h-16 rounded-xl" />
                  <div className="skeleton h-16 rounded-xl" />
                </div>
                <div className="mt-5 skeleton h-10 rounded-xl" />
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-5 grid auto-rows-fr grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {projects.length > 0
              ? projects.map((p) => <ProjectCard key={p.id} project={p} />)
              : <EmptyState />
            }
          </div>
        )}
      </div>
    </div>
  );
}

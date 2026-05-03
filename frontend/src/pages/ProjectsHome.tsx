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
          "group media-card tech-border relative cursor-pointer overflow-hidden p-5",
          "animate-fade-in"
        )}
      >
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary via-sub to-line opacity-90" />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(0,0,0,0.025),transparent_35%,rgba(0,0,0,0.035))] opacity-0 transition-opacity duration-200 group-hover:opacity-100" />
        <div className="flex items-start justify-between gap-3 mb-5">
          <div className="flex items-start gap-3 min-w-0">
            <div className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-xs ring-1 ring-black/5",
              project.initStatus === "initialized"
                ? "bg-primary text-white shadow-md ring-1 ring-black/10"
                : "bg-soft text-sub"
            )}>
              <Play className="w-4.5 h-4.5" style={{ width: "1.125rem", height: "1.125rem" }} />
            </div>
            <div className="min-w-0">
              <h3 className="font-bold text-text text-base leading-snug group-hover:text-brand transition-colors line-clamp-2">
                {project.title}
              </h3>
              <p className="mt-1 text-xs text-muted truncate">{project.format}</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <div className={cn("w-1.5 h-1.5 rounded-full", cfg.dot)} />
            <Badge variant={cfg.variant}>{cfg.label}</Badge>
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
                "ml-1 inline-flex h-7 w-7 items-center justify-center rounded-md border border-transparent",
                "text-muted opacity-70 transition-all hover:border-danger/30 hover:bg-danger-soft hover:text-danger",
                "focus:outline-none focus:ring-2 focus:ring-danger/20"
              )}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {project.initStatus === "initialized" && (
          <div className="mb-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-muted">制作进度</span>
              <span className="text-xs font-bold text-brand tabular-nums">{project.progress}%</span>
            </div>
            <div className="h-2 bg-soft rounded-full overflow-hidden ring-1 ring-line/70">
              <div
                className="h-full bg-brand rounded-full transition-all duration-500"
                style={{ width: `${project.progress}%` }}
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-2 mb-4">
          <div className="rounded-xl border border-line/70 bg-elev p-3 text-center">
            <div className="text-lg font-bold text-text tabular-nums">{project.renderedEpisodes}</div>
            <div className="text-2xs text-muted mt-0.5">已完成</div>
          </div>
          <div className="rounded-xl border border-line/70 bg-elev p-3 text-center">
            <div className="text-lg font-bold text-text tabular-nums">{project.episodes || "—"}</div>
            <div className="text-2xs text-muted mt-0.5">总集数</div>
          </div>
          <div className={cn(
            "rounded-xl border border-line/70 p-3 text-center",
            project.blockers && project.blockers > 0 ? "border-danger/20 bg-danger-soft" : "bg-elev"
          )}>
            <div className={cn(
              "text-lg font-bold tabular-nums",
              project.blockers && project.blockers > 0 ? "text-danger" : "text-text"
            )}>
              {project.blockers ?? 0}
            </div>
            <div className="text-2xs text-muted mt-0.5">阻塞</div>
          </div>
        </div>

        {project.note && (
          <div className={cn(
            "flex items-start gap-2 text-xs px-3 py-2.5 rounded-xl border",
            project.blockers && project.blockers > 0 ? "bg-warn-soft text-warn" : "bg-elev text-sub"
          )}>
            {project.blockers && project.blockers > 0
              ? <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              : <Clock className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted" />
            }
            <span className="line-clamp-2">{project.note}</span>
          </div>
        )}

        <div className="mt-4 pt-3 border-t border-line flex items-center justify-between">
          <span className="text-xs text-muted">{project.stage}</span>
          <span className="text-xs font-semibold text-brand flex items-center gap-1 rounded-lg bg-brand-soft px-2 py-1 transition-colors group-hover:text-brand">
            进入项目 <ChevronRight className="w-3.5 h-3.5" />
          </span>
        </div>
      </div>

      <Dialog open={deleteOpen} onOpenChange={(open) => !deleting && setDeleteOpen(open)}>
        <DialogContent className="max-w-md" onClick={(e) => e.stopPropagation()}>
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
    <div className="col-span-full flex flex-col items-center justify-center py-24 gap-5 animate-fade-in">
      <div className="w-20 h-20 rounded-2xl bg-elev flex items-center justify-center">
        <Layers className="w-9 h-9 text-muted" />
      </div>
      <div className="text-center">
        <p className="text-lg font-bold text-text">还没有项目</p>
        <p className="text-sm text-sub mt-1.5 max-w-xs">上传剧本，AI 自动完成分集规划和资产生成，快速开始制作。</p>
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
      <div className="page-shell py-8">
        <div className="page-header">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="section-title mb-2">Production Workspace</p>
              <h1 className="text-3xl font-extrabold text-text tracking-tight">我的项目</h1>
              <div className="flex items-center gap-4 mt-2">
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
            <Button size="lg" onClick={() => navigate("/projects/new")}>
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
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="page-panel p-5 h-64">
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
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
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

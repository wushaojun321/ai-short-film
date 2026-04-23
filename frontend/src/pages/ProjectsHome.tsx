import { useNavigate } from "react-router-dom";
import { Plus, ChevronRight, AlertTriangle, CheckCircle2, Clock, Play, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Project } from "@/lib/data";
import { useProjects } from "@/lib/ProjectsContext";
import { cn } from "@/lib/utils";

const initStatusConfig: Record<Project["initStatus"], {
  label: string;
  variant: "success" | "warning" | "secondary" | "outline" | "primary";
  dot: string;
}> = {
  initialized:        { label: "制作中",   variant: "success",  dot: "bg-brand" },
  assets_confirmed:   { label: "资产审核", variant: "warning",  dot: "bg-warn animate-pulse" },
  episodes_confirmed: { label: "分集规划", variant: "warning",  dot: "bg-warn animate-pulse" },
  script_uploaded:    { label: "待解析",   variant: "secondary",dot: "bg-sub/40" },
  not_started:        { label: "未初始化", variant: "outline",  dot: "bg-line" },
};

function ProjectCard({ project }: { project: Project }) {
  const navigate = useNavigate();
  const cfg = initStatusConfig[project.initStatus];

  return (
    <div
      onClick={() => navigate(`/projects/${project.id}`)}
      className={cn(
        "group relative bg-white rounded-2xl border border-line p-5 cursor-pointer",
        "transition-all duration-200 hover:shadow-lg hover:border-primary/20 hover:-translate-y-0.5",
        "animate-fade-in"
      )}
    >
      {/* 顶部行 */}
      <div className="flex items-start justify-between gap-3 mb-5">
        <div className="flex items-start gap-3 min-w-0">
          {/* 项目图标 */}
          <div className={cn(
            "w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-xs",
            project.initStatus === "initialized"
              ? "bg-primary text-white"
              : "bg-soft text-sub"
          )}>
            <Play className="w-4.5 h-4.5" style={{ width: "1.125rem", height: "1.125rem" }} />
          </div>
          <div className="min-w-0">
            <h3 className="font-bold text-text text-base leading-snug group-hover:text-primary transition-colors line-clamp-2">
              {project.title}
            </h3>
            <p className="text-xs text-muted mt-0.5 tabular-nums">{project.genre}</p>
          </div>
        </div>

        {/* 状态徽章 */}
        <div className="flex items-center gap-1.5 shrink-0">
          <div className={cn("w-1.5 h-1.5 rounded-full", cfg.dot)} />
          <Badge variant={cfg.variant}>{cfg.label}</Badge>
        </div>
      </div>

      {/* 进度条（已初始化项目） */}
      {project.initStatus === "initialized" && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-muted">制作进度</span>
            <span className="text-xs font-bold text-primary tabular-nums">{project.progress}%</span>
          </div>
          <div className="h-1.5 bg-soft rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-brand to-brand/80 rounded-full transition-all duration-500"
              style={{ width: `${project.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* 统计数据 */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-elev rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-text tabular-nums">{project.renderedEpisodes}</div>
          <div className="text-2xs text-muted mt-0.5">已完成</div>
        </div>
        <div className="bg-elev rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-text tabular-nums">{project.episodes || "—"}</div>
          <div className="text-2xs text-muted mt-0.5">总集数</div>
        </div>
        <div className={cn(
          "rounded-xl p-3 text-center",
          project.blockers && project.blockers > 0 ? "bg-danger-soft" : "bg-elev"
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

      {/* 备注 */}
      {project.note && (
        <div className={cn(
          "flex items-start gap-2 text-xs px-3 py-2.5 rounded-xl",
          project.blockers && project.blockers > 0
            ? "bg-warn-soft text-warn"
            : "bg-elev text-sub"
        )}>
          {project.blockers && project.blockers > 0
            ? <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            : <Clock className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted" />
          }
          <span className="line-clamp-2">{project.note}</span>
        </div>
      )}

      {/* 悬浮底部行 */}
      <div className="mt-4 pt-3 border-t border-line flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity duration-150">
        <span className="text-xs text-muted">{project.format}</span>
        <span className="text-xs font-semibold text-brand flex items-center gap-1">
          进入项目 <ChevronRight className="w-3.5 h-3.5" />
        </span>
      </div>
    </div>
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
    <div className="min-h-screen bg-elev/40">
      {/* 页面 Hero */}
      <div className="bg-white border-b border-line">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
          <div className="flex items-end justify-between gap-6">
            <div>
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
      </div>

      {/* 项目网格 */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {error && (
          <div className="mb-6 px-4 py-3 rounded-xl bg-danger-soft text-danger text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white rounded-2xl border border-line p-5 animate-pulse h-52" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
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

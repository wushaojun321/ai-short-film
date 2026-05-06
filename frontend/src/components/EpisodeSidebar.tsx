import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, Circle, Film } from "lucide-react";
import { EpisodeDetail, EpisodeStatus } from "@/lib/data";
import { cn } from "@/lib/utils";

interface EpisodeSidebarProps {
  projectId: string;
  episodes: EpisodeDetail[];
  activeEpisodeId: string;
}

const statusConfig: Record<EpisodeStatus, {
  icon: React.ReactNode;
  dot: string;
  label: string;
}> = {
  completed:   {
    icon: <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />,
    dot:  "bg-success",
    label: "已完成",
  },
  in_progress: {
    icon: <Film className="w-3.5 h-3.5 text-warn shrink-0" />,
    dot:  "bg-warn animate-pulse",
    label: "制作中",
  },
  not_started: {
    icon: <Circle className="w-3.5 h-3.5 text-muted shrink-0" />,
    dot:  "bg-line",
    label: "未开始",
  },
};

export default function EpisodeSidebar({ projectId, episodes, activeEpisodeId }: EpisodeSidebarProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const handleSelect = (episodeId: string) => {
    const params = new URLSearchParams(searchParams);
    params.set("episode", episodeId);
    params.delete("shot");
    params.delete("step");
    navigate(`/projects/${projectId}?${params.toString()}`);
  };

  const counts = {
    completed:   episodes.filter((e) => e.status === "completed").length,
    in_progress: episodes.filter((e) => e.status === "in_progress").length,
    not_started: episodes.filter((e) => e.status === "not_started").length,
  };

  return (
    <aside className="sticky top-16 z-30 flex w-full shrink-0 flex-col border-b border-line bg-panel/95 shadow-card backdrop-blur-xl lg:z-auto lg:h-[calc(100vh-64px)] lg:w-72 lg:border-b-0 lg:border-r">
      {/* 顶部标题 */}
      <div className="flex items-center justify-between gap-3 border-b border-line bg-elev/70 px-3 py-3 lg:block lg:px-5 lg:py-5">
        <div className="flex items-center gap-2.5">
          <Film className="w-4 h-4 text-brand lg:w-5 lg:h-5" />
          <h3 className="text-sm font-black text-text uppercase tracking-widest">分集列表</h3>
        </div>
        <div className="flex shrink-0 gap-3 lg:mt-4 lg:gap-4">
          <div className="flex items-center gap-1 text-xs text-muted">
            <div className="w-1.5 h-1.5 rounded-full bg-success" />
            <span className="tabular-nums font-medium text-success">{counts.completed}</span>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted">
            <div className="w-1.5 h-1.5 rounded-full bg-warn" />
            <span className="tabular-nums font-medium text-warn">{counts.in_progress}</span>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted">
            <div className="w-1.5 h-1.5 rounded-full bg-line" />
            <span className="tabular-nums font-medium">{counts.not_started}</span>
          </div>
        </div>
      </div>

      {/* 分集列表 */}
      <div className="scroll-shadow-x min-h-0 flex-1 overflow-x-auto lg:overflow-y-auto lg:overflow-x-hidden lg:[mask-image:none]">
        <div className="flex gap-2 px-3 py-3 lg:block">
          {episodes.map((ep) => {
            const isActive = ep.id === activeEpisodeId;
            const cfg = statusConfig[ep.status];

            return (
              <button
                key={ep.id}
                onClick={() => handleSelect(ep.id)}
                className={cn(
                  "min-h-[68px] min-w-[148px] text-left px-3 py-3 rounded-2xl flex items-center gap-2.5 border lg:mb-2 lg:w-full lg:min-w-0 lg:px-4 lg:py-3.5 lg:gap-3",
                  "transition-all duration-150 group",
                  isActive
                    ? "bg-brand-soft border-brand/35 shadow-brand"
                    : "border-transparent hover:bg-soft",
                )}
              >
                <div className={cn("w-2.5 h-2.5 rounded-full shrink-0", cfg.dot)} />

                <div className="flex-1 min-w-0">
                  <div className={cn(
                    "text-xs font-black leading-tight lg:text-sm",
                    isActive ? "text-text" : "text-sub"
                  )}>
                    第 {ep.number} 集
                  </div>
                  <div className={cn(
                    "text-xs leading-tight mt-1 truncate lg:text-sm",
                    isActive ? "text-sub" : "text-muted",
                    ep.status === "not_started" && "italic text-muted"
                  )}>
                    {ep.title || "待规划"}
                  </div>
                </div>

                <div className={cn(
                  "transition-opacity",
                  isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                )}>
                  {cfg.icon}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 底部汇总 */}
      <div className="hidden px-5 py-4 border-t border-line bg-elev/70 lg:block">
        <div className="text-sm text-muted text-center">
          共 <span className="font-bold text-text tabular-nums">{episodes.length}</span> 集
          · <span className="text-success font-bold tabular-nums">{counts.completed}</span> 完成
        </div>
      </div>
    </aside>
  );
}

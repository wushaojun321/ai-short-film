import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, Circle, Film } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
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
    icon: <CheckCircle2 className="w-3.5 h-3.5 text-brand shrink-0" />,
    dot:  "bg-brand",
    label: "已完成",
  },
  in_progress: {
    icon: <Film className="w-3.5 h-3.5 text-warn shrink-0" />,
    dot:  "bg-warn animate-pulse",
    label: "制作中",
  },
  not_started: {
    icon: <Circle className="w-3.5 h-3.5 text-line shrink-0" />,
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
    params.delete("step");
    navigate(`/projects/${projectId}?${params.toString()}`);
  };

  const counts = {
    completed:   episodes.filter((e) => e.status === "completed").length,
    in_progress: episodes.filter((e) => e.status === "in_progress").length,
    not_started: episodes.filter((e) => e.status === "not_started").length,
  };

  return (
    <aside className="w-60 shrink-0 border-r border-line bg-white/92 flex flex-col h-[calc(100vh-56px)] sticky top-14 shadow-xs backdrop-blur">
      {/* 顶部标题 */}
      <div className="px-4 py-4 border-b border-line bg-white">
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-primary" />
          <h3 className="text-xs font-bold text-primary uppercase tracking-widest">分集列表</h3>
        </div>
        <div className="flex gap-3 mt-3">
          <div className="flex items-center gap-1 text-xs text-muted">
            <div className="w-1.5 h-1.5 rounded-full bg-brand" />
            <span className="tabular-nums font-medium text-brand">{counts.completed}</span>
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
      <ScrollArea className="flex-1">
        <div className="py-2 px-2">
          {episodes.map((ep) => {
            const isActive = ep.id === activeEpisodeId;
            const cfg = statusConfig[ep.status];

            return (
              <button
                key={ep.id}
                onClick={() => handleSelect(ep.id)}
                className={cn(
                  "w-full text-left px-3 py-2.5 rounded-xl mb-1 flex items-center gap-2.5 border",
                  "transition-all duration-150 group",
                  isActive
                    ? "bg-primary-soft border-primary/20 shadow-xs"
                    : "hover:bg-soft border-transparent",
                )}
              >
                {/* 状态点 */}
                <div className={cn("w-2 h-2 rounded-full shrink-0", cfg.dot)} />

                {/* 内容 */}
                <div className="flex-1 min-w-0">
                  <div className={cn(
                    "text-xs font-bold leading-tight",
                    isActive ? "text-primary" : "text-text"
                  )}>
                    第 {ep.number} 集
                  </div>
                  <div className={cn(
                    "text-xs leading-tight mt-0.5 truncate",
                    isActive ? "text-primary/70" : "text-sub",
                    ep.status === "not_started" && "italic text-muted"
                  )}>
                    {ep.title || "待规划"}
                  </div>
                </div>

                {/* 图标 */}
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
      </ScrollArea>

      {/* 底部汇总 */}
      <div className="px-4 py-3 border-t border-line bg-elev/70">
        <div className="text-xs text-muted text-center">
          共 <span className="font-bold text-text tabular-nums">{episodes.length}</span> 集
          · <span className="text-brand font-bold tabular-nums">{counts.completed}</span> 完成
        </div>
      </div>
    </aside>
  );
}

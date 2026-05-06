import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Circle, Film, Layers, Loader2, Play } from "lucide-react";
import { EpisodeDetail, EpisodeStatus, EpisodeStep, Shot } from "@/lib/data";
import { buildShotGroups, segmentTitle, shotNumberLabel } from "@/lib/shot-groups";
import { cn } from "@/lib/utils";

interface EpisodeSidebarProps {
  projectId: string;
  episodes: EpisodeDetail[];
  activeEpisodeId: string;
  activeEpisode?: EpisodeDetail;
  activeStep?: EpisodeStep;
  activeShotId?: string | null;
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

function isShotWarning(shot: Shot) {
  return !shot.videoUrl && (shot.state === "review_failed" || !!shot.continuityDirty);
}

export default function EpisodeSidebar({
  projectId,
  episodes,
  activeEpisodeId,
  activeEpisode,
  activeStep,
  activeShotId,
}: EpisodeSidebarProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const shotListRef = useRef<HTMLDivElement | null>(null);
  const showShotList = activeStep === "storyboard_videos" && activeEpisode?.id === activeEpisodeId && activeEpisode.shots.length > 0;
  const effectiveShotId = activeEpisode?.shots.some((shot) => shot.id === activeShotId)
    ? activeShotId
    : activeEpisode?.shots[0]?.id || null;

  useEffect(() => {
    if (!showShotList || !effectiveShotId) return;
    const activeEl = shotListRef.current?.querySelector<HTMLElement>(`[data-shot-id="${effectiveShotId}"]`);
    activeEl?.scrollIntoView({ block: "nearest" });
  }, [effectiveShotId, showShotList]);

  const handleSelect = (episodeId: string) => {
    const params = new URLSearchParams(searchParams);
    params.set("episode", episodeId);
    params.delete("shot");
    params.delete("step");
    navigate(`/projects/${projectId}?${params.toString()}`);
  };

  const handleSelectShot = (shotId: string) => {
    const params = new URLSearchParams(searchParams);
    params.set("episode", activeEpisodeId);
    params.set("step", "storyboard_videos");
    params.set("shot", shotId);
    navigate(`/projects/${projectId}?${params.toString()}`, { replace: true });
  };

  const handleShotKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!showShotList || !activeEpisode) return;
    const shots = activeEpisode.shots;
    const currentIndex = Math.max(0, shots.findIndex((shot) => shot.id === effectiveShotId));
    let nextIndex = currentIndex;

    if (event.key === "ArrowDown" || event.key === "ArrowRight") nextIndex = Math.min(shots.length - 1, currentIndex + 1);
    else if (event.key === "ArrowUp" || event.key === "ArrowLeft") nextIndex = Math.max(0, currentIndex - 1);
    else if (event.key === "PageDown") nextIndex = Math.min(shots.length - 1, currentIndex + 5);
    else if (event.key === "PageUp") nextIndex = Math.max(0, currentIndex - 5);
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = shots.length - 1;
    else return;

    event.preventDefault();
    const nextShot = shots[nextIndex];
    if (nextShot) handleSelectShot(nextShot.id);
  };

  const counts = {
    completed:   episodes.filter((e) => e.status === "completed").length,
    in_progress: episodes.filter((e) => e.status === "in_progress").length,
    not_started: episodes.filter((e) => e.status === "not_started").length,
  };

  return (
    <aside className={cn(
      "sticky top-16 z-30 flex w-full shrink-0 flex-col border-b border-line bg-panel/95 shadow-card backdrop-blur-xl lg:z-auto lg:h-[calc(100vh-64px)] lg:border-b-0 lg:border-r",
      showShotList ? "lg:w-80" : "lg:w-72"
    )}>
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
              <div key={ep.id} className="min-w-[148px] lg:min-w-0">
                <button
                  onClick={() => handleSelect(ep.id)}
                  className={cn(
                    "min-h-[68px] w-full text-left px-3 py-3 rounded-2xl flex items-center gap-2.5 border lg:mb-2 lg:px-4 lg:py-3.5 lg:gap-3",
                    "transition-all duration-150 group",
                    isActive
                      ? "bg-brand-soft border-brand/35 shadow-brand"
                      : "border-transparent hover:bg-soft",
                  )}
                >
                  {/* 状态点 */}
                  <div className={cn("w-2.5 h-2.5 rounded-full shrink-0", cfg.dot)} />

                  {/* 内容 */}
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

                  {/* 图标 */}
                  <div className={cn(
                    "transition-opacity",
                    isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                  )}>
                    {cfg.icon}
                  </div>
                </button>

                {isActive && showShotList && activeEpisode && (
                  <div className="mb-3 hidden rounded-2xl border border-line bg-base/70 p-2 shadow-inner lg:block">
                    <div className="mb-2 flex items-center justify-between px-1">
                      <span className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">Shot Index</span>
                      <span className="text-[11px] font-semibold text-sub">
                        {Math.max(1, activeEpisode.shots.findIndex((shot) => shot.id === effectiveShotId) + 1)} / {activeEpisode.shots.length}
                      </span>
                    </div>
                    <div
                      ref={shotListRef}
                      tabIndex={0}
                      role="listbox"
                      aria-label="镜头列表"
                      onKeyDown={handleShotKeyDown}
                      className="max-h-[min(52vh,560px)] space-y-3 overflow-y-auto overscroll-contain pr-1 focus:outline-none focus:ring-2 focus:ring-brand/40"
                    >
                      {buildShotGroups(activeEpisode.shots).map((group, groupIdx) => (
                        <div key={group.key} className="rounded-xl border border-line bg-panel/75 p-2">
                          <div className="mb-2 border-l-2 border-brand pl-2">
                            <div className="flex items-center gap-1.5 text-[11px] font-bold text-text">
                              <Layers className="h-3 w-3 text-brand" />
                              <span className="truncate">{segmentTitle(group, groupIdx)}</span>
                            </div>
                            {group.segmentFunction && (
                              <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted">{group.segmentFunction}</p>
                            )}
                          </div>
                          <div className="space-y-1.5">
                            {group.items.map(({ shot, index }) => {
                              const isShotActive = shot.id === effectiveShotId;
                              const isGenerating = shot.state === "rendering";
                              const isWarning = isShotWarning(shot);
                              const isDone = !!shot.videoUrl;
                              return (
                                <button
                                  key={shot.id}
                                  data-shot-id={shot.id}
                                  type="button"
                                  role="option"
                                  aria-selected={isShotActive}
                                  onClick={() => handleSelectShot(shot.id)}
                                  className={cn(
                                    "flex w-full items-center gap-2 rounded-xl border px-2 py-2 text-left transition-all",
                                    isShotActive
                                      ? "border-brand/60 bg-brand-soft shadow-brand"
                                      : isWarning
                                        ? "border-warn/45 bg-warn-soft/15 hover:bg-warn-soft/25"
                                        : "border-transparent bg-elev/50 hover:border-line hover:bg-soft"
                                  )}
                                >
                                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-soft">
                                    {isGenerating ? (
                                      <Loader2 className="h-4 w-4 animate-spin text-warn" />
                                    ) : isWarning ? (
                                      <AlertTriangle className="h-4 w-4 text-warn" />
                                    ) : isDone ? (
                                      <Play className="h-3.5 w-3.5 text-success" />
                                    ) : (
                                      <Film className="h-4 w-4 text-muted" />
                                    )}
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-1.5">
                                      <span className="truncate text-xs font-black text-text">{shotNumberLabel(index)}</span>
                                      <span className="shrink-0 text-[11px] text-muted">{shot.duration}s</span>
                                    </div>
                                    <p className="mt-0.5 truncate text-[11px] text-muted">
                                      {shot.shotFunction || shot.description || shot.shotCode}
                                    </p>
                                  </div>
                                  <div className={cn(
                                    "h-2.5 w-2.5 shrink-0 rounded-full",
                                    isGenerating ? "bg-warn animate-pulse" : isWarning ? "bg-warn" : isDone ? "bg-success" : "bg-line"
                                  )} />
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
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

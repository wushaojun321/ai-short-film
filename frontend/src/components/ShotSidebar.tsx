import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, Film, Layers, Loader2, Play } from "lucide-react";
import { EpisodeDetail, Shot } from "@/lib/data";
import { buildShotGroups, segmentTitle, shotNumberLabel } from "@/lib/shot-groups";
import { cn } from "@/lib/utils";

interface ShotSidebarProps {
  projectId: string;
  episode: EpisodeDetail;
  activeShotId?: string | null;
}

function isShotWarning(shot: Shot) {
  return !shot.videoUrl && (shot.state === "review_failed" || !!shot.continuityDirty);
}

export default function ShotSidebar({ projectId, episode, activeShotId }: ShotSidebarProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const shotListRef = useRef<HTMLDivElement | null>(null);
  const effectiveShotId = episode.shots.some((shot) => shot.id === activeShotId)
    ? activeShotId
    : episode.shots[0]?.id || null;
  const activeShotIndex = Math.max(0, episode.shots.findIndex((shot) => shot.id === effectiveShotId));

  useEffect(() => {
    if (!effectiveShotId) return;
    const activeEl = shotListRef.current?.querySelector<HTMLElement>(`[data-shot-id="${effectiveShotId}"]`);
    activeEl?.scrollIntoView({ block: "nearest" });
  }, [effectiveShotId]);

  const handleSelectShot = (shotId: string) => {
    const params = new URLSearchParams(searchParams);
    params.set("episode", episode.id);
    params.set("step", "storyboard_videos");
    params.set("shot", shotId);
    navigate(`/projects/${projectId}?${params.toString()}`, { replace: true });
  };

  const handleShotKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const shots = episode.shots;
    let nextIndex = activeShotIndex;

    if (event.key === "ArrowDown" || event.key === "ArrowRight") nextIndex = Math.min(shots.length - 1, activeShotIndex + 1);
    else if (event.key === "ArrowUp" || event.key === "ArrowLeft") nextIndex = Math.max(0, activeShotIndex - 1);
    else if (event.key === "PageDown") nextIndex = Math.min(shots.length - 1, activeShotIndex + 5);
    else if (event.key === "PageUp") nextIndex = Math.max(0, activeShotIndex - 5);
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = shots.length - 1;
    else return;

    event.preventDefault();
    const nextShot = shots[nextIndex];
    if (nextShot) handleSelectShot(nextShot.id);
  };

  return (
    <aside className="hidden w-80 shrink-0 border-r border-line bg-base/88 shadow-card backdrop-blur-xl lg:flex lg:h-[calc(100vh-64px)] lg:flex-col">
      <div className="border-b border-line bg-elev/70 px-4 py-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-black uppercase tracking-[0.22em] text-muted">Shot Index</span>
          <span className="text-sm font-black tabular-nums text-text">
            {activeShotIndex + 1} / {episode.shots.length}
          </span>
        </div>
        <div className="mt-2 min-w-0">
          <p className="truncate text-sm font-black text-text">第 {episode.number} 集</p>
          <p className="mt-1 truncate text-xs text-sub">{episode.title || "待规划"}</p>
        </div>
      </div>

      <div
        ref={shotListRef}
        tabIndex={0}
        role="listbox"
        aria-label="镜头列表"
        onKeyDown={handleShotKeyDown}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-3 py-4 focus:outline-none focus:ring-2 focus:ring-brand/40"
      >
        {buildShotGroups(episode.shots).map((group, groupIdx) => (
          <section key={group.key} className="rounded-2xl border border-line bg-panel/80 p-3 shadow-inner">
            <div className="mb-3 border-l-2 border-brand pl-3">
              <div className="flex items-center gap-2 text-sm font-black text-text">
                <Layers className="h-4 w-4 text-brand" />
                <span className="truncate">{segmentTitle(group, groupIdx)}</span>
              </div>
              {group.segmentFunction && (
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{group.segmentFunction}</p>
              )}
            </div>

            <div className="space-y-2">
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
                      "flex w-full items-center gap-3 rounded-2xl border px-3 py-3 text-left transition-all",
                      isShotActive
                        ? "border-brand/70 bg-brand-soft shadow-brand"
                        : isWarning
                          ? "border-warn/45 bg-warn-soft/15 hover:bg-warn-soft/25"
                          : "border-transparent bg-elev/50 hover:border-line hover:bg-soft"
                    )}
                  >
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line bg-soft">
                      {isGenerating ? (
                        <Loader2 className="h-5 w-5 animate-spin text-warn" />
                      ) : isWarning ? (
                        <AlertTriangle className="h-5 w-5 text-warn" />
                      ) : isDone ? (
                        <Play className="h-4 w-4 text-success" />
                      ) : (
                        <Film className="h-5 w-5 text-muted" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-black text-text">{shotNumberLabel(index)}</span>
                        <span className="shrink-0 text-xs font-semibold text-muted">{shot.duration}s</span>
                      </div>
                      <p className="mt-1 truncate text-xs text-muted">
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
          </section>
        ))}
      </div>
    </aside>
  );
}

import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Film, Layers, Loader2, Play } from "lucide-react";
import { EpisodeDetail, Shot } from "@/lib/data";
import { shotNumberLabel, type ShotGroup } from "@/lib/shot-groups";
import { cn } from "@/lib/utils";

interface ShotSidebarProps {
  projectId: string;
  episode: EpisodeDetail;
  activeShotId?: string | null;
}

function isShotWarning(shot: Shot) {
  return !shot.videoUrl && (shot.state === "review_failed" || !!shot.continuityDirty);
}

function isShotApproved(shot: Shot) {
  return shot.state === "approved";
}

function buildSidebarShotGroups(items: Array<{ shot: Shot; index: number }>): ShotGroup[] {
  const groups: ShotGroup[] = [];
  const groupMap = new Map<string, ShotGroup>();

  items.forEach(({ shot, index }) => {
    const segmentCode = shot.segmentCode?.trim();
    const segmentName = shot.segmentName?.trim();
    const key = segmentCode || segmentName || "ungrouped";
    let group = groupMap.get(key);
    if (!group) {
      group = {
        key,
        label: segmentName || segmentCode || "未分段片段",
        segmentCode,
        segmentName,
        segmentFunction: shot.segmentFunction,
        items: [],
      };
      groupMap.set(key, group);
      groups.push(group);
    }
    if (!group.segmentFunction && shot.segmentFunction) group.segmentFunction = shot.segmentFunction;
    group.items.push({ shot, index });
  });

  return groups;
}

function sidebarGroupTitle(group: ShotGroup) {
  const name = group.segmentName || group.segmentCode || group.label;
  return name && name !== "未分段片段" ? name : "未分段片段";
}

export default function ShotSidebar({ projectId, episode, activeShotId }: ShotSidebarProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const shotListRef = useRef<HTMLDivElement | null>(null);
  const effectiveShotId = episode.shots.some((shot) => shot.id === activeShotId)
    ? activeShotId
    : episode.shots[0]?.id || null;
  const activeShotIndex = Math.max(0, episode.shots.findIndex((shot) => shot.id === effectiveShotId));
  const indexedShots = episode.shots.map((shot, index) => ({ shot, index }));
  const pendingItems = indexedShots.filter(({ shot }) => !isShotApproved(shot));
  const approvedItems = indexedShots.filter(({ shot }) => isShotApproved(shot));
  const approvalSections = [
    {
      key: "pending",
      title: "待审批",
      count: pendingItems.length,
      helper: "需要生成、修复或审批",
      icon: AlertTriangle,
      headerClass: "text-warn",
      badgeClass: "bg-warn-soft text-warn",
      emptyText: "暂无待审批镜头",
      groups: buildSidebarShotGroups(pendingItems),
    },
    {
      key: "approved",
      title: "已审批",
      count: approvedItems.length,
      helper: "已通过，可用于合成",
      icon: CheckCircle2,
      headerClass: "text-success",
      badgeClass: "bg-success-soft text-success",
      emptyText: "暂无已审批镜头",
      groups: buildSidebarShotGroups(approvedItems),
    },
  ];

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
    <aside className="hidden w-64 shrink-0 border-r border-line bg-base/88 shadow-card backdrop-blur-xl xl:w-72 lg:flex lg:h-[calc(100vh-64px)] lg:flex-col">
      <div className="border-b border-line bg-elev/70 px-3 py-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-muted">Shot Index</span>
          <span className="text-xs font-black tabular-nums text-text">
            {activeShotIndex + 1} / {episode.shots.length}
          </span>
        </div>
        <div className="mt-1.5 min-w-0">
          <p className="truncate text-xs font-black text-text">第 {episode.number} 集</p>
          <p className="mt-1 truncate text-xs text-sub">{episode.title || "待规划"}</p>
        </div>
      </div>

      <div
        ref={shotListRef}
        tabIndex={0}
        role="listbox"
        aria-label="镜头列表"
        onKeyDown={handleShotKeyDown}
        className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-2.5 py-3 focus:outline-none focus:ring-2 focus:ring-brand/40"
      >
        {approvalSections.map((section) => {
          const SectionIcon = section.icon;
          return (
            <section key={section.key} aria-label={section.title} className="space-y-2">
              <div className="sticky top-0 z-10 -mx-0.5 rounded-xl border border-line bg-base/95 px-2.5 py-2 shadow-xs backdrop-blur">
                <div className="flex items-center justify-between gap-2">
                  <div className={cn("flex min-w-0 items-center gap-1.5", section.headerClass)}>
                    <SectionIcon className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate text-xs font-black">{section.title}</span>
                  </div>
                  <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-black tabular-nums", section.badgeClass)}>
                    {section.count}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-[11px] text-muted">{section.helper}</p>
              </div>

              {section.groups.length === 0 ? (
                <div className="rounded-xl border border-dashed border-line bg-elev/35 px-3 py-3 text-center text-xs text-muted">
                  {section.emptyText}
                </div>
              ) : (
                <div className="space-y-2">
                  {section.groups.map((group) => (
                    <section key={`${section.key}-${group.key}`} className="rounded-xl border border-line bg-panel/80 p-2.5 shadow-inner">
                      <div className="mb-2 border-l-2 border-brand pl-2">
                        <div className="flex items-center gap-1.5 text-xs font-black text-text">
                          <Layers className="h-3.5 w-3.5 text-brand" />
                          <span className="truncate">{sidebarGroupTitle(group)}</span>
                        </div>
                        {group.segmentFunction && (
                          <p className="mt-0.5 line-clamp-1 text-[11px] leading-relaxed text-muted">{group.segmentFunction}</p>
                        )}
                      </div>

                      <div className="space-y-1.5">
                        {group.items.map(({ shot, index }) => {
                          const isShotActive = shot.id === effectiveShotId;
                          const isGenerating = shot.state === "rendering";
                          const isWarning = isShotWarning(shot);
                          const isApproved = isShotApproved(shot);
                          const isGenerated = !!shot.videoUrl;
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
                                  ? "border-brand/70 bg-brand-soft shadow-brand"
                                  : isWarning
                                    ? "border-warn/45 bg-warn-soft/15 hover:bg-warn-soft/25"
                                    : isApproved
                                      ? "border-success/20 bg-success-soft/35 hover:border-success/35 hover:bg-success-soft/50"
                                      : isGenerated
                                        ? "border-warn/20 bg-warn-soft/10 hover:border-warn/35 hover:bg-warn-soft/20"
                                        : "border-transparent bg-elev/50 hover:border-line hover:bg-soft"
                              )}
                            >
                              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-soft">
                                {isGenerating ? (
                                  <Loader2 className="h-4 w-4 animate-spin text-warn" />
                                ) : isWarning ? (
                                  <AlertTriangle className="h-4 w-4 text-warn" />
                                ) : isApproved ? (
                                  <CheckCircle2 className="h-4 w-4 text-success" />
                                ) : isGenerated ? (
                                  <Play className="h-3.5 w-3.5 text-warn" />
                                ) : (
                                  <Film className="h-4 w-4 text-muted" />
                                )}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="truncate text-xs font-black text-text">{shotNumberLabel(index)}</span>
                                  <span className="shrink-0 text-[11px] font-semibold text-muted">{shot.duration}s</span>
                                </div>
                                <p className="mt-0.5 truncate text-[11px] text-muted">
                                  {shot.shotFunction || shot.description || shot.shotCode}
                                </p>
                              </div>
                              <div className={cn(
                                "h-2.5 w-2.5 shrink-0 rounded-full",
                                isGenerating ? "bg-warn animate-pulse" : isWarning ? "bg-warn" : isApproved ? "bg-success" : isGenerated ? "bg-warn" : "bg-line"
                              )} />
                            </button>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </aside>
  );
}

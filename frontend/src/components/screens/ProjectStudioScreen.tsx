import { useSearchParams, useNavigate } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { Images, FileText } from "lucide-react";
import EpisodeSidebar from "@/components/EpisodeSidebar";
import EpisodeStepBar from "@/components/EpisodeStepBar";
import StepContent from "@/components/StepContent";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { Project, EpisodeDetail, EpisodeStep, STEP_ORDER } from "@/lib/data";
import { episodeAPI } from "@/lib/api";
import { transformEpisode } from "@/lib/transforms";
import { cn } from "@/lib/utils";

interface ProjectStudioScreenProps {
  project: Project;
  onProjectUpdate: () => void;
}

export default function ProjectStudioScreen({ project, onProjectUpdate }: ProjectStudioScreenProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [episodes, setEpisodes] = useState<EpisodeDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [scriptSheetOpen, setScriptSheetOpen] = useState(false);

  const episodeId = searchParams.get("episode") ?? episodes[0]?.id;
  const stepParam = searchParams.get("step") as EpisodeStep | null;
  const activeEpisode = episodes.find((e) => e.id === episodeId) ?? episodes[0];
  const activeStep: EpisodeStep =
    stepParam && STEP_ORDER.includes(stepParam)
      ? stepParam
      : activeEpisode?.currentStep ?? "storyboard_script";
  const sourceLineRange = activeEpisode?.sourceStartLine && activeEpisode?.sourceEndLine
    ? `L${activeEpisode.sourceStartLine}-${activeEpisode.sourceEndLine}`
    : "未索引";

  // 记录上次 currentStep，防止轮询循环写 URL
  const lastCurrentStepRef = useRef<string | null>(null);

  // ── 初始加载 ──────────────────────────────────────────────────
  useEffect(() => {
    episodeAPI.list(project.id).then((data) => {
      const eps = data.map(transformEpisode);
      setEpisodes(eps);
      setLoading(false);
      if (!searchParams.get("episode") && eps.length > 0) {
        const defaultEp = eps.find((e) => e.status === "in_progress") ?? eps[0];
        const params = new URLSearchParams(searchParams);
        params.set("episode", defaultEp.id);
        params.set("step", defaultEp.currentStep);
        setSearchParams(params, { replace: true });
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  // ── 集数列表轮询（5s）————————————————————————————————————
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await episodeAPI.list(project.id);
        setEpisodes((prev) =>
          data.map((raw) => {
            const transformed = transformEpisode(raw);
            const existing = prev.find((e) => e.id === transformed.id);
            // 保留当前集已加载的 shots 和 runningTasks，避免列表接口覆盖为空
            return existing
              ? { ...transformed, shots: existing.shots, runningTasks: existing.runningTasks, taskProgress: existing.taskProgress }
              : transformed;
          })
        );
      } catch {
        // 静默失败，不影响使用
      }
    };
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, [project.id]);

  // ── 当前集全量轮询（3s，含 shots）─────────────────────────────
  useEffect(() => {
    if (!episodeId) return;
    lastCurrentStepRef.current = null;

    const poll = async () => {
      try {
        const raw = await episodeAPI.get(project.id, episodeId, { include_shots: true });
        const updated = transformEpisode(raw);

        setEpisodes((prev) =>
          prev.map((e) => (e.id === updated.id ? updated : e))
        );

        // currentStep 推进时自动跳转到最新步骤
        if (updated.currentStep !== lastCurrentStepRef.current) {
          lastCurrentStepRef.current = updated.currentStep;
          setSearchParams(
            (prev) => {
              const p = new URLSearchParams(prev);
              p.set("step", updated.currentStep);
              return p;
            },
            { replace: true }
          );
        }
      } catch {
        // 静默失败
      }
    };

    poll(); // 立即执行一次
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, episodeId]);

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-64px)] items-center justify-center">
        <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!activeEpisode) return null;

  const shotTotalDuration = activeEpisode.shots.reduce((sum, shot) => sum + (shot.duration || 0), 0);
  const displayDuration = shotTotalDuration > 0 ? shotTotalDuration : activeEpisode.estimatedDuration;
  const displayDurationLabel = shotTotalDuration > 0 ? "分镜总时长" : "预估时长";
  const displayDurationText = `${Math.floor(displayDuration / 60)}:${(displayDuration % 60).toString().padStart(2, "0")}`;
  const isVideoStep = activeStep === "storyboard_videos";

  return (
    <div className="flex h-[calc(100vh-64px)]">
      <EpisodeSidebar
        projectId={project.id}
        episodes={episodes}
        activeEpisodeId={activeEpisode.id}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <EpisodeStepBar
          projectId={project.id}
          episodeId={activeEpisode.id}
          currentStep={activeEpisode.currentStep}
          activeStep={activeStep}
        />

        <div className="flex-1 overflow-y-auto">
          <div className={cn("mx-auto px-7", isVideoStep ? "max-w-7xl py-4" : "max-w-6xl py-7")}>
            <div className={cn("page-panel tech-border", isVideoStep ? "mb-4 p-5" : "mb-7 p-6")}>
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="min-w-0">
                  <p className="section-title mb-2">Episode Workspace</p>
                  <h2 className="text-2xl font-black text-text">
                    第 {activeEpisode.number} 集 · {activeEpisode.title}
                  </h2>
                  {activeEpisode.summary && (
                    <p className="text-base text-sub mt-2">{activeEpisode.summary}</p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold text-muted">
                    <span className="rounded-lg bg-soft px-2.5 py-1">原文 {sourceLineRange}</span>
                    <span className="rounded-lg bg-soft px-2.5 py-1">对白 {activeEpisode.dialogueCount ?? 0}</span>
                    {activeEpisode.sourceIntegrity && (
                      <span className={cn(
                        "rounded-lg px-2.5 py-1",
                        activeEpisode.sourceIntegrity === "original" ? "bg-brand-soft text-brand" : "bg-warn/10 text-warn"
                      )}>
                        {activeEpisode.sourceIntegrity === "original" ? "原文完整" : activeEpisode.sourceIntegrity}
                      </span>
                    )}
                  </div>
                  {activeEpisode.scriptExcerpt && (
                    <p
                      className={cn(
                        "text-sm text-muted mt-3 cursor-pointer hover:text-sub transition-colors whitespace-pre-wrap",
                        isVideoStep ? "line-clamp-1" : "line-clamp-2"
                      )}
                      onClick={() => setScriptSheetOpen(true)}
                    >
                      {activeEpisode.scriptExcerpt}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2 shrink-0 xl:ml-4">
                  {activeEpisode.scriptExcerpt && (
                    <Button
                      size="default"
                      variant="outline"
                      className="flex items-center gap-2"
                      onClick={() => setScriptSheetOpen(true)}
                    >
                      <FileText className="w-3.5 h-3.5" />
                      查看剧本
                    </Button>
                  )}
                  <Button
                      size="default"
                    variant="outline"
                    className="flex items-center gap-2"
                    onClick={() => navigate(`/projects/${project.id}?view=assets`)}
                  >
                    <Images className="w-3.5 h-3.5" />
                    资产库
                  </Button>
                  <div className="toolbar gap-4 text-right">
                    {displayDuration > 0 && (
                      <div>
                        <div className="text-lg font-black text-text">
                          {displayDurationText}
                        </div>
                        <div className="text-xs font-semibold text-muted">{displayDurationLabel}</div>
                      </div>
                    )}
                    {activeEpisode.shots.length > 0 && (
                      <div>
                        <div className="text-lg font-black text-text">{activeEpisode.shots.length}</div>
                        <div className="text-xs font-semibold text-muted">分镜数</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <StepContent
              step={activeStep}
              episode={activeEpisode}
              projectId={project.id}
            />
          </div>
        </div>
      </div>

      <Sheet
        open={scriptSheetOpen}
        onClose={() => setScriptSheetOpen(false)}
        title={activeEpisode ? `第 ${activeEpisode.number} 集《${activeEpisode.title}》· 原始剧本` : "原始剧本"}
        width="w-[560px]"
      >
        {activeEpisode?.scriptExcerpt && (
          <pre className="text-xs text-text leading-relaxed whitespace-pre-wrap font-sans">
            {activeEpisode.scriptExcerpt}
          </pre>
        )}
      </Sheet>
    </div>
  );
}

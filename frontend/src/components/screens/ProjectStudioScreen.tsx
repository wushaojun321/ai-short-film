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
      <div className="flex h-[calc(100vh-56px)] items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!activeEpisode) return null;

  return (
    <div className="flex h-[calc(100vh-56px)]">
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

        <div className="flex-1 overflow-y-auto bg-white">
          <div className="max-w-5xl mx-auto px-6 py-6">
            <div className="mb-6 pb-4 border-b border-line">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-text">
                    第 {activeEpisode.number} 集 · {activeEpisode.title}
                  </h2>
                  {activeEpisode.summary && (
                    <p className="text-sm text-sub mt-1">{activeEpisode.summary}</p>
                  )}
                  {activeEpisode.scriptExcerpt && (
                    <p
                      className="text-xs text-muted mt-1.5 line-clamp-2 cursor-pointer hover:text-sub transition-colors whitespace-pre-wrap"
                      onClick={() => setScriptSheetOpen(true)}
                    >
                      {activeEpisode.scriptExcerpt}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  {activeEpisode.scriptExcerpt && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex items-center gap-1.5 text-xs"
                      onClick={() => setScriptSheetOpen(true)}
                    >
                      <FileText className="w-3.5 h-3.5" />
                      查看剧本
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex items-center gap-1.5 text-xs"
                    onClick={() => navigate(`/projects/${project.id}?view=assets`)}
                  >
                    <Images className="w-3.5 h-3.5" />
                    资产库
                  </Button>
                  <div className="flex gap-4 text-right">
                    {activeEpisode.estimatedDuration > 0 && (
                      <div>
                        <div className="text-sm font-semibold text-text">
                          {Math.floor(activeEpisode.estimatedDuration / 60)}:
                          {(activeEpisode.estimatedDuration % 60).toString().padStart(2, "0")}
                        </div>
                        <div className="text-xs text-muted">预估时长</div>
                      </div>
                    )}
                    {activeEpisode.shots.length > 0 && (
                      <div>
                        <div className="text-sm font-semibold text-text">{activeEpisode.shots.length}</div>
                        <div className="text-xs text-muted">分镜数</div>
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

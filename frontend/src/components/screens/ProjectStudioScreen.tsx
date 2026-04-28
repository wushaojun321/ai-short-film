import { useSearchParams, useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";
import { Images } from "lucide-react";
import EpisodeSidebar from "@/components/EpisodeSidebar";
import EpisodeStepBar from "@/components/EpisodeStepBar";
import StepContent from "@/components/StepContent";
import { Button } from "@/components/ui/button";
import { Project, EpisodeDetail, EpisodeStep, STEP_ORDER } from "@/lib/data";
import { episodeAPI, shotAPI } from "@/lib/api";
import { transformEpisode, transformShot } from "@/lib/transforms";
interface ProjectStudioScreenProps {
  project: Project;
  onProjectUpdate: () => void;
}

export default function ProjectStudioScreen({ project }: ProjectStudioScreenProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [episodes, setEpisodes] = useState<EpisodeDetail[]>([]);
  const [loading, setLoading] = useState(true);

  const loadEpisodes = useCallback(async () => {
    try {
      const data = await episodeAPI.list(project.id);
      const eps = data.map(transformEpisode);
      setEpisodes(eps);
      return eps;
    } finally {
      setLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    loadEpisodes().then((eps) => {
      // 初始化 URL 参数
      if (!searchParams.get("episode") && eps.length > 0) {
        const defaultEp = eps.find((e) => e.status === "in_progress") ?? eps[0];
        const params = new URLSearchParams(searchParams);
        params.set("episode", defaultEp.id);
        params.set("step", defaultEp.currentStep);
        setSearchParams(params, { replace: true });
      }
    });
  }, [project.id]);

  const episodeId = searchParams.get("episode") ?? episodes[0]?.id;
  const stepParam = searchParams.get("step") as EpisodeStep | null;

  const activeEpisode = episodes.find((e) => e.id === episodeId) ?? episodes[0];
  const activeStep: EpisodeStep = (stepParam && STEP_ORDER.includes(stepParam))
    ? stepParam
    : activeEpisode?.currentStep ?? "storyboard_script";

  // 加载当前集的分镜
  const loadShots = useCallback(async (ep: EpisodeDetail) => {
    if (!ep) return ep;
    const shots = await shotAPI.list(project.id, ep.id);
    const updated = { ...ep, shots: shots.map(transformShot) };
    setEpisodes((prev) => prev.map((e) => e.id === ep.id ? updated : e));
    return updated;
  }, [project.id]);

  // 重新加载单个 episode（step 推进后调用）
  const reloadEpisode = useCallback(async (episodeId: string) => {
    const raw = await episodeAPI.get(project.id, episodeId);
    const updated = transformEpisode(raw);
    setEpisodes((prev) => prev.map((e) => e.id === episodeId
      // 保留已加载的 shots，只更新 episode 元信息
      ? { ...e, ...updated, shots: e.shots }
      : e
    ));
    // 同步 URL step 到新的 currentStep
    setSearchParams((prev) => {
      const p = new URLSearchParams(prev);
      p.set("step", updated.currentStep);
      return p;
    }, { replace: true });
  }, [project.id, setSearchParams]);

  useEffect(() => {
    if (activeEpisode) loadShots(activeEpisode);
  }, [activeEpisode?.id]);

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
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-4">
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
              key={`${activeEpisode.id}-${activeEpisode.shots.length}`}
              step={activeStep}
              episode={activeEpisode}
              projectId={project.id}
              onShotsUpdate={() => loadShots(activeEpisode)}
              onEpisodeUpdate={() => reloadEpisode(activeEpisode.id)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

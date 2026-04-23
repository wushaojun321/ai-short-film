import { useSearchParams, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import EpisodeSidebar from "@/components/EpisodeSidebar";
import EpisodeStepBar from "@/components/EpisodeStepBar";
import StepContent from "@/components/StepContent";
import {
  Project,
  EpisodeStep,
  STEP_ORDER,
  getEpisodeDetails,
  getFirstInProgressEpisode,
} from "@/lib/data";

interface ProjectStudioScreenProps {
  project: Project;
}

export default function ProjectStudioScreen({ project }: ProjectStudioScreenProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const episodes = getEpisodeDetails(project.id);
  const defaultEpisode = getFirstInProgressEpisode(project.id);

  // 从 URL 读取当前集和步骤
  const episodeId = searchParams.get("episode") ?? defaultEpisode?.id ?? episodes[0]?.id;
  const stepParam = searchParams.get("step") as EpisodeStep | null;

  const activeEpisode = episodes.find((e) => e.id === episodeId) ?? episodes[0];
  const activeStep: EpisodeStep = (stepParam && STEP_ORDER.includes(stepParam))
    ? stepParam
    : activeEpisode?.currentStep ?? "storyboard_script";

  // 初始化时如果 URL 没有参数，写入默认值
  useEffect(() => {
    if (!searchParams.get("episode") && defaultEpisode) {
      const params = new URLSearchParams(searchParams);
      params.set("episode", defaultEpisode.id);
      params.set("step", defaultEpisode.currentStep);
      setSearchParams(params, { replace: true });
    }
  }, []);

  if (!activeEpisode) return null;

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* 左侧分集侧边栏 */}
      <EpisodeSidebar
        projectId={project.id}
        episodes={episodes}
        activeEpisodeId={activeEpisode.id}
      />

      {/* 右侧主区域 */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* 顶部步骤条 */}
        <EpisodeStepBar
          projectId={project.id}
          episodeId={activeEpisode.id}
          currentStep={activeEpisode.currentStep}
          activeStep={activeStep}
        />

        {/* 步骤内容区 */}
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="max-w-5xl mx-auto px-6 py-6">
            {/* 集信息 */}
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
                <div className="flex gap-4 text-right shrink-0 ml-4">
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

            {/* 步骤内容 */}
            <StepContent step={activeStep} episode={activeEpisode} />
          </div>
        </div>
      </div>
    </div>
  );
}

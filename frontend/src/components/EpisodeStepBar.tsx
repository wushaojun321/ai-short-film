import { useNavigate, useSearchParams } from "react-router-dom";
import { Check } from "lucide-react";
import { EPISODE_STEPS, STEP_ORDER, EpisodeStep, getStepIndex } from "@/lib/data";
import { cn } from "@/lib/utils";

interface EpisodeStepBarProps {
  projectId: string;
  episodeId: string;
  currentStep: EpisodeStep;
  activeStep: EpisodeStep;
}

export default function EpisodeStepBar({
  projectId,
  episodeId,
  currentStep,
  activeStep,
}: EpisodeStepBarProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const currentIdx = getStepIndex(currentStep);
  const activeIdx = getStepIndex(activeStep);

  const handleStepClick = (step: EpisodeStep) => {
    const stepIdx = getStepIndex(step);
    // 只允许点击已到达或当前步骤
    if (stepIdx > currentIdx) return;
    const params = new URLSearchParams(searchParams);
    params.set("episode", episodeId);
    params.set("step", step);
    navigate(`/projects/${projectId}?${params.toString()}`);
  };

  return (
    <div className="bg-white/92 border-b border-line px-6 py-0 overflow-x-auto shadow-xs backdrop-blur">
      <div className="flex items-stretch min-w-max">
        {EPISODE_STEPS.map((stepDef, idx) => {
          const stepIdx = getStepIndex(stepDef.key);
          const isDone = stepIdx < currentIdx;
          const isCurrent = stepDef.key === currentStep;
          const isActive = stepDef.key === activeStep;
          const isReachable = stepIdx <= currentIdx;
          const isLast = idx === EPISODE_STEPS.length - 1;

          return (
            <div key={stepDef.key} className="flex items-center">
              <button
                onClick={() => handleStepClick(stepDef.key)}
                disabled={!isReachable}
                className={cn(
                  "relative flex flex-col items-center gap-1 px-4 py-3 text-xs transition-colors border-b-2",
                  isReachable ? "cursor-pointer" : "cursor-default",
                  isActive
                    ? "border-brand text-brand font-semibold"
                    : "border-transparent",
                  !isActive && isDone && "text-brand/60 hover:text-brand/80",
                  !isActive && isCurrent && !isActive && "text-text hover:text-brand",
                  !isActive && !isDone && !isCurrent && "text-muted",
                )}
              >
                {/* 步骤图标 */}
                <div className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold transition-all",
                  isDone && !isActive && "bg-brand/10 text-brand ring-1 ring-brand/10",
                  isCurrent && isActive && "bg-brand text-white",
                  isCurrent && !isActive && "bg-brand/10 text-brand ring-1 ring-brand/10",
                  isActive && !isCurrent && "bg-brand text-white",
                  !isDone && !isCurrent && !isActive && "bg-soft text-muted ring-1 ring-line/80",
                )}>
                  {isDone && !isActive ? (
                    <Check className="w-3.5 h-3.5" />
                  ) : (
                    <span>{idx + 1}</span>
                  )}
                </div>
                <span className="whitespace-nowrap">{stepDef.shortLabel}</span>
              </button>

              {/* 连接线 */}
              {!isLast && (
                <div className={cn(
                  "w-6 h-px mx-1 shrink-0",
                  stepIdx < currentIdx ? "bg-brand/30" : "bg-line"
                )} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

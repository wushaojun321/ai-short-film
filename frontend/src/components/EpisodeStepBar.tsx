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
    <div className="scroll-shadow-x overflow-x-auto border-b border-line bg-panel/90 px-2 py-0 shadow-xs backdrop-blur-xl sm:px-4 lg:px-7 lg:[mask-image:none]">
      <div className="flex min-w-max items-stretch">
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
                  "relative flex min-h-[68px] flex-col items-center gap-1 border-b-2 px-3 py-2.5 text-xs transition-colors sm:gap-1.5 sm:px-4 sm:py-3 lg:px-5 lg:py-3.5 lg:text-sm",
                  isReachable ? "cursor-pointer" : "cursor-default",
                  isActive
                    ? "border-brand text-brand font-semibold"
                    : "border-transparent",
                  !isActive && isDone && "text-success/75 hover:text-success",
                  !isActive && isCurrent && !isActive && "text-text hover:text-brand",
                  !isActive && !isDone && !isCurrent && "text-muted",
                )}
              >
                {/* 步骤图标 */}
                <div className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center text-xs font-black transition-all sm:w-8 sm:h-8 sm:text-sm",
                  isDone && !isActive && "bg-success-soft text-success ring-1 ring-success/10",
                  isCurrent && isActive && "bg-brand text-white shadow-brand",
                  isCurrent && !isActive && "bg-brand-soft text-brand ring-1 ring-brand/10",
                  isActive && !isCurrent && "bg-brand text-white shadow-brand",
                  !isDone && !isCurrent && !isActive && "bg-soft text-muted ring-1 ring-line/80",
                )}>
                  {isDone && !isActive ? (
                    <Check className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  ) : (
                    <span>{idx + 1}</span>
                  )}
                </div>
                <span className="whitespace-nowrap">{stepDef.shortLabel}</span>
              </button>

              {/* 连接线 */}
              {!isLast && (
                <div className={cn(
                  "w-5 h-px mx-1 shrink-0 sm:w-8",
                  stepIdx < currentIdx ? "bg-gradient-to-r from-success/35 to-brand/30" : "bg-line"
                )} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

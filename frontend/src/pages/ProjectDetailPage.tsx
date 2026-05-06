import { useParams, Navigate, useSearchParams } from "react-router-dom";
import { lazy, Suspense, useEffect, useState } from "react";
import { projectAPI } from "@/lib/api";
import { transformProject } from "@/lib/transforms";
import type { Project } from "@/lib/data";

const ProjectStudioScreen = lazy(() => import("@/components/screens/ProjectStudioScreen"));
const NewProjectScreen = lazy(() => import("@/components/screens/NewProjectScreen"));
const Phase3 = lazy(() =>
  import("@/components/screens/NewProjectScreen").then((module) => ({ default: module.Phase3 }))
);

function DetailFallback() {
  return (
    <div className="min-h-[calc(100dvh-64px)] flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const reload = () => {
    if (!projectId) return;
    setLoading(true);
    projectAPI.get(projectId)
      .then((data) => setProject(transformProject(data)))
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, [projectId]);

  if (!projectId) return <Navigate to="/projects" replace />;
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (notFound || !project) return <Navigate to="/projects" replace />;

  if (project.initStatus !== "initialized") {
    return (
      <Suspense fallback={<DetailFallback />}>
        <NewProjectScreen project={project} onProjectUpdate={reload} />
      </Suspense>
    );
  }

  // 已初始化，但用户点击了「资产库」入口
  if (searchParams.get("view") === "assets") {
    return (
      <div className="min-h-screen">
        <div className="page-shell py-5 sm:py-10">
          <div className="page-header mb-5 sm:mb-7">
            <p className="section-title mb-2">Asset Library</p>
            <h1 className="break-words text-2xl font-black text-text sm:text-4xl">{project.title} · 资产库</h1>
            <p className="text-base text-sub mt-2">查看、重新生成和确认项目资产图片。</p>
          </div>
          <Suspense fallback={<DetailFallback />}>
            <Phase3
              projectId={projectId}
              manageMode={true}
              onFinish={() => {
                const params = new URLSearchParams(searchParams);
                params.delete("view");
                setSearchParams(params, { replace: true });
              }}
            />
          </Suspense>
        </div>
      </div>
    );
  }

  return (
    <Suspense fallback={<DetailFallback />}>
      <ProjectStudioScreen project={project} onProjectUpdate={reload} />
    </Suspense>
  );
}

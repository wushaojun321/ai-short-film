import { useParams, Navigate, useSearchParams } from "react-router-dom";
import { useState, useEffect } from "react";
import { projectAPI } from "@/lib/api";
import { transformProject } from "@/lib/transforms";
import type { Project } from "@/lib/data";
import ProjectStudioScreen from "@/components/screens/ProjectStudioScreen";
import NewProjectScreen from "@/components/screens/NewProjectScreen";
import { Phase3 } from "@/components/screens/NewProjectScreen";

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
    return <NewProjectScreen project={project} onProjectUpdate={reload} />;
  }

  // 已初始化，但用户点击了「资产库」入口
  if (searchParams.get("view") === "assets") {
    return (
      <div className="min-h-screen">
        <div className="page-shell py-10">
          <div className="page-header mb-7">
            <p className="section-title mb-2">Asset Library</p>
            <h1 className="text-4xl font-black text-text">{project.title} · 资产库</h1>
            <p className="text-base text-sub mt-2">查看、重新生成和确认项目资产图片。</p>
          </div>
          <Phase3
            projectId={projectId}
            manageMode={true}
            onFinish={() => {
              const params = new URLSearchParams(searchParams);
              params.delete("view");
              setSearchParams(params, { replace: true });
            }}
          />
        </div>
      </div>
    );
  }

  return <ProjectStudioScreen project={project} onProjectUpdate={reload} />;
}

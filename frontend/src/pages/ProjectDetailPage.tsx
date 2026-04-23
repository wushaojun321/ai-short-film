import { useParams, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { projectAPI } from "@/lib/api";
import { transformProject } from "@/lib/transforms";
import type { Project } from "@/lib/data";
import ProjectStudioScreen from "@/components/screens/ProjectStudioScreen";
import NewProjectScreen from "@/components/screens/NewProjectScreen";

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
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
      <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (notFound || !project) return <Navigate to="/projects" replace />;

  if (project.initStatus !== "initialized") {
    return <NewProjectScreen project={project} onProjectUpdate={reload} />;
  }

  return <ProjectStudioScreen project={project} onProjectUpdate={reload} />;
}

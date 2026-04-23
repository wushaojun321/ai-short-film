import { useParams, Navigate } from "react-router-dom";
import { getProject } from "@/lib/data";
import ProjectStudioScreen from "@/components/screens/ProjectStudioScreen";
import NewProjectScreen from "@/components/screens/NewProjectScreen";

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();

  if (!projectId) return <Navigate to="/projects" replace />;

  const project = getProject(projectId);

  // 项目不存在 → 回首页
  if (!project) return <Navigate to="/projects" replace />;

  // 未初始化 → 显示初始化流程
  if (project.initStatus !== "initialized") {
    return <NewProjectScreen />;
  }

  // 已初始化 → 制作台
  return <ProjectStudioScreen project={project} />;
}

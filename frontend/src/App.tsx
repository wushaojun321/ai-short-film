import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Shell from "@/components/Shell";
import ProjectsHome from "@/pages/ProjectsHome";
import NewProjectPage from "@/pages/NewProjectPage";
import ProjectDetailPage from "@/pages/ProjectDetailPage";
import { ProjectsProvider } from "@/lib/ProjectsContext";
import { CosProvider } from "@/lib/CosContext";

export default function App() {
  return (
    <BrowserRouter>
      <CosProvider>
        <ProjectsProvider>
          <Shell>
            <Routes>
              <Route path="/" element={<Navigate to="/projects" replace />} />
              <Route path="/projects" element={<ProjectsHome />} />
              <Route path="/projects/new" element={<NewProjectPage />} />
              <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
              <Route path="*" element={<Navigate to="/projects" replace />} />
            </Routes>
          </Shell>
        </ProjectsProvider>
      </CosProvider>
    </BrowserRouter>
  );
}

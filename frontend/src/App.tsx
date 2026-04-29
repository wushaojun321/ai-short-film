import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Shell from "@/components/Shell";
import ProjectsHome from "@/pages/ProjectsHome";
import NewProjectPage from "@/pages/NewProjectPage";
import ProjectDetailPage from "@/pages/ProjectDetailPage";
import LoginPage from "@/pages/LoginPage";
import { ProjectsProvider } from "@/lib/ProjectsContext";
import { CosProvider } from "@/lib/CosContext";
import { AuthProvider } from "@/lib/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* 公开路由：登录页，不套 Shell */}
          <Route path="/login" element={<LoginPage />} />

          {/* 受保护路由 */}
          <Route
            path="/*"
            element={
              <ProtectedRoute>
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
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

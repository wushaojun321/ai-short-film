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
        <CosProvider>
          <ProjectsProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<Navigate to="/projects" replace />} />
              <Route path="/projects" element={
                <ProtectedRoute><Shell><ProjectsHome /></Shell></ProtectedRoute>
              } />
              <Route path="/projects/new" element={
                <ProtectedRoute><Shell><NewProjectPage /></Shell></ProtectedRoute>
              } />
              <Route path="/projects/:projectId" element={
                <ProtectedRoute><Shell><ProjectDetailPage /></Shell></ProtectedRoute>
              } />
              <Route path="*" element={<Navigate to="/projects" replace />} />
            </Routes>
          </ProjectsProvider>
        </CosProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

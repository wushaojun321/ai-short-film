import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Shell from "@/components/Shell";
import { ProjectsProvider } from "@/lib/ProjectsContext";
import { CosProvider } from "@/lib/CosContext";
import { AuthProvider } from "@/lib/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

const LoginPage = lazy(() => import("@/pages/LoginPage"));
const ProjectsHome = lazy(() => import("@/pages/ProjectsHome"));
const NewProjectPage = lazy(() => import("@/pages/NewProjectPage"));
const ProjectDetailPage = lazy(() => import("@/pages/ProjectDetailPage"));

function PageFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CosProvider>
          <ProjectsProvider>
            <Suspense fallback={<PageFallback />}>
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
            </Suspense>
          </ProjectsProvider>
        </CosProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

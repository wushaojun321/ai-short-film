import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { projectAPI, type ApiProject } from "./api";
import { transformProject } from "./transforms";
import type { Project } from "./data";

interface ProjectsContextValue {
  projects: Project[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const ProjectsContext = createContext<ProjectsContextValue>({
  projects: [],
  loading: true,
  error: null,
  reload: () => {},
});

export function ProjectsProvider({ children }: { children: ReactNode }) {
  const [apiProjects, setApiProjects] = useState<ApiProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    projectAPI.list()
      .then((data) => setApiProjects(data))
      .catch((err) => setError(err?.response?.data?.detail ?? "加载项目失败"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const projects = apiProjects.map(transformProject);

  return (
    <ProjectsContext.Provider value={{ projects, loading, error, reload }}>
      {children}
    </ProjectsContext.Provider>
  );
}

export function useProjects() {
  return useContext(ProjectsContext);
}

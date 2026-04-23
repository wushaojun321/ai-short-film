import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { projectAPI } from "@/lib/api";
import { transformProject } from "@/lib/transforms";
import type { Project } from "@/lib/data";
import NewProjectScreen from "@/components/screens/NewProjectScreen";
import { useProjects } from "@/lib/ProjectsContext";

export default function NewProjectPage() {
  const navigate = useNavigate();
  const { reload } = useProjects();
  const [project, setProject] = useState<Project | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 创建项目表单
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("古装");

  const handleCreate = async () => {
    if (!title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const data = await projectAPI.create({ title: title.trim(), genre });
      const p = transformProject(data);
      setProject(p);
      reload();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setCreating(false);
    }
  };

  const handleProjectUpdate = async () => {
    if (!project) return;
    try {
      const data = await projectAPI.get(project.id);
      setProject(transformProject(data));
      reload();
    } catch {
      // ignore
    }
  };

  if (project) {
    return <NewProjectScreen project={project} onProjectUpdate={handleProjectUpdate} />;
  }

  return (
    <div className="max-w-md mx-auto py-16 px-6">
      <h1 className="text-2xl font-semibold text-text mb-2">新建项目</h1>
      <p className="text-sm text-sub mb-8">填写基本信息，后续通过上传剧本完成初始化。</p>

      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-sub mb-1.5 block">项目标题 *</label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例：《锦绣长安》"
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-sub mb-1.5 block">类型</label>
          <Input
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            placeholder="古装 / 现代 / 悬疑…"
          />
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex gap-3 pt-2">
          <Button variant="outline" onClick={() => navigate("/projects")} disabled={creating}>
            取消
          </Button>
          <Button onClick={handleCreate} disabled={creating || !title.trim()}>
            {creating
              ? <><Loader2 className="w-4 h-4 animate-spin" />创建中…</>
              : "创建项目"}
          </Button>
        </div>
      </div>
    </div>
  );
}

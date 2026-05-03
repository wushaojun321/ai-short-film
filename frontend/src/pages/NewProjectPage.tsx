import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clapperboard, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { projectAPI } from "@/lib/api";
import { useProjects } from "@/lib/ProjectsContext";

export default function NewProjectPage() {
  const navigate = useNavigate();
  const { reload } = useProjects();
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const data = await projectAPI.create({ title: title.trim() });
      reload();
      navigate(`/projects/${data.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "创建失败");
      setCreating(false);
    }
  };

  return (
    <div className="page-shell flex min-h-[calc(100vh-56px)] items-center justify-center py-10">
      <div className="w-full max-w-md page-panel p-6">
        <div className="mb-6 flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-white shadow-sm">
            <Clapperboard className="h-5 w-5" />
          </div>
          <div>
            <p className="section-title mb-1">New Production</p>
            <h1 className="text-2xl font-semibold text-text">新建项目</h1>
            <p className="text-sm text-sub mt-1">填写基本信息，后续通过上传剧本完成初始化。</p>
          </div>
        </div>

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

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex gap-3 pt-2">
          <Button variant="outline" onClick={() => navigate("/projects")} disabled={creating}>
            取消
          </Button>
          <Button onClick={handleCreate} disabled={creating || !title.trim()}>
            {creating
              ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />创建中…</>
              : "创建项目"}
          </Button>
        </div>
      </div>
      </div>
    </div>
  );
}

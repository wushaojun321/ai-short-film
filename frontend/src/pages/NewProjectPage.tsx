import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { projectAPI } from "@/lib/api";
import { useProjects } from "@/lib/ProjectsContext";

export default function NewProjectPage() {
  const navigate = useNavigate();
  const { reload } = useProjects();
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("古装");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const data = await projectAPI.create({ title: title.trim(), genre });
      reload();
      navigate(`/projects/${data.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "创建失败");
      setCreating(false);
    }
  };

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
              ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />创建中…</>
              : "创建项目"}
          </Button>
        </div>
      </div>
    </div>
  );
}

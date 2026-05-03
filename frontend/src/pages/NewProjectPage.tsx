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
    <div className="page-shell flex min-h-[calc(100dvh-64px)] items-center justify-center py-6 sm:py-12">
      <div className="w-full max-w-xl page-panel tech-border p-5 sm:p-8">
        <div className="mb-6 flex items-start gap-3 sm:mb-8 sm:gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary text-white shadow-brand ring-1 ring-white/10 sm:h-14 sm:w-14">
            <Clapperboard className="h-6 w-6" />
          </div>
          <div>
            <p className="section-title mb-2">New Production</p>
            <h1 className="text-2xl font-black text-text sm:text-3xl">新建项目</h1>
            <p className="text-base text-sub mt-2">填写基本信息，后续通过上传剧本完成初始化。</p>
          </div>
        </div>

        <div className="space-y-4">
        <div>
          <label className="text-sm font-bold text-sub mb-2 block">项目标题 *</label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例：《锦绣长安》"
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
        </div>

        {error && <p className="status-banner status-banner-danger">{error}</p>}

        <div className="flex flex-col gap-3 pt-3 sm:flex-row">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => navigate("/projects")} disabled={creating}>
            取消
          </Button>
          <Button className="w-full sm:w-auto" onClick={handleCreate} disabled={creating || !title.trim()}>
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

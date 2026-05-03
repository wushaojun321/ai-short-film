import { useNavigate, useParams, useLocation } from "react-router-dom";
import { ChevronDown, Clapperboard, Plus, LayoutGrid, LogOut } from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useProjects } from "@/lib/ProjectsContext";
import { useAuth } from "@/lib/AuthContext";
import { cn } from "@/lib/utils";

const statusColor: Record<string, string> = {
  initialized:        "bg-success",
  assets_confirmed:   "bg-warn",
  episodes_confirmed: "bg-warn",
  script_uploaded:    "bg-slate-400",
  not_started:        "bg-slate-600",
};

export default function Nav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId } = useParams<{ projectId: string }>();
  const { projects } = useProjects();
  const { user, logout } = useAuth();
  const currentProject = projects.find((p) => p.id === projectId);
  const isHome = location.pathname === "/projects" || location.pathname === "/";

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 border-b border-line bg-panel/95 shadow-sm backdrop-blur-xl">
      <div className="h-full flex items-center px-4 gap-3">

        {/* Logo */}
        <button
          onClick={() => navigate("/projects")}
          className="flex items-center gap-2.5 text-text hover:opacity-95 transition-opacity shrink-0 group"
          aria-label="首页"
        >
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-sm ring-1 ring-black/10 group-hover:shadow-brand transition-shadow">
            <Clapperboard className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-sm text-text hidden sm:block tracking-tight">
            短剧制作
          </span>
        </button>

        {/* 路径分隔 + 项目切换 */}
        {!isHome && (
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-line text-lg font-light">/</span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-semibold",
                  "text-text hover:bg-soft transition-colors duration-150 min-w-0 max-w-[260px] group border border-transparent hover:border-line"
                )}>
                  <span className="truncate">{currentProject?.title ?? "项目"}</span>
                  <ChevronDown className="w-3.5 h-3.5 text-muted shrink-0 transition-transform group-data-[state=open]:rotate-180" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-72 p-1.5">
                <DropdownMenuLabel className="px-2 py-1.5 text-xs text-muted font-semibold uppercase tracking-wider">
                  我的项目
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="my-1" />
                {projects.map((p) => (
                  <DropdownMenuItem
                    key={p.id}
                    onClick={() => navigate(`/projects/${p.id}`)}
                    className={cn(
                      "flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer",
                      p.id === projectId && "bg-brand-soft"
                    )}
                  >
                    <div className={cn(
                      "w-2 h-2 rounded-full shrink-0",
                      statusColor[p.initStatus] ?? "bg-line"
                    )} />
                    <div className="min-w-0 flex-1">
                      <div className={cn(
                        "text-sm font-medium truncate",
                        p.id === projectId ? "text-brand" : "text-text"
                      )}>
                        {p.title}
                      </div>
                      <div className="text-xs text-muted truncate">{p.stage}</div>
                    </div>
                    {p.id === projectId && (
                      <span className="text-2xs bg-brand text-white px-1.5 py-0.5 rounded-full font-bold shrink-0">
                        当前
                      </span>
                    )}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator className="my-1" />
                <DropdownMenuItem
                  onClick={() => navigate("/projects/new")}
                  className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-brand cursor-pointer hover:bg-brand-soft"
                >
                  <div className="w-5 h-5 rounded-md bg-brand-soft flex items-center justify-center">
                    <Plus className="w-3.5 h-3.5 text-brand" />
                  </div>
                  <span className="text-sm font-semibold">新建项目</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}

        {/* 首页副标题 */}
        {isHome && (
          <span className="hidden rounded-full border border-line bg-soft px-2.5 py-1 text-xs text-muted sm:block">
            AI Production Console
          </span>
        )}

        {/* 右侧操作区 */}
        <div className="ml-auto flex items-center gap-2">
          {isHome && (
            <button
              onClick={() => navigate("/projects")}
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-line text-xs font-medium text-sub hover:border-brand/35 hover:bg-soft hover:text-text transition-colors"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              所有项目
            </button>
          )}
          {/* 用户菜单 */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-1.5 px-2 py-1 rounded-lg border border-line bg-panel hover:border-brand/35 hover:bg-soft transition-colors group">
                <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white text-xs font-bold shadow-sm">
                  {user?.username?.[0]?.toUpperCase() ?? "U"}
                </div>
                <span className="text-xs font-medium text-sub hidden sm:block max-w-[80px] truncate">
                  {user?.username}
                </span>
                <ChevronDown className="w-3 h-3 text-muted hidden sm:block group-data-[state=open]:rotate-180 transition-transform" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44 p-1">
              <DropdownMenuLabel className="px-2 py-1.5 text-xs text-muted font-semibold">
                {user?.username}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleLogout}
                className="flex items-center gap-2 px-2 py-1.5 text-sm text-red-500 cursor-pointer hover:bg-red-50 rounded-md"
              >
                <LogOut className="w-3.5 h-3.5" />
                退出登录
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}

import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Clapperboard } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { authAPI } from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";

type Tab = "login" | "register";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [tab, setTab] = useState<Tab>("login");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "login") {
        const res = await authAPI.login(username, password);
        login(res.username, res.access_token);
        navigate("/projects", { replace: true });
      } else {
        const res = await authAPI.register(username, password, inviteCode);
        login(res.username, res.access_token);
        navigate("/projects", { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-workspace flex min-h-screen flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center shadow-md ring-1 ring-black/10">
            <Clapperboard className="w-6 h-6 text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold text-text">短剧制作</h1>
          </div>
        </div>

        {/* Card */}
        <div className="page-panel p-6">
          {/* Tabs */}
          <div className="flex gap-0 mb-6 bg-soft rounded-xl p-1 ring-1 ring-line/60">
            {(["login", "register"] as Tab[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => { setTab(t); setError(""); }}
                className={
                  "flex-1 py-1.5 text-sm font-medium rounded-md transition-all " +
                  (tab === t
                    ? "bg-panel text-brand shadow-sm"
                    : "text-muted hover:text-text")
                }
              >
                {t === "login" ? "登录" : "注册"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-sub">用户名</label>
              <Input
                type="text"
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                autoComplete="username"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-sub">密码</label>
              <Input
                type="password"
                placeholder="请输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={tab === "login" ? "current-password" : "new-password"}
              />
            </div>

            {tab === "register" && (
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-sub">激活码</label>
                <Input
                  type="text"
                  placeholder="请输入激活码"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value.trim())}
                  required
                  autoComplete="off"
                />
              </div>
            )}

            {error && (
              <p className="text-xs text-danger bg-danger-soft border border-danger/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <Button type="submit" disabled={loading} className="w-full mt-1">
              {loading ? "处理中..." : tab === "login" ? "登录" : "注册"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

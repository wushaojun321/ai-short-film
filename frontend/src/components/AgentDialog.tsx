/**
 * AgentDialog — AI 修改对话框
 *
 * 打开时自动拉取（或创建）与当前 target 绑定的对话历史。
 * 用户发消息 → POST /conversations/{id}/chat → 显示回复 + 通知父组件刷新。
 */
import { useState, useEffect, useRef } from "react";
import { Loader2, Send, Bot, User, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { conversationAPI, type ApiConversation, type ApiMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

interface AgentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 对话绑定的对象类型（asset / shot_image / shot_video / episode） */
  targetType: string;
  targetId: string;
  projectId: string;
  /** 标题，例如「AI 修改 · 主角陈诺」 */
  title?: string;
  /** 生成任务启动后回调，父组件用来刷新资产/分镜状态 */
  onTaskStarted?: () => void;
}

// ── 消息气泡 ──────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ApiMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex gap-2.5 mb-4", isUser && "flex-row-reverse")}>
      <div className={cn(
        "w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5",
        isUser ? "bg-brand text-white" : "bg-soft border border-line",
      )}>
        {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5 text-brand" />}
      </div>
      <div className={cn(
        "max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
        isUser
          ? "bg-brand text-white rounded-tr-sm"
          : "bg-soft text-text rounded-tl-sm border border-line",
      )}>
        {msg.content}
      </div>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────

export default function AgentDialog({
  open,
  onOpenChange,
  targetType,
  targetId,
  projectId,
  title = "AI 修改助手",
  onTaskStarted,
}: AgentDialogProps) {
  const [conv, setConv] = useState<ApiConversation | null>(null);
  const [messages, setMessages] = useState<ApiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 打开时加载对话（取最近的，没有就创建）
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    conversationAPI.list({ target_id: targetId })
      .then(async (list) => {
        if (list.length > 0) {
          const existing = list[0];
          setConv(existing);
          setMessages(existing.messages.filter(m => m.role !== "system"));
        } else {
          const newConv = await conversationAPI.create({
            target_type: targetType,
            target_id: targetId,
            project_id: projectId,
            title,
          });
          setConv(newConv);
          setMessages([]);
        }
      })
      .catch(() => { /* ignore */ })
      .finally(() => setLoading(false));
  }, [open, targetId]);

  // 自动滚到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !conv || sending) return;
    const userContent = input.trim();
    setInput("");
    setSending(true);

    // 乐观更新——先加用户消息
    const userMsg: ApiMessage = {
      role: "user",
      content: userContent,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await conversationAPI.chat(conv.id, userContent);

      const assistantMsg: ApiMessage = {
        role: "assistant",
        content: res.reply,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // 如果有工具调用（即启动了生成任务），通知父组件刷新
      if (res.tool_calls_made.length > 0) {
        onTaskStarted?.();
      }
    } catch (err: unknown) {
      const errMsg: ApiMessage = {
        role: "assistant",
        content: `出错了：${err instanceof Error ? err.message : "请求失败"}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setSending(false);
    }
  };

  const handleClear = async () => {
    if (!conv) return;
    await conversationAPI.delete(conv.id);
    const newConv = await conversationAPI.create({
      target_type: targetType,
      target_id: targetId,
      project_id: projectId,
      title,
    });
    setConv(newConv);
    setMessages([]);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md h-[600px] flex flex-col p-0 gap-0">
        <DialogHeader className="px-4 py-3 border-b border-line shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand" />
              <DialogTitle className="text-sm font-semibold">{title}</DialogTitle>
            </div>
            {messages.length > 0 && (
              <button
                onClick={handleClear}
                className="text-muted hover:text-danger transition-colors p-1"
                title="清空对话"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </DialogHeader>

        {/* 消息区域 */}
        <div className="flex-1 overflow-y-auto px-4 py-4 min-h-0">
          {loading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="w-5 h-5 animate-spin text-muted" />
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center gap-3">
              <Bot className="w-8 h-8 text-muted" />
              <div>
                <p className="text-sm font-medium text-text">AI 修改助手</p>
                <p className="text-xs text-muted mt-1">描述你的修改需求，AI 会自动调用工具完成。</p>
                <p className="text-xs text-muted mt-0.5">例如：「把提示词里的夜景改成日景，然后重新生成」</p>
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <MessageBubble key={i} msg={msg} />
              ))}
              {sending && (
                <div className="flex gap-2.5 mb-4">
                  <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-soft border border-line">
                    <Bot className="w-3.5 h-3.5 text-brand" />
                  </div>
                  <div className="bg-soft border border-line rounded-2xl rounded-tl-sm px-3.5 py-2.5">
                    <Loader2 className="w-4 h-4 animate-spin text-muted" />
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        {/* 输入区域 */}
        <div className="px-4 py-3 border-t border-line shrink-0">
          <div className="flex gap-2 items-end">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="描述你的修改需求… (Enter 发送，Shift+Enter 换行)"
              rows={2}
              className="resize-none text-sm"
              disabled={sending || loading}
            />
            <Button
              size="sm"
              onClick={handleSend}
              disabled={!input.trim() || sending || loading}
              className="shrink-0 h-9 w-9 p-0"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

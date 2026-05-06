import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  width?: string;
}

export function Sheet({ open, onClose, title, children, width = "sm:w-[480px]" }: SheetProps) {
  // 点击遮罩关闭
  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  // ESC 关闭
  React.useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <>
      {/* 遮罩 */}
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/70 backdrop-blur-md transition-opacity duration-200",
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={handleOverlayClick}
      />
      {/* 抽屉面板 */}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-full max-w-full bg-panel/95 shadow-card-hover flex flex-col transition-transform duration-300 ease-out border-l border-line backdrop-blur-xl sm:w-[calc(100vw-1rem)]",
          width,
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        <div className="flex items-center justify-between gap-3 px-4 py-4 border-b border-line bg-elev/70 shrink-0 sm:px-6 sm:py-5">
          {title && <h3 className="min-w-0 font-bold text-text text-base leading-snug">{title}</h3>}
          <button
            onClick={onClose}
            className="ml-auto inline-flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-soft/70 text-muted transition-colors hover:border-brand/40 hover:text-text"
            aria-label="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6 sm:py-5">
          {children}
        </div>
      </div>
    </>
  );
}

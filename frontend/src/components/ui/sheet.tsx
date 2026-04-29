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

export function Sheet({ open, onClose, title, children, width = "w-[480px]" }: SheetProps) {
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
          "fixed inset-0 z-40 bg-black/30 transition-opacity duration-200",
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={handleOverlayClick}
      />
      {/* 抽屉面板 */}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-in-out",
          width,
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-line shrink-0">
          {title && <h3 className="font-semibold text-text text-sm">{title}</h3>}
          <button
            onClick={onClose}
            className="ml-auto text-muted hover:text-text transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {children}
        </div>
      </div>
    </>
  );
}

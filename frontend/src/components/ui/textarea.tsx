import * as React from "react"
import { cn } from "@/lib/utils"

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex min-h-[96px] w-full rounded-xl border border-line bg-elev/80 px-4 py-3 text-base text-text shadow-xs placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/25 focus-visible:border-brand disabled:cursor-not-allowed disabled:opacity-50 resize-none sm:text-sm",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }

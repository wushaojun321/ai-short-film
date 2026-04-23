import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default:     "border-transparent bg-primary text-white",
        secondary:   "border-line bg-soft text-sub",
        outline:     "border-line text-text bg-white",
        success:     "border-transparent bg-brand-soft text-brand",
        warning:     "border-transparent bg-warn-soft text-warn",
        destructive: "border-transparent bg-danger-soft text-danger",
        primary:     "border-transparent bg-primary-soft text-primary font-bold",
      },
    },
    defaultVariants: { variant: "default" },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }

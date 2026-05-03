import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-bold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:pointer-events-none disabled:opacity-50 cursor-pointer select-none",
  {
    variants: {
      variant: {
        default:     "bg-primary text-white shadow-brand hover:bg-primary/90 hover:shadow-card-hover active:scale-[0.97] active:shadow-sm",
        primary:     "bg-primary text-white shadow-brand hover:bg-primary/90 hover:shadow-card-hover active:scale-[0.97]",
        secondary:   "bg-soft text-text border border-line shadow-xs hover:bg-elev hover:border-brand/45 active:scale-[0.97]",
        ghost:       "text-sub hover:bg-soft hover:text-text active:bg-line",
        outline:     "border border-line bg-panel/85 text-text shadow-xs hover:bg-elev hover:border-brand/45 hover:text-brand active:scale-[0.97]",
        destructive: "bg-danger text-white shadow-sm hover:bg-danger/90 active:scale-[0.97]",
        link:        "text-brand underline-offset-4 hover:underline p-0 h-auto shadow-none",
      },
      size: {
        default: "h-11 px-5 py-2.5",
        sm:      "h-9 rounded-lg px-3.5 text-xs",
        lg:      "h-12 rounded-2xl px-7 text-base",
        icon:    "h-11 w-11",
        "icon-sm": "h-9 w-9 rounded-lg",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }

import * as React from "react"
import { cn } from "../../lib/utils"

type GlassCardProps = React.HTMLAttributes<HTMLDivElement>

export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-xl border border-white/20 bg-white/70 backdrop-blur-md shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg dark:border-white/10 dark:bg-gray-900/55",
        className
      )}
      {...props}
    />
  )
)

GlassCard.displayName = "GlassCard"

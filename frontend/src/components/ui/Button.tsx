import * as React from "react"
import { cn } from "../../lib/utils"

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "accent"
  size?: "default" | "sm" | "lg" | "icon"
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    return (
      <button
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
          {
            "bg-accent-500 dark:bg-accent-600 text-white hover:bg-accent-600 dark:hover:bg-accent-700 shadow-lg": variant === "default",
            "bg-accent-600 dark:bg-accent-700 text-white hover:bg-accent-700 dark:hover:bg-accent-800 shadow-lg": variant === "accent",
            "bg-destructive text-destructive-foreground hover:bg-destructive/90 dark:hover:bg-destructive/80": variant === "destructive",
            "border border-accent-200 dark:border-accent-700 bg-background hover:bg-accent-50 dark:hover:bg-accent-900/50 hover:text-accent-700 dark:hover:text-accent-300 hover:border-accent-300 dark:hover:border-accent-600": variant === "outline",
            "bg-secondary text-secondary-foreground hover:bg-secondary/80 dark:hover:bg-secondary/70": variant === "secondary",
            "hover:bg-accent-50 dark:hover:bg-gray-700 hover:text-accent-700 dark:hover:text-accent-300": variant === "ghost",
            "text-primary underline-offset-4 hover:underline": variant === "link",
          },
          {
            "h-10 px-3 sm:px-4 py-2 text-sm sm:text-base": size === "default",
            "h-8 sm:h-9 rounded-md px-2 sm:px-3 text-xs sm:text-sm": size === "sm",
            "h-11 sm:h-12 rounded-md px-6 sm:px-8 text-base sm:text-lg": size === "lg",
            "h-8 w-8 sm:h-10 sm:w-10": size === "icon",
          },
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }

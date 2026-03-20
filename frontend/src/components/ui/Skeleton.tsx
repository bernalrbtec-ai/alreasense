import * as React from "react"
import { cn } from "../../lib/utils"

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-gray-200/80 dark:bg-gray-700/70", className)}
      {...props}
    />
  )
}

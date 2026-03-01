import React from 'react'
import { cn } from '../../lib/utils'

interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  className?: string
}

export const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn('text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 block', className)}
        {...props}
      />
    )
  }
)

Label.displayName = 'Label'

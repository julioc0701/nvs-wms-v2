import { cn } from '../../lib/utils'

const variants = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700 border border-blue-700/20',
  subtle: 'bg-white text-slate-700 hover:bg-slate-50 border border-slate-200',
  danger: 'bg-red-600 text-white hover:bg-red-700 border border-red-700/20',
}

export default function Button({ className, variant = 'subtle', children, ...props }) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl transition-colors min-h-[44px] active:scale-95',
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
}


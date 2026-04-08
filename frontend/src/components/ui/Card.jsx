import { cn } from '../../lib/utils'

export default function Card({ className, children }) {
  return (
    <div className={cn('bg-white border border-slate-200 rounded-2xl shadow-sm', className)}>
      {children}
    </div>
  )
}


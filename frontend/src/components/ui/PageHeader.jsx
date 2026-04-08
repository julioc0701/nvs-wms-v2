import { ArrowLeft } from 'lucide-react'
import Button from './Button'

export default function PageHeader({ title, subtitle, backLabel = 'Voltar', onBack, right }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div className="flex items-start gap-3">
        {onBack && (
          <Button variant="subtle" className="mt-1" onClick={onBack} aria-label={backLabel}>
            <ArrowLeft size={16} />
            {backLabel}
          </Button>
        )}
        <div>
          <h1 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight">{title}</h1>
          {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
        </div>
      </div>
      {right}
    </div>
  )
}


export default function SkeletonRows({ rows = 5 }) {
  return (
    <div className="animate-pulse space-y-3 py-2">
      {Array.from({ length: rows }).map((_, idx) => (
        <div key={idx} className="h-10 rounded-lg bg-slate-100" />
      ))}
    </div>
  )
}


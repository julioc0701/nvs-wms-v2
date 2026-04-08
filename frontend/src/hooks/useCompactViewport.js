import { useEffect, useState } from 'react'

export function useCompactViewport(maxHeight = 800) {
  const getValue = () =>
    typeof window !== 'undefined' ? window.innerHeight <= maxHeight : false

  const [compact, setCompact] = useState(getValue)

  useEffect(() => {
    const onResize = () => setCompact(getValue())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [maxHeight])

  return compact
}

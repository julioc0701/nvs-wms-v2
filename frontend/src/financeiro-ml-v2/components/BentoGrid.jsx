/**
 * Wrapper de CSS Grid: 6 colunas, auto-rows 90px, gap 10px.
 * Filhos definem seu próprio `gridColumn: span N` e `gridRow: span N` via style inline.
 * Auto-flow padrão preenche buracos automaticamente.
 */
export function BentoGrid({ children }) {
  return (
    <div
      className="mb-3"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(6, 1fr)',
        gridAutoRows: '90px',
        gap: '10px',
      }}
    >
      {children}
    </div>
  )
}

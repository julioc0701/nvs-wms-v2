# LAUDO TÉCNICO — Bug freeze do date picker em `/financeiro-ml/resumo-v2`

**Data:** 2026-05-27
**Status:** REPRODUZIDO · root cause isolado · solução pendente
**Branch:** `feature/financeiro-ml`

---

## 1. Sintoma

Ao clicar num dia dentro do calendar popup do componente `DateRangePicker` (botão "De" ou "Até"), o renderer do Chrome **trava completamente** (Página sem resposta · CPU pinned 100%). Comportamento permanente até kill da tab.

## 2. Como o usuário disparou

1. Abre `/financeiro-ml/resumo-v2`
2. Clica botão "De" (ou "Até") → calendar popup aparece OK
3. Clica num dia (ex: 15) → renderer freeze

## 3. Stack envolvida

- React **18** + Vite 5.4.21 + Tailwind
- `<StrictMode>` habilitado em `main.jsx`
- `react-day-picker` **8.10.1** (downgrade de 10.0.1 que tinha mesmo bug)
- `date-fns` 3.6.0
- `@tanstack/react-table` v8 (DataTable.jsx)
- `@tanstack/react-query` v5 (mutation)
- Recharts (charts dentro dos tiles)
- `@radix-ui/react-tooltip` (não usado neste fluxo)

## 4. Cronologia da investigação

### Tentativas que NÃO resolveram
1. **Memoização** `useMemo` no Date selected + `useCallback` nos handlers do DateRangePicker → sem efeito
2. **Downgrade** `react-day-picker` 10.0.1 → 8.10.1 + `date-fns` 4.3.0 → 3.6.0 → sem efeito
3. **Hard refresh** browser (Cmd+Shift+R) → sem efeito
4. **Aba anônima** (sem cache, sem extensões) → sem efeito
5. **Vite restart limpo** sugerido mas não confirmado se feito → assumido sem efeito

### Bisect que ISOLOU o culprit

Reproduzi em Chrome real do Julio via `Claude in Chrome` MCP (não reproduzi em Chromium isolado via JS `.click()` — só com evento mouse REAL).

| Configuração | Resultado |
|---|---|
| Tudo montado (HeroTile, MediumTile, DonutTile, SmallTiles, DataTable, FilterChips) | **TRAVA** ao clicar dia |
| HeroTile/MediumTile/DonutTile comentados, resto presente | **TRAVA** ao clicar dia |
| HeroTile/MediumTile/DonutTile + DataTable + FilterChips comentados | **FUNCIONA** |
| DataTable presente com `chips={null}` (sem FilterChips) | **TRAVA** ao clicar dia |

**Conclusão:** A presença do componente `DataTable.jsx` (TanStack Table v8 via `useReactTable`) é o trigger do loop. Recharts ResponsiveContainer e FilterChips estão inocentes.

## 5. Diferença chave: mouse real vs JS click

- Em meu Chromium isolado, simulei o click com `element.click()` (JS) → **FUNCIONOU SEMPRE**
- No Chrome real do Julio, o click via `Input.dispatchMouseEvent` (CDP) → **TRAVA**

A diferença é que evento real dispara `mousedown` → `mouseup` → `click`. JS `.click()` só dispara `click`.

Meu `DateRangePicker.jsx` tem um listener `document.mousedown` para fechar o popup ao clicar fora (`useEffect` com `document.addEventListener('mousedown', handler)`).

## 6. Hipótese central da causa raiz

O loop é resultado de **combinação tóxica**:

1. Click real no dia do picker dispara `mousedown` primeiro
2. Meu `document.mousedown` handler roda — checa `ref.current.contains(target)`. Há **dois `SingleDatePicker` instances** (De + Até), cada um com seu próprio listener. O listener do "Até" vê que o click NÃO está em sua ref e chama `setOpen(false)` (no-op se já false, mas dispara fluxo React)
3. `mouseup` + `click` → `DayPicker.onSelect` → meu `handleSelect` → `onChange(toISO(d))` + `setOpen(false)`
4. `onChange` propaga até `Resumo.jsx`: `setFiltros((f) => ({...f, data_inicio, data_fim, page: 1}))`
5. Resumo re-renderiza → passa `data={resultado?.tabela}` (undefined inicialmente) pro `DataTable`
6. **`DataTable.jsx` faz `data: data || []`** — cria array novo `[]` a cada render
7. `useReactTable` recebe nova ref `data` → internamente dispara setState (provavelmente em useEffect que normaliza rows/cols)
8. Re-render → novo `[]` → loop infinito
9. `React.StrictMode` em dev DOBRA invocações, amplifica o problema

Por que só com mouse real? Provavelmente o `document.mousedown` listener entrega um update extra que o React 18 automatic batching NÃO consegue agrupar com o `setOpen(false)` do `handleSelect`, criando 2 ciclos de render em vez de 1 — e com TanStack Table sob StrictMode, isso vira loop.

## 7. Fix aplicado mas não validado

Em `DataTable.jsx`:

```js
const EMPTY_DATA = Object.freeze([])  // referência estável

const tableData = data && data.length ? data : EMPTY_DATA

const table = useReactTable({
  data: tableData,  // antes era: data: data || []
  ...
})
```

Estabiliza referência. Tentei testar mas a sessão tava extensa e usuário pediu pausa antes de confirmar.

## 8. Outras hipóteses NÃO descartadas

A) **`onSortingChange: setSorting`** no `useReactTable` — `setSorting` é referência estável (do useState), mas TanStack pode estar tratando como nova prop e disparando state interno.

B) **Mistura `state` controlled + uncontrolled** no useReactTable — só passamos `state: { sorting }` parcialmente. TanStack pode preferir tudo controlled ou nada.

C) **`getCoreRowModel()` / `getSortedRowModel()`** sendo chamadas a cada render (não são memoized). TanStack docs recomendam manter referência estável.

D) **StrictMode + TanStack Table v8** — bug conhecido em algumas versões com double-invocation.

E) **react-day-picker** ainda tendo issue interno mesmo na v8 — improvável (battle-tested via shadcn) mas não impossível.

## 9. O que SEI com certeza

- Bug é determinístico no Chrome real do Julio
- Trigger: click real (mouse) num dia do calendar
- DataTable presente = trigger. Removido = sem bug
- Recharts NÃO é o culprit
- FilterChips NÃO é o culprit
- v1 (`/financeiro-ml/resumo`) totalmente intocada, **funciona normalmente** — usuário pode usar enquanto investiga

## 10. Arquivos relevantes

- [DateRangePicker.jsx](../../frontend/src/financeiro-ml-v2/components/DateRangePicker.jsx) — wrap react-day-picker
- [DataTable.jsx](../../frontend/src/financeiro-ml-v2/components/DataTable.jsx) — useReactTable
- [Resumo.jsx](../../frontend/src/financeiro-ml-v2/pages/Resumo.jsx) — orquestrador
- [main.jsx](../../frontend/src/main.jsx) — StrictMode wrapper

## 11. Próximos passos sugeridos

1. **Validar fix `EMPTY_DATA` stabilization** primeiro (mais provável)
2. Se não resolver:
   - Memoizar `getCoreRowModel()`, `getSortedRowModel()` com `useMemo`
   - Remover `document.mousedown` listener; usar `onBlur` ou portal isolado
   - Renderizar DayPicker em `createPortal` pra isolar do render tree
   - Testar sem `<StrictMode>` (apenas pra confirmar hipótese — não é solução final)
3. Convocar especialistas: backend não envolvido, mas full-stack + React profundo são os necessários

# ANTES vs DEPOIS — Como o Operador Sente

## Cenário 1: Operador escaneia SKU inválido

### ANTES
Operador escaneia rápido no fluxo de picking.  
Confirma item inválido.  
Sistema usa `alert()` bloqueante.  
Operador perde ritmo e interpreta como travamento.

### DEPOIS
Operador confirma item inválido.  
Toast vermelho não bloqueante aparece com mensagem clara e ação sugerida.  
Fluxo continua sem perda de contexto.

**Impacto de negócio:** menos interrupção, menos suporte, maior confiança operacional.

---

## Cenário 2: Supervisor abre dashboard

### ANTES
Tela mostra texto de carregamento e spinner simples.  
Percepção: "travou?" em redes lentas.

### DEPOIS
Skeleton de cards/KPIs aparece instantaneamente.  
Percepção: "está carregando corretamente".

**Impacto psicológico:** mesma latência real, percepção significativamente melhor.

---

## Cenário 3: Impressora falha

### ANTES
Sem padrão global de feedback para falha de impressão.  
Falhas podem gerar retrabalho e dúvidas.

### DEPOIS
Toast crítico + status persistente de impressão + botão de retry.  
Erro vira ação imediata, não incidente tardio.

**Impacto financeiro:** redução de devoluções/reprocessamento e de custo de suporte.

---

## Cenário 4: ShortageReport (tela crítica)

### ANTES
Visual destoante do app principal.  
Sem skeleton e com interação baseada em prompt/alert.  
Supervisor percebe baixa maturidade na tela mais sensível.

### DEPOIS
Tela alinhada ao design system (layout, tokens, botões, feedback).  
Tabela com skeleton, filtros, export e feedback padronizado.

**Impacto de confiança:** menos checagem paralela, decisão mais rápida.

---

## Resumo de Impacto Visual/UX

| Mudança | Antes | Depois | Impacto esperado |
|---|---|---|---|
| Alert/Prompt/Confirm | Bloqueia e quebra foco | Toast + diálogo de produto | +produtividade e -suporte |
| Loading textual | Incerteza | Skeleton orientado por contexto | -desconfiança |
| Erro de impressão | Inconsistente | Feedback padronizado + retry | -retrabalho |
| Shortage visual | Tela “isolada” | Padrão único de produto | +confiança decisória |
| Navegação mobile supervisor | Limitada | Navegação equivalente desktop/mobile | +usabilidade |

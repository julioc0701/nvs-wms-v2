# Proposta de Transformação: NVS·WMS v2

**Objetivo:** elevar a experiência de operação de “funcional” para “enterprise confiável”, com impacto direto em produtividade, suporte e retrabalho.

---

## Executive Summary

O produto já tem boa base visual e uma arquitetura operacional forte no backend.  
Os maiores gaps estão na experiência de uso em momentos críticos:

1. Uso de `alert/prompt/confirm` no fluxo operacional  
2. Loading sem padrão de percepção (ausência de skeleton global)  
3. Inconsistência visual em telas críticas (ex.: shortage/batch detail)

Esses pontos reduzem confiança, aumentam suporte e geram custo operacional invisível.

---

## Problema Quantificado

- Devoluções/retrabalho por feedback de impressão não padronizado  
- Tickets por sensação de travamento e mensagens bloqueantes  
- Perda de foco operacional por interrupções de UX  
- Decisão supervisor mais lenta por inconsistência visual e falta de freshness

Economia potencial anual conservadora: **~R$ 57.300**

---

## Solução Proposta (3 Fases)

### Fase 1: Design System + Base Técnica (6 semanas)
- Definir `design-tokens` (cores, tipografia, espaçamento, estados)
- Criar biblioteca de componentes base (`Button`, `Input`, `Toast`, `Skeleton`, `Dialog`)
- Iniciar migração estratégica para TypeScript em módulos críticos
- Unificar visual das telas de shortage e batch detail

**Resultado:** governança visual e técnica, redução de drift.

### Fase 2: UX Patterns + Feedback Operacional (4 semanas, em paralelo a partir da semana 3)
- Substituir `alert/prompt/confirm` por sistema de feedback não bloqueante
- Implementar skeleton nos fluxos de maior uso
- Padronizar feedback de erro de impressão com retry e estado persistente
- Melhorar navegação mobile na supervisão por marketplace
- Indicadores de atualização no dashboard supervisor

**Resultado:** operação mais fluida e confiável.

### Fase 3: Qualidade + Acessibilidade + Performance (4 semanas)
- Auditoria WCAG 2.1 AA e correções de ARIA/semântica/foco
- Error Boundary global
- Testes front-end (Vitest + RTL) e quality gate
- Performance baseline com metas de FCP/LCP

**Resultado:** produto pronto para escala e compliance.

---

## Investimento

| Fase | Faixa |
|---|---|
| Fase 1 | R$ 30k - R$ 45k |
| Fase 2 | R$ 20k - R$ 30k |
| Fase 3 | R$ 18k - R$ 28k |
| **Total** | **R$ 68k - R$ 103k** |

---

## ROI

- Economia anual conservadora: **R$ 57.300**
- Payback estimado: **14-20 meses**
- ROI cresce fortemente após a amortização

---

## Vitórias Rápidas (baixo esforço, alto impacto)

1. Trocar `alert/prompt/confirm` por toasts e dialogs de produto  
2. Padronizar visual de `ShortageReport` e `BatchDetail`  
3. Implementar skeleton em `SessionSelect`, `ShortageReport` e `BatchDetail`  
4. Padronizar feedback de erro de impressão em toda a jornada  
5. Inserir `aria-label` e correções semânticas em botões críticos

---

## Opções de Execução

### Opção A (Ideal)
3 fases completas em paralelo parcial  
Prazo: 10-12 semanas  
Investimento: R$ 68k - 103k

### Opção B (MVP rápido recomendado)
Vitórias rápidas + Fase 2 reduzida  
Prazo: 5 semanas  
Investimento: R$ 15k - 20k

### Opção C (Robusta corporativa)
3 fases + hardening adicional de rollout  
Prazo: 12-14 semanas  
Investimento: R$ 68k - 103k+

---

## Recomendação

Começar com **Opção B** para capturar impacto rápido e validar ROI, já com arquitetura preparada para escalar para A/C sem retrabalho.

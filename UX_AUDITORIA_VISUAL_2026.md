# Auditoria Visual e UX - NVS WMS v2

Data: 27/03/2026  
Escopo: frontend operacional completo (Login, Sessões, Picking, Supervisor, Faltas)

## Resumo Executivo

O produto tem base visual forte e identidade própria, mas ainda sofre com variacao de layout entre telas e falta de regras fixas de densidade.  
Hoje o sistema parece "bom por tela". O objetivo para nivel enterprise e "bom como plataforma".

Score geral atual: **6.6/10**

## Scores por dimensão

1. Consistencia visual: 6.0  
2. Hierarquia de informacao: 7.2  
3. Fluxo operacional (velocidade): 7.4  
4. Densidade inteligente (one-screen): 5.6  
5. Feedback e estados: 7.0  
6. Design system e tokens: 5.4  
7. Acessibilidade visual: 5.8  
8. Maturidade enterprise: 6.3

## Achados principais

1. Existe drift de layout entre Supervisor, Sessões e Picking.
2. Algumas areas mudam muito de escala (cards, graficos, espacos), sem uma regra unica.
3. O sistema de feedback melhorou, mas ainda convive com mensagens de contexto em blocos persistentes em algumas jornadas.
4. Componentes base existem, mas o contrato visual ainda esta parcialmente "no CSS solto".
5. Os dashboards ficaram melhores, porem precisam de grammar fixa para nao oscilar entre tentativas.

## Benchmark e princípios usados

1. IBM Carbon - dashboards e visualizacao de dados
2. Atlassian Design - spacing, tokens e layout primitives
3. PatternFly Dashboard - organizacao por cards, prioridade e densidade
4. Material principles para hierarquia e legibilidade operacional

## Melhorias aplicadas agora (neste ciclo)

1. Expansao de tokens de design:
   - Arquivo: `frontend/src/design-tokens.js`
   - Incluso: `chart`, `spacing`, `density`, `shadow.elevated`

2. Utilitarios visuais de sistema adicionados:
   - Arquivo: `frontend/src/index.css`
   - Incluso: `section-kicker`, `section-title`, `metric-tile`, `metric-label`, `metric-value`, `chart-card`, `action-rail`

3. Estrutura do topo da tela de Sessões reorganizada:
   - Arquivo: `frontend/src/pages/SessionSelect.jsx`
   - Ação de troca de usuario movida para rail lateral visual sem deslocar o card principal.

## Riscos UX ainda abertos

1. Supervisor ainda alterna densidade perceptiva dependendo da quantidade de dados.
2. Picking mistura estilos de "painel premium" com trechos de "modo utilitario".
3. Falta um preset formal de viewport por perfil (operador vs supervisor) para garantir "uma tela" com confianca.

## Recomendação técnica de curto prazo

1. Fixar 2 perfis oficiais de densidade:
   - `compact` para operador
   - `comfortable` para supervisor/master

2. Instituir 5 primitivas obrigatorias:
   - `PageShell`
   - `SectionCard`
   - `MetricCard`
   - `ActionRail`
   - `ChartCard`

3. Congelar grammar de ranking de operador:
   - um grafico principal (padrao)
   - um fallback para tela pequena

4. Padronizar estados visuais:
   - loading
   - empty
   - warning
   - error
   - success

## Plano de execução acelerado (com IA executando)

Sem equipe tradicional, o ritmo e muito mais rapido.  
Podemos seguir por ciclos tecnicos, sem esperar "sprints longas".

1. Ciclo A (hoje): fundacao visual e tokens
2. Ciclo B (hoje): Supervisor + Sessões com grammar final
3. Ciclo C (amanha): Picking + Falhas + polimento de acessibilidade

## Opiniao profissional final

Voce esta perto de um visual realmente enterprise.  
O que falta nao e "mais cor", e sim **governança visual**: regras fixas de densidade, componentes de layout e padrao de graficos por contexto.

Com essa base, cada nova tela nasce consistente, e nao vira retrabalho de ajuste manual.

# Impacto Visual para Operadores e Supervisores

## Resumo Executivo
O sistema é funcional, mas ainda transmite sinais visuais inconsistentes em momentos críticos.  
As melhorias propostas mudam a percepção de "sistema que pode ter travado" para "sistema guiado, confiável e responsivo".

## Impactos de alto valor visual
1. `alert/prompt/confirm` -> Toast/Dialog padrão de produto.
2. Loading textual -> Skeleton contextual em telas críticas.
3. Unificação visual de `ShortageReport` e `BatchDetail`.
4. Erro de impressão com feedback claro + ação de retry.
5. Supervisão mobile com navegação consistente com desktop.

## Percepção esperada no operador
- Menos interrupção mental no picking.
- Menos ansiedade durante carregamento.
- Mais confiança em dados de shortage.
- Menos dúvidas sobre sucesso/falha da impressão.

## Matriz Antes/Depois
| Cenário | Antes | Depois | Resultado |
|---|---|---|---|
| SKU inválido | popup bloqueante | toast não bloqueante | fluxo contínuo |
| Dashboard supervisor | tela vazia/texto | skeleton imediato | confiança de carregamento |
| Falha de impressão | feedback irregular | erro visual padronizado + retry | menos retrabalho |
| Shortage report | estética isolada | padrão único de produto | decisão mais rápida |


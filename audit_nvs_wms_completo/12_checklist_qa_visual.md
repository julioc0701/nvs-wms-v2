# Checklist QA Visual (Teste Rápido)

## Pré-condição
1. Rodar `setup_isolado.bat` (uma vez).
2. Rodar `start_isolado.bat`.
3. Validar saúde com:
   - `node scripts/healthcheck_isolado.js`

## Login e Navegação
- [ ] Login abre sem erro visual.
- [ ] Layout desktop e mobile mantém identidade visual consistente.
- [ ] Botões de navegação não mostram popup nativo.

## SessionSelect
- [ ] Loading usa skeleton (não apenas texto).
- [ ] Feedback de busca/erro aparece em toast/card e não bloqueia tela.
- [ ] Campo de busca mantém foco após ação.

## Picking
- [ ] Erros operacionais aparecem por toast/dialog do produto.
- [ ] Falha de vínculo/transferência não abre `alert()` nativo.
- [ ] Estado visual de impressão permanece claro.

## ShortageReport
- [ ] Visual alinhado ao resto do sistema (header/card/tipografia).
- [ ] Loading com skeleton.
- [ ] Edição de observação abre dialog de produto (não prompt nativo).

## Supervisor + BatchDetail
- [ ] Ações de transferência/exclusão usam dialog próprio.
- [ ] Edição de observações usa dialog próprio.
- [ ] BatchDetail visualmente consistente com o app.

## Resiliência
- [ ] Forçar erro de UI e confirmar fallback do ErrorBoundary.

## Critério de aprovação
- [ ] Nenhum `alert/prompt/confirm` nativo em fluxo crítico.
- [ ] Nenhuma tela crítica com visual “fora do padrão”.
- [ ] Operador conclui fluxo sem dúvida de feedback.


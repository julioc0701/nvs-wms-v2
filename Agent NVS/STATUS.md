# NVS Agent — Status 2026-04-17

## Pronto e testado

| Componente | Status |
|---|---|
| SPEC + README + INSTALL | OK |
| 5 Skills Claude Code | OK |
| config/prompts (6 arquivos) | OK |
| Scorecard 4 Eixos | OK — 6/6 testes |
| Trilha A — Descrição | OK — 4/4 testes |
| Trilha B — Fotos (pyiqa + PIL) | OK — 5/5 testes |
| Trilha C — Objeções | OK |
| Trilha D — Concorrentes | OK (stub) |
| LLM — Título otimizado | OK — testado ao vivo |
| LLM — Descrição otimizada | OK — testado ao vivo |
| LLM — 8 prompts de imagem | OK — testado ao vivo |
| LLM — 5 prompts de vídeo | OK — testado ao vivo |
| Teste e2e retrovisor CG | OK — output completo 7 blocos NØR |

## Dependências (.venv Python 3.13)
- requests, Pillow, anthropic, openpyxl ✅
- pyiqa 0.1.15, rembg[cpu] 2.0.75 ✅
- torch + torchvision (CPU) ✅
- bertopic ❌ (pendente — Trilha C avançada)

## Chaves (.env)
- `ANTHROPIC_API_KEY` ✅ ativa
- `ML_ACCESS_TOKEN` ❌ pendente

## Próxima sessão — o que fazer

1. Obter `ML_ACCESS_TOKEN` (ver INSTALL.md → seção ML API)
2. Rodar: `python src/main.py MLB3661846735`
3. Comparar output real vs. mock do retrovisor
4. Instalar bertopic para clustering avançado na Trilha C
5. Implementar export .xlsx compatível com planilha NVS Diagnóstico

## Comando de retomada
```bash
cd "C:\Users\julio\OneDrive\Documentos\Antigra\Claude Code\Agent NVS"
.venv\Scripts\activate
set ANTHROPIC_API_KEY=<ver .env>
set ML_ACCESS_TOKEN=APP_USR-...
python src/main.py --check
python src/main.py MLB3661846735
```

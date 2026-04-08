# Rollback Seguro (Ambiente Isolado)

## Objetivo
Remover o ambiente isolado sem impacto no Antigravity.

## Passos
1. Parar processos locais nas portas isoladas.
2. Remover apenas `nvs-wms-code-isolated`.
3. Validar que Antigravity permanece intacto.

## Comandos (Windows)
```bat
REM Encerrar portas isoladas (se estiverem em uso)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5174') do taskkill /F /PID %%a
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do taskkill /F /PID %%a

REM Remover somente o projeto isolado
rmdir /S /Q nvs-wms-code-isolated
```

## Garantia
- Antigravity não é alterado por este rollback.
- Bancos `.db` de produção não são tocados.


# Runbook: Teste Agora (3 passos)

1. Setup (somente primeira vez):
```bat
setup_isolado.bat
```

2. Subir ambiente isolado:
```bat
start_isolado.bat
```

3. Verificar saúde:
```bat
node scripts/healthcheck_isolado.js
```

Se quiser encerrar:
```bat
stop_isolado.bat
```

Depois, validar visual com:
- `audit_nvs_wms_completo/12_checklist_qa_visual.md`


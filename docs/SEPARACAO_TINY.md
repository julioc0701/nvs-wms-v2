# Documentação Técnica: Integração e Separação Tiny ERP

> **Data:** 15 de Abril de 2026  
> **Status:** Implementado (Aguardando liberação de banco)  
> **Objetivo:** Unificar a experiência de picking entre o WMS (Full/Orgânico) e as Listas de Separação do Tiny ERP.

---

## 1. Visão Geral
A integração com o Tiny ERP permite que pedidos sejam agrupados em uma **Lista de Separação Consolidada**. Antigamente, essa lista trabalhava com uma lógica simplista de estado local. Agora, ela utiliza o **Padrão WMS**, onde o backend gerencia atomicamente as quantidades coletadas, garantindo precisão absoluta e suporte a múltiplos operadores.

## 2. Arquitetura de Picking (WMS Pattern)

### 🧠 Backend (O Cérebro)
Localizado em `backend/routers/tiny.py`.
- **Estratégia**: O frontend não calcula quantidades. Ele envia uma "intenção" (bipe ou clique) e o backend processa o incremento no banco de dados.
- **Endpoint Central**: `POST /api/tiny/picking-items/{item_id}/pick`
- **Modos de Operação**:
  - `unit` (Padrão): Incrementa `qty_picked` em 1. Usado para bipes individuais.
  - `box`: Coleta total. Define `qty_picked` como o valor total da `quantity`.
  - `set`: Ajuste manual. Define `qty_picked` extratamente como o valor enviado.
- **Retorno**: A API sempre devolve o objeto `item` completo e atualizado para que o frontend se sincronize imediatamente.

### ⚛️ Frontend (A Reatividade)
Localizado em `frontend/src/pages/PickingListDetail.jsx`.
- **Sincronia Global**: Função `updateItemInState`. Ela atualiza simultaneamente:
  - O estado do React (`items`) para o grid principal.
  - As referências mutáveis (`itemsRef`, `pickedIdsRef`) para o motor de scan.
  - O objeto de foco no modal (`selectedItem`).
- **Blindagem do Scanner**:
  - **Fallback de SKU**: Se o código bipado não for um barcode cadastrado, ele é tratado automaticamente como SKU.
  - **Sanitização**: Uso de `.trim().toUpperCase()` em todas as comparações para evitar erros por espaços invisíveis ou letras minúsculas.
  - **Prioridade de Foco**: Se um modal estiver aberto, o scanner tenta validar o código primeiro contra o item em foco, evitando bipes acidentais em outros itens da lista.

## 3. Fluxos de Trabalho

### ✅ Coleta Normal (Bipe)
1. Operador bipa SKU ou Barcode.
2. Sistema localiza o item na lista que não esteja 100% concluído.
3. Envia `mode: unit` para o servidor.
4. Servidor soma +1 e retorna o novo total.
5. UI atualiza a barra de progresso (ex: 2/5 -> 3/5).

### ❗ Registro de Falta (Shortage)
1. Operador clica em "Sem Estoque".
2. Modal sugere a falta baseada no saldo (Total - Já coletado).
3. Operador pode opcionalmente adicionar uma nota/observação.
4. Backend salva em `tiny_picking_list_items` e gera um espelho na tabela `shortages` para o relatório geral.

### 🔄 Reset de Item (Pendente)
1. Através do menu de status na lista, o operador pode marcar um item como "Pendente".
2. Isso dispara um `pick` com `qty: 0`, zerando o progresso no banco de dados.

## 4. Estrutura de Dados
Tabela principal: `tiny_picking_list_items`
- `qty_picked`: Quantidade física já bipada (Float).
- `quantity`: Quantidade total necessária (Float).
- `is_shortage`: Flag booleana para itens com falta.
- `notes`: Campo de texto para observações do operador.
- `location`: Localização física no armazém (importada do Tiny).

---

## ⚠️ Bloqueio Atual e Solução
**Problema:** O banco de dados físico (`database.db`) foi criado em versões anteriores e não possui as colunas de picking na tabela do Tiny. Isso causa o erro **"ERRO DE COMUNICAÇÃO"** (Erro 500 no Backend).

**Ações já tomadas:**
- Criado o script `backend/migrate_db.py`.
- Refatorada a lógica de scan para ser tolerante a espaços.

**Ação Necessária (Operador/Dev):**
É obrigatório rodar a migração manual no servidor/máquina local, pois o ambiente atual restringe a execução via PowerShell:
```bash
cd backend
python migrate_db.py
```
Apos rodar este comando, a tabela será atualizada e o sistema voltará a gravar as contagens corretamente.

---
*Documento gerado por Antigra (Google AI) - 2026*

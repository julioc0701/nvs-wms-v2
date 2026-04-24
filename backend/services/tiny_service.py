import httpx
import logging
import os
from typing import List, Dict, Any, Optional

log = logging.getLogger(__name__)

class TinyService:
    BASE_URL = "https://api.tiny.com.br/api2/"
    
    def __init__(self, token: str):
        self.token = token
        
    async def _post(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        if data is None:
            data = {}
        
        data["token"] = self.token
        data["formato"] = "json"
        
        url = f"{self.BASE_URL}{endpoint}"
        print(f"--- TINY REQ: {url} ---")
        print(f"--- DATA: {data} ---")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data, timeout=30.0)
                print(f"--- RESPONSE STATUS: {response.status_code} ---")
                raw_text = response.text
                print(f"--- RAW RESPONSE: {raw_text[:500]} ---")
                
                try:
                    data_json = response.json()
                except Exception:
                    log.error(f"Falha ao processar JSON. Resposta bruta: {raw_text[:200]}")
                    raise Exception(f"Tiny retornou resposta inválida (não decodificável como JSON). Resposta bruta: {raw_text[:100]}")
                
                retorno = data_json.get("retorno", {})
                if retorno.get("status") == "Erro":
                    erros = retorno.get("erros", [])
                    msg = erros[0].get("erro", "Erro desconhecido") if erros else "Erro na API do Tiny"
                    codigo = retorno.get("codigo_erro")
                    print(f"--- TINY ERROR: {msg} (Code: {codigo}) ---")
                    raise Exception(msg)
                
                return retorno
            except Exception as e:
                log.error(f"Erro na chamada Tiny ({endpoint}): {e}")
                raise

    async def search_orders(self, pagina: int = 1, status: Optional[str] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None) -> Dict[str, Any]:
        """Busca pedidos de venda percorrendo as páginas se necessário."""
        from datetime import datetime, timedelta
        
        params = {}
        if status:
            params["situacao"] = status
            
        if not data_inicial:
            data_inicial = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")
            
        params["dataInicial"] = data_inicial
        if data_final:
            params["dataFinal"] = data_final
            
        # Busca a primeira página
        params["pagina"] = pagina
        primeira_resposta = await self._post("pedidos.pesquisa.php", params)
        
        # O Tiny pode retornar código 20 (Não foram encontrados registros) se estiver vazio
        if primeira_resposta.get("codigo_erro") == "20" or "pedidos" not in primeira_resposta:
             return {"pedidos": []}
        
        pedidos_coletados = primeira_resposta.get("pedidos", [])
        numero_paginas = int(primeira_resposta.get("numero_paginas", 1))
        
        # Se pedimos uma página específica, não iteramos
        # Se pedimos a partir da 1, e tem mais de 1, vamos buscar as outras
        if pagina == 1 and numero_paginas > 1:
            import asyncio
            # Mantemos um teto configurável para evitar explosão de tempo, mas sem truncar cedo demais.
            limite_paginas = min(numero_paginas, int(os.getenv("TINY_SEARCH_MAX_PAGES", "100")))
            
            for p in range(2, limite_paginas + 1):
                # Pausa obrigatória para não sobrecarregar o banco de dados do Tiny e gerar "Erro 35"
                await asyncio.sleep(0.4)
                
                params["pagina"] = p
                resp = await self._post("pedidos.pesquisa.php", params)
                
                if "pedidos" in resp:
                    novos_pedidos = resp.get("pedidos", [])
                    if novos_pedidos:
                        pedidos_coletados.extend(novos_pedidos)
        
        # Sobrescreve a lista pela soma completa
        primeira_resposta["pedidos"] = pedidos_coletados
        
        return primeira_resposta

    async def search_separations(self, pagina: int = 1, data_inicial: Optional[str] = None, data_final: Optional[str] = None) -> Dict[str, Any]:
        """Busca separações com situacao=1 (aguardando separação) no período informado.
        Pagina automaticamente para garantir que TODOS os documentos sejam retornados.
        Situações 4 e 2 são gerenciadas internamente pelo NVS — não precisamos buscá-las no Tiny."""
        import asyncio
        from datetime import datetime, timedelta

        separacoes_dict = {}  # dicionário para evitar duplicatas por ID
        situacoes_alvo = ["1"]  # apenas aguardando separação

        if not data_inicial:
            data_inicial = (datetime.now() - timedelta(days=6)).strftime("%d/%m/%Y")
        if not data_final:
            data_final = datetime.now().strftime("%d/%m/%Y")

        for sit in situacoes_alvo:
            pg = 1
            while True:
                try:
                    resp = await self._post("separacao.pesquisa.php", {
                        "pagina": pg,
                        "situacao": sit,
                        "dataInicial": data_inicial,
                        "dataFinal": data_final
                    })
                    items = resp.get("separacoes", [])
                    for item in items:
                        data = item.get("separacao", item)
                        sep_id = data.get("id")
                        if sep_id:
                            separacoes_dict[sep_id] = data

                    numero_paginas = int(resp.get("numero_paginas", 1))
                    log.debug(f"SEPARACOES sit={sit} pg={pg}/{numero_paginas} docs={len(items)}")
                    if pg >= numero_paginas:
                        break
                    pg += 1
                    await asyncio.sleep(0.3)  # respeita rate limit do Tiny
                except Exception as e:
                    log.warning(f"SEPARACOES sit={sit} pg={pg} erro: {e}")
                    break

        return {
            "status": "OK",
            "separacoes": list(separacoes_dict.values())
        }

    async def get_order_details(self, pedido_id: str) -> Dict[str, Any]:
        """Obtém detalhes completos de um pedido (incluindo itens)."""
        params = {"id": pedido_id}
        return await self._post("pedido.obter.php", params)

    async def get_order_items(self, pedido_id: str) -> List[Dict[str, Any]]:
        """Extrai apenas os itens de um pedido formatados para o nosso sistema."""
        data = await self.get_order_details(pedido_id)
        pedido = data.get("pedido", {})
        itens_raw = pedido.get("itens", [])
        
        # Formata para o padrão PickingItem
        items = []
        for item in itens_raw:
            item_data = item.get("item", {})
            items.append({
                "sku": item_data.get("codigo"),
                "description": item_data.get("descricao"),
                "qty": float(item_data.get("quantidade", 0)),
                "price": float(item_data.get("valor_unitario", 0))
            })
        return items

    async def get_faturados_numeros(self, data_inicial: str, data_final: str) -> Dict[str, str]:
        """Busca números de pedidos faturados no período via pesquisa em lote.
        Retorna mapa {id_pedido: numero}. Geralmente 1 página (~17 registros/dia)."""
        info = await self.get_faturados_info(data_inicial, data_final)
        return {pid: v["numero"] for pid, v in info.items()}

    async def get_faturados_info(self, data_inicial: str, data_final: str) -> Dict[str, dict]:
        """Busca pedidos faturados no período.
        Retorna mapa {id_pedido: {numero, data_prevista, data_pedido}}."""
        import asyncio
        result: Dict[str, dict] = {}
        pagina = 1
        while True:
            try:
                resp = await self._post("pedidos.pesquisa.php", {
                    "dataInicial": data_inicial,
                    "dataFinal": data_final,
                    "situacao": "Faturado",
                    "pagina": pagina
                })
                pedidos = resp.get("pedidos", [])
                for p in pedidos:
                    ped = p.get("pedido", {})
                    pid = str(ped.get("id", ""))
                    if pid:
                        result[pid] = {
                            "numero": ped.get("numero", ""),
                            "data_prevista": ped.get("data_prevista", ""),
                            "data_pedido": ped.get("data_pedido", ""),
                        }
                numero_paginas = int(resp.get("numero_paginas", 1))
                if pagina >= numero_paginas:
                    break
                pagina += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                log.warning(f"get_faturados_info pagina={pagina}: {e}")
                break
        return result

    async def get_separation_details(self, separation_id: str) -> Dict[str, Any]:
        """Obtém detalhes completos de uma separação."""
        params = {"idSeparacao": separation_id}
        return await self._post("separacao.obter.php", params)

    async def update_separation_status(self, separation_id: str, situacao: str) -> Dict[str, Any]:
        """Atualiza a situação de uma separação na API do Tiny ERP v2.

        ⚠️  VERIFICAR antes de ativar em PRD (ENABLE_OLIST_SYNC=true):
            - Endpoint correto: separacao.alterar.situacao.php  (confirmar na doc Tiny)
            - Parâmetro 'id': ID numérico da separação no Tiny
            - Parâmetro 'situacao': valor esperado pelo Tiny (ex: 'separado', '3', etc.)

        Ativado apenas quando ENABLE_OLIST_SYNC=true no ambiente.
        """
        params = {
            "id": separation_id,
            "situacao": situacao,
        }
        return await self._post("separacao.alterar.situacao.php", params)

    async def get_multi_separation_items(self, separation_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Consolida itens de múltiplas separações com alta performance.
        Agrupa por SKU, soma quantidades e ordena por Qtd DESC.
        Utiliza processamento paralelo em blocos para respeitar o rate limit do Tiny.
        """
        import asyncio
        sku_map = {} # {sku: {desc, qty, loc, ids}}
        
        # Batch size aumentado de 5 para 12 para performance em escala
        BATCH_SIZE = 12
        
        for i in range(0, len(separation_ids), BATCH_SIZE):
            batch = separation_ids[i:i + BATCH_SIZE]
            tasks = [self.get_separation_details(sid) for sid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in results:
                if isinstance(res, Exception): 
                    print(f"!!! ERRO AO BUSCAR SEPARAÇÃO: {res} !!!")
                    continue
                
                sep = res.get("separacao", {})
                itens_raw = sep.get("itens", [])
                
                for it in itens_raw:
                    sku = it.get("codigo")
                    if not sku: continue
                    
                    qty = float(it.get("quantidade", 0))
                    desc = it.get("descricao")
                    loc = it.get("localizacao", "")
                    
                    if sku not in sku_map:
                        sku_map[sku] = {
                            "sku": sku,
                            "description": desc,
                            "quantity": 0,
                            "location": loc,
                            "source_ids": []
                        }
                    
                    sku_map[sku]["quantity"] += qty
                    sep_id = str(sep.get("id"))
                    if sep_id not in sku_map[sku]["source_ids"]:
                        sku_map[sku]["source_ids"].append(sep_id)
            
            # Pequena pausa apenas se houver mais blocos, para evitar o Erro 35 do Tiny
            # 0.2s é suficiente com lotes maiores
            if i + BATCH_SIZE < len(separation_ids):
                await asyncio.sleep(0.2)
                
        # Converte para lista e ordena por quantidade DESC
        consolidated = list(sku_map.values())
        consolidated.sort(key=lambda x: x["quantity"], reverse=True)
        
        return consolidated

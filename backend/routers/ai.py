import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from database import SessionLocal
from models import (AgentMemory, AgentRun, OrderOperational, TinyOrderSync,
                    Barcode, TinyPickingList, TinyPickingListItem, TinySeparationStatus, Shortage)
from services.tiny_service import TinyService
from mas_core.agent_protocol import (
    ALLOWED_SALES_STATUS,
    BUSINESS_TIMEZONE_OFFSET_HOURS,
    build_runtime_system_prompt,
    classify_user_intent,
    compute_confidence,
    infer_metric_focus,
    is_operational_sale_status,
    parse_requested_days,
    safe_json_dumps,
    should_show_dashboard,
    validate_tool_result,
)
from mas_core.agents import AGENT_PROMPTS, AgentRole, get_agent_prompt, get_agent_skills
from mas_core.ai_service import AIClient

router = APIRouter()
log = logging.getLogger(__name__)

AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
TINY_API_TOKEN = os.getenv("TINY_API_TOKEN", "")
OLIST_STATUS_BUCKET = ["faturado", "pronto para envio", "enviado", "entregue"]


class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    session_id: Optional[str] = None


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "show_orders_grid_ui",
            "description": "Renderiza a grade operacional de pedidos. Use apenas quando o usuário pedir explicitamente para ver lista, grade ou tabela.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Justificativa da abertura"}
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_data",
            "description": "Consulta estoque, giro e risco de ruptura para responder perguntas operacionais de inventário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_buscado": {"type": "string", "description": "SKU ou nome da peça"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_marketplace_performance",
            "description": "Analisa performance por marketplace com foco em conversão e vendas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "marketplace": {"type": "string", "description": "Mercado Livre, Olist ou Shopee"}
                },
                "required": ["marketplace"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_creative_brief",
            "description": "Gera briefing criativo estruturado para marketing, roteiro e arte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "peca": {"type": "string", "description": "Nome da peça a ser divulgada"},
                    "angulo_visual": {"type": "string", "description": "Descrição do ângulo da foto ideal"}
                },
                "required": ["peca"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_dashboard_data",
            "description": "Ferramenta obrigatória para responder perguntas sobre vendas, pedidos e resumo operacional. Respeita a política oficial de status válidos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "string", "description": "Quantidade de dias para análise. Ex.: '1', '7', '30'."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_olist_status_summary",
            "description": "Conta pedidos no bucket operacional da Olist/Tiny somando exatamente os status faturado, pronto para envio, enviado e entregue.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_dashboard_ui",
            "description": "Ativa a UI de dashboard com gráficos. Use apenas quando o usuário pedir visualização explícita.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Motivo da exibição"}
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_shortage_report",
            "description": "Retorna relatório de faltas de estoque — SKUs que tiveram ruptura ou falta durante a separação. Use para perguntas sobre faltas, rupturas, falta de produto, o que faltou.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_picking_list_summary",
            "description": "Retorna resumo das listas de separação ativas: status, progresso de coleta e faltas por lista. Use para perguntas sobre listas de separação, picking, o que está sendo separado.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_separation_pipeline",
            "description": "Retorna o pipeline de separações do Tiny: quantas estão em separação, concluídas e distribuição por status. Use para perguntas sobre separações, pipeline do armazém.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


TOOL_NAME_TO_ROLE = {
    "show_orders_grid_ui": AgentRole.ORCHESTRATOR,
    "get_inventory_data": AgentRole.DATA_SCIENTIST,
    "analyze_marketplace_performance": AgentRole.GROWTH_STRATEGIST,
    "generate_creative_brief": AgentRole.ART_DIRECTOR,
    "get_sales_dashboard_data": AgentRole.DATA_SCIENTIST,
    "get_olist_status_summary": AgentRole.DATA_SCIENTIST,
    "show_dashboard_ui": AgentRole.BI_ANALYST,
    "get_shortage_report": AgentRole.DATA_SCIENTIST,
    "get_picking_list_summary": AgentRole.DATA_SCIENTIST,
    "get_separation_pipeline": AgentRole.DATA_SCIENTIST,
}


def _tool_lookup() -> Dict[str, Dict[str, Any]]:
    return {tool["function"]["name"]: tool for tool in TOOLS_SCHEMA}


def _allowed_tools_for_role(role: AgentRole) -> List[Dict[str, Any]]:
    names = set(get_agent_skills(role))
    lookup = _tool_lookup()
    return [lookup[name] for name in names if name in lookup]


def _save_memory(session_id: str, role: str, message_type: str, content: str, tool_call_id: str | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(
            AgentMemory(
                session_id=session_id,
                agent_role=role,
                message_type=message_type,
                content=content,
                tool_call_id=tool_call_id,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        log.exception("Failed to persist agent memory: %s", exc)
    finally:
        db.close()


def _create_agent_run(request_id: str, session_id: str, user_prompt: str, specialist_role: str) -> int:
    db = SessionLocal()
    try:
        run = AgentRun(
            request_id=request_id,
            session_id=session_id,
            user_prompt=user_prompt,
            orchestrator_role=AgentRole.ORCHESTRATOR.value,
            specialist_role=specialist_role,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id
    finally:
        db.close()


def _update_agent_run(run_id: int, **fields: Any) -> None:
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            return
        for key, value in fields.items():
            setattr(run, key, value)
        if "status" in fields and fields["status"] in {"success", "error"} and not fields.get("completed_at"):
            run.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()
        log.exception("Failed to update agent run: %s", exc)
    finally:
        db.close()


def _extract_user_prompt(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "").strip()
    return ""


def _specialist_announcement(role: AgentRole) -> str:
    if role == AgentRole.DATA_SCIENTIST:
        return "Fala boi, consultei o Cientista de Dados aqui nos bastidores e já puxei a leitura operacional certa."
    if role == AgentRole.BI_ANALYST:
        return "Seguinte, alinhei com o Analista de BI aqui por dentro pra te entregar a visão mais redonda."
    if role == AgentRole.ART_DIRECTOR:
        return "Bora nessa: falei com o Diretor de Arte aqui na retaguarda e trouxe o briefing no jeito."
    if role == AgentRole.GROWTH_STRATEGIST:
        return "É nóis, consultei o Especialista de Vendas e puxei a leitura de performance sem chute."
    return "Fala boi, aqui é o NVS coordenando a jogada."



def _build_local_olist_status_summary() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        counts = {status: 0 for status in OLIST_STATUS_BUCKET}
        last_sync: Optional[datetime] = None
        canonical_rows = db.query(OrderOperational).all()
        if canonical_rows:
            for row in canonical_rows:
                if not last_sync or (row.last_synced_at and row.last_synced_at > last_sync):
                    last_sync = row.last_synced_at
                status = str(row.current_status or "").strip().lower()
                if status in counts:
                    counts[status] += 1
            source_name = "canonical_local"
        else:
            for order in db.query(TinyOrderSync).all():
                if not last_sync or (order.last_synced_at and order.last_synced_at > last_sync):
                    last_sync = order.last_synced_at
                try:
                    raw_json = json.loads(order.raw_data) if order.raw_data else {}
                except json.JSONDecodeError:
                    continue
                status = str(raw_json.get("situacao", "")).strip().lower()
                if status in counts:
                    counts[status] += 1
            source_name = "local_mirror"
        return {
            "status": "success",
            "source": source_name,
            "status_counts": counts,
            "total_status_bucket": sum(counts.values()),
            "data_quality": {
                "last_sync_at": last_sync.isoformat() if last_sync else None,
                "freshness": "fresh" if last_sync and datetime.utcnow() - last_sync <= timedelta(hours=12) else "stale",
                "warnings": ["contagem baseada no espelho local, não em leitura direta da API Tiny/Olist"],
            },
        }
    finally:
        db.close()


async def _build_olist_status_summary() -> Dict[str, Any]:
    if not TINY_API_TOKEN:
        return _build_local_olist_status_summary()

    from datetime import datetime, timedelta

    service = TinyService(TINY_API_TOKEN)
    lookback_days = int(os.getenv("OLIST_STATUS_LOOKBACK_DAYS", "30"))
    data_inicial = (datetime.now() - timedelta(days=lookback_days)).strftime("%d/%m/%Y")
    counts: Dict[str, int] = {}
    warnings: List[str] = []

    for status in OLIST_STATUS_BUCKET:
        response = await service.search_orders(status=status, data_inicial=data_inicial)
        pedidos = response.get("pedidos", []) if isinstance(response, dict) else []
        numero_paginas = int(response.get("numero_paginas", 1) or 1)
        max_pages = int(os.getenv("TINY_SEARCH_MAX_PAGES", "100"))
        if numero_paginas >= max_pages:
            warnings.append(f"status '{status}' encostou no limite de paginação configurado ({max_pages})")
        counts[status] = len(pedidos)

    result = {
        "status": "success",
        "source": "tiny_api",
        "status_counts": counts,
        "total_status_bucket": sum(counts.values()),
        "data_quality": {
            "last_sync_at": datetime.utcnow().isoformat(),
            "freshness": "fresh",
            "warnings": sorted(set(warnings + [f"janela consultada: últimos {lookback_days} dias"])),
        },
    }
    return validate_tool_result("get_olist_status_summary", result)


def _build_sales_dashboard_data(days_value: Any) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        days = parse_requested_days(days_value)
        status_breakdown: Dict[str, int] = {}
        platforms: Dict[str, int] = {}
        top_skus: Dict[str, float] = {}
        total_operational_orders = 0
        total_operational_revenue = 0.0
        last_sync: Optional[datetime] = None
        warnings: List[str] = []
        window_start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")

        canonical_orders = db.query(OrderOperational).filter(OrderOperational.order_date >= window_start).all()
        if canonical_orders:
            for order in canonical_orders:
                if not last_sync or (order.last_synced_at and order.last_synced_at > last_sync):
                    last_sync = order.last_synced_at

                situation = str(order.current_status or "em_aberto").lower()
                status_breakdown[situation] = status_breakdown.get(situation, 0) + 1

                if order.is_operational_sale:
                    total_operational_orders += 1
                    marketplace = order.channel or "Outros"
                    platforms[marketplace] = platforms.get(marketplace, 0) + 1
                    total_operational_revenue += float(order.total_value or 0)

            all_orders_total = db.query(OrderOperational).count()
            window_total = len(canonical_orders)
            warnings.append("consulta baseada na camada canônica operacional")
        else:
            min_date = datetime.utcnow() - timedelta(days=days, hours=abs(BUSINESS_TIMEZONE_OFFSET_HOURS))
            orders = db.query(TinyOrderSync).filter(TinyOrderSync.last_synced_at >= min_date).all()
            all_orders = db.query(TinyOrderSync).all()

            for order in orders:
                if not last_sync or (order.last_synced_at and order.last_synced_at > last_sync):
                    last_sync = order.last_synced_at

                raw_json = {}
                if order.raw_data:
                    try:
                        raw_json = json.loads(order.raw_data)
                    except json.JSONDecodeError:
                        warnings.append(f"pedido {order.id} com raw_data inválido")

                situation = str(raw_json.get("situacao", "em_aberto")).lower()
                status_breakdown[situation] = status_breakdown.get(situation, 0) + 1

                if is_operational_sale_status(situation):
                    total_operational_orders += 1
                    marketplace = order.ecommerce or "Outros"
                    platforms[marketplace] = platforms.get(marketplace, 0) + 1
                    for item in order.items:
                        qty = float(item.quantidade or 0)
                        unit_value = float(item.valor_unitario or 0)
                        total_operational_revenue += qty * unit_value
                        sku = item.codigo or item.id_produto or "SKU_DESCONHECIDO"
                        top_skus[sku] = top_skus.get(sku, 0.0) + qty

            all_orders_total = len(all_orders)
            window_total = len(orders)

        freshness = "unknown"
        if last_sync:
            freshness = "fresh" if datetime.utcnow() - last_sync <= timedelta(hours=12) else "stale"
            if freshness == "stale":
                warnings.append("última sincronização acima de 12h")
        else:
            warnings.append("nenhuma sincronização recente encontrada")

        if window_total == 0:
            warnings.append("sem pedidos na janela consultada")

        result = {
            "status": "success",
            "policy": {
                "allowed_sales_status": ALLOWED_SALES_STATUS,
                "days_requested": days,
                "timezone_offset_hours": BUSINESS_TIMEZONE_OFFSET_HOURS,
            },
            "total_pedidos_periodo": window_total,
            "total_vendas_reais_calc": total_operational_orders,
            "total_receita_real_calc": round(total_operational_revenue, 2),
            "explicação": "Número operacional baseado apenas em status válidos segundo a política oficial do sistema.",
            "diagnostico_completo": {
                "total_bruto_no_banco": all_orders_total,
                "total_pedidos_na_janela": window_total,
                "detalhe_por_status": status_breakdown,
                "vendas_por_plataforma": platforms,
                "top_skus_por_quantidade": dict(sorted(top_skus.items(), key=lambda item: item[1], reverse=True)[:5]),
            },
            "data_quality": {
                "last_sync_at": last_sync.isoformat() if last_sync else None,
                "freshness": freshness,
                "warnings": sorted(set(warnings)),
            },
        }
        return validate_tool_result("get_sales_dashboard_data", result)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Erro ao calcular dashboard de vendas: {exc!r}",
            "data_quality": {"warnings": ["falha interna na tool"]},
        }
    finally:
        db.close()


def _execute_tool(tool_name: str, arguments: Dict[str, Any], user_prompt: str) -> tuple[Dict[str, Any], Optional[str]]:
    inject_ui = None

    if tool_name == "show_orders_grid_ui":
        return {"status": "success", "reason": arguments.get("reason", "visualização solicitada")}, "olist_orders"

    if tool_name == "show_dashboard_ui":
        if not should_show_dashboard(user_prompt):
            return {
                "status": "error",
                "message": "dashboard bloqueado porque o usuário não pediu visualização explícita",
            }, None
        return validate_tool_result(
            tool_name,
            {"status": "success", "reason": arguments.get("reason", "dashboard solicitado pelo usuário")},
        ), "sales_dashboard"

    if tool_name == "get_inventory_data":
        sku = arguments.get("sku_buscado", "")
        db = SessionLocal()
        try:
            q = db.query(Barcode)
            if sku:
                q = q.filter(Barcode.sku.ilike(f"%{sku}%"))
            barcodes = q.limit(20).all()
            sku_list = list({b.sku for b in barcodes})
            item_data: Dict[str, Dict] = {}
            if sku_list:
                for item in db.query(TinyPickingListItem).filter(TinyPickingListItem.sku.in_(sku_list)).all():
                    if item.sku not in item_data:
                        item_data[item.sku] = {"qty": 0.0, "picked": 0.0, "shortage": 0.0}
                    item_data[item.sku]["qty"] += float(item.quantity or 0)
                    item_data[item.sku]["picked"] += float(item.qty_picked or 0)
                    item_data[item.sku]["shortage"] += float(item.qty_shortage or 0)
            detalhes = []
            seen_skus: set = set()
            for b in barcodes:
                if b.sku in seen_skus:
                    continue
                seen_skus.add(b.sku)
                d = item_data.get(b.sku, {})
                detalhes.append({
                    "sku": b.sku,
                    "description": b.description or "—",
                    "qty_em_listas": d.get("qty", 0),
                    "qty_coletado": d.get("picked", 0),
                    "qty_falta": d.get("shortage", 0),
                })
            result = {
                "status": "success",
                "sku_ref": sku or "todos",
                "skus_cadastrados": len(seen_skus),
                "detalhes": detalhes[:10],
                "nota": "Dados reais do banco local. Saldo físico atualizado via listas de separação.",
            }
        finally:
            db.close()
        return validate_tool_result(tool_name, result), None

    if tool_name == "analyze_marketplace_performance":
        marketplace = arguments.get("marketplace", "")
        db = SessionLocal()
        try:
            q = db.query(OrderOperational).filter(OrderOperational.is_operational_sale == True)
            if marketplace:
                q = q.filter(OrderOperational.channel.ilike(f"%{marketplace}%"))
            orders = q.all()
            total = len(orders)
            total_revenue = sum(float(o.total_value or 0) for o in orders)
            by_status: Dict[str, int] = {}
            by_channel: Dict[str, int] = {}
            for o in orders:
                s = o.current_status or "desconhecido"
                by_status[s] = by_status.get(s, 0) + 1
                ch = o.channel or "Outros"
                by_channel[ch] = by_channel.get(ch, 0) + 1
            result = {
                "status": "success",
                "plataforma": marketplace or "todas",
                "total_pedidos_operacionais": total,
                "receita_total": round(total_revenue, 2),
                "detalhe_por_status": by_status,
                "detalhe_por_canal": by_channel,
                "nota": "Dados reais da camada operacional local.",
            }
        finally:
            db.close()
        return validate_tool_result(tool_name, result), None

    if tool_name == "generate_creative_brief":
        part_name = arguments.get("peca", "Peça indefinida")
        result = {
            "status": "success",
            "peca_foco": part_name,
            "roteiro_tiktok": f"HOOK: 'Você acha que a sua {part_name} atual aguenta marretada?'.",
            "prompt_midjourney": f"Extreme close up of motorcycle part {part_name}, studio lighting, photorealistic --ar 16:9",
        }
        return validate_tool_result(tool_name, result), None

    if tool_name == "get_sales_dashboard_data":
        return _build_sales_dashboard_data(arguments.get("days")), None

    if tool_name == "get_shortage_report":
        db = SessionLocal()
        try:
            shortages = db.query(Shortage).order_by(Shortage.created_at.desc()).limit(50).all()
            result = {
                "status": "success",
                "total_faltas": len(shortages),
                "faltas": [
                    {
                        "sku": s.sku,
                        "description": s.description,
                        "quantity": s.quantity,
                        "category": s.category,
                        "notes": s.notes,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                    }
                    for s in shortages
                ],
            }
        finally:
            db.close()
        return result, None

    if tool_name == "get_picking_list_summary":
        db = SessionLocal()
        try:
            lists = db.query(TinyPickingList).order_by(TinyPickingList.created_at.desc()).limit(10).all()
            summary = []
            for pl in lists:
                total_items = len(pl.items)
                picked = sum(1 for i in pl.items if float(i.qty_picked or 0) >= float(i.quantity or 0))
                shortage = sum(1 for i in pl.items if i.is_shortage)
                summary.append({
                    "id": pl.id,
                    "name": pl.name,
                    "status": pl.status,
                    "total_items": total_items,
                    "itens_coletados": picked,
                    "itens_com_falta": shortage,
                    "created_at": pl.created_at.isoformat() if pl.created_at else None,
                })
            result = {"status": "success", "total_listas": len(summary), "listas": summary}
        finally:
            db.close()
        return result, None

    if tool_name == "get_separation_pipeline":
        db = SessionLocal()
        try:
            all_seps = db.query(TinySeparationStatus).all()
            por_status: Dict[str, int] = {}
            for s in all_seps:
                por_status[s.status] = por_status.get(s.status, 0) + 1
            result = {
                "status": "success",
                "total_separacoes": len(all_seps),
                "por_status": por_status,
            }
        finally:
            db.close()
        return result, None

    return {"status": "error", "message": f"Unknown function: {tool_name}"}, None


def _collect_warnings(tool_result: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    warnings.extend(tool_result.get("warnings") or [])
    warnings.extend(tool_result.get("data_quality", {}).get("warnings") or [])
    return sorted(set(warnings))


def _compose_sales_answer(user_prompt: str, tool_result: Dict[str, Any], confidence: str) -> str:
    focus = infer_metric_focus(user_prompt)
    days = int(tool_result.get("policy", {}).get("days_requested") or 1)
    periodo = "hoje" if days == 1 else f"nos últimos {days} dias"
    total_orders = int(tool_result.get("total_pedidos_periodo") or 0)
    total_sales = int(tool_result.get("total_vendas_reais_calc") or 0)
    total_revenue = float(tool_result.get("total_receita_real_calc") or 0.0)
    warnings = _collect_warnings(tool_result)

    if focus == "orders":
        final_content = (
            f"Fala boi, puxei os números {periodo} aqui. Tivemos {total_orders} pedidos {periodo}.\n\n"
            f"Desses, {total_sales} já estão em status operacionais válidos pela política do sistema."
        )
    elif focus == "revenue":
        final_content = (
            f"Fala boi, o faturamento operacional {periodo} está em R$ {total_revenue:.2f}.\n\n"
            f"Esse valor vem de {total_sales} pedidos em status válidos, dentro de {total_orders} pedidos no período."
        )
    else:
        final_content = (
            f"Fala boi, {periodo} estamos com {total_sales} vendas operacionais válidas.\n\n"
            f"No total, o sistema registrou {total_orders} pedidos no período consultado."
        )

    if warnings:
        final_content += f"\n\nPonto de atenção: {warnings[0]}."
    if confidence in {'low', 'medium'}:
        final_content += f"\n\nConfianca operacional: {confidence}."
    return final_content


def _compose_olist_status_answer(tool_result: Dict[str, Any], confidence: str) -> str:
    counts = tool_result.get("status_counts", {})
    total = int(tool_result.get("total_status_bucket") or 0)
    source = tool_result.get("source", "unknown")
    warnings = _collect_warnings(tool_result)

    final_content = (
        "Fala boi, aqui eu li a contagem do bucket operacional da Olist/Tiny somando exatamente os status que você definiu.\n\n"
        f"Faturado: {int(counts.get('faturado', 0))}\n"
        f"Pronto para envio: {int(counts.get('pronto para envio', 0))}\n"
        f"Enviado: {int(counts.get('enviado', 0))}\n"
        f"Entregue: {int(counts.get('entregue', 0))}\n\n"
        f"Total: {total}"
    )

    if source == "tiny_api":
        final_content += "\n\nFonte: leitura direta da API Tiny/Olist."
    else:
        final_content += "\n\nFonte: espelho local sincronizado."

    if warnings:
        final_content += f"\n\nPonto de atenção: {warnings[0]}."
    if confidence in {"low", "medium"}:
        final_content += f"\n\nConfianca operacional: {confidence}."
    return final_content


@router.get("/health")
async def ai_health():
    provider = "groq" if "groq" in AI_BASE_URL.lower() else "custom"
    return {
        "status": "online" if os.getenv("GROQ_API_KEY") else "degraded",
        "provider": provider,
        "configured_model": AI_MODEL,
        "base_url": AI_BASE_URL,
        "message": "AI router loaded. Provider auth/config needs validation at runtime.",
    }


@router.post("/chat")
async def chat_handler(req: ChatRequest):
    client = AIClient()
    session_id = req.session_id or "anonymous"
    request_id = str(uuid4())
    user_prompt = _extract_user_prompt(req.messages)

    routing = classify_user_intent(user_prompt)
    specialist_role = AgentRole(routing.specialist_role) if routing.specialist_role in AgentRole._value2member_map_ else AgentRole.ORCHESTRATOR

    specialist_prompt = get_agent_prompt(specialist_role)
    system_prompt = build_runtime_system_prompt(
        get_agent_prompt(AgentRole.ORCHESTRATOR),
        specialist_prompt,
        routing,
    )

    messages_payload = [m for m in req.messages if m.get("role") != "system"]
    messages_payload.insert(0, {"role": "system", "content": system_prompt})

    _save_memory(session_id, AgentRole.ORCHESTRATOR.value, "system", system_prompt)
    if user_prompt:
        _save_memory(session_id, AgentRole.ORCHESTRATOR.value, "user", user_prompt)

    run_id = _create_agent_run(request_id, session_id, user_prompt, specialist_role.value)

    tool_schema = _allowed_tools_for_role(specialist_role) or _allowed_tools_for_role(AgentRole.ORCHESTRATOR)

    model_response = await client.chat_completion(messages=messages_payload, tools=tool_schema)
    if model_response["status"] == "error":
        error_detail = model_response.get("message", {}).get("content", "Erro interno de conexão com a IA")
        _update_agent_run(run_id, status="error", error_message=error_detail, completed_at=datetime.utcnow())
        return {
            "message": {
                "role": "assistant",
                "content": f"⚠️ Falha de comunicação com a Groq. Detalhe técnico: {error_detail}",
            },
            "generative_ui": None,
            "agent_meta": {
                "request_id": request_id,
                "specialist": routing.specialist_label,
                "confidence": "low",
            },
        }

    msg = model_response["message"]
    inject_ui = None
    confidence = "unknown"
    chosen_tool = None
    final_content = msg.get("content") or ""

    if msg.get("tool_calls"):
        messages_with_tools = messages_payload.copy()
        messages_with_tools.append(msg)

        for tool_call in msg["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            chosen_tool = tool_name
            arguments = tool_call["function"]["arguments"]
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}

            allowed_names = {tool["function"]["name"] for tool in tool_schema}
            if tool_name not in allowed_names:
                tool_result = {
                    "status": "error",
                    "message": f"tool '{tool_name}' não permitida para o especialista roteado",
                }
                local_ui = None
            else:
                tool_result, local_ui = _execute_tool(tool_name, arguments, user_prompt)

            if local_ui:
                inject_ui = local_ui

            confidence = compute_confidence(
                has_data=tool_result.get("status") == "success",
                tool_status=tool_result.get("status", "error"),
                warnings=_collect_warnings(tool_result),
                last_sync_at=tool_result.get("data_quality", {}).get("last_sync_at"),
            )

            _save_memory(session_id, specialist_role.value, "tool", safe_json_dumps(tool_result), tool_call["id"])
            _update_agent_run(
                run_id,
                tool_name=tool_name,
                tool_args_json=safe_json_dumps(arguments),
                tool_result_json=safe_json_dumps(tool_result),
                confidence=confidence,
            )

            messages_with_tools.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_name,
                    "content": safe_json_dumps(tool_result),
                }
            )

        if chosen_tool == "get_sales_dashboard_data":
            final_content = _compose_sales_answer(user_prompt, tool_result, confidence)
            _save_memory(session_id, AgentRole.ORCHESTRATOR.value, "assistant", final_content)
            _update_agent_run(
                run_id,
                status="success",
                final_content=final_content,
                confidence=confidence,
                completed_at=datetime.utcnow(),
            )
            return {
                "message": {"role": "assistant", "content": final_content},
                "generative_ui": inject_ui,
                "agent_meta": {
                    "request_id": request_id,
                    "specialist": routing.specialist_label,
                    "tool_name": chosen_tool,
                    "confidence": confidence,
                },
            }

        final_response = await client.chat_completion(messages=messages_with_tools)
        if final_response["status"] == "error":
            final_content = (
                f"{_specialist_announcement(specialist_role)}\n\n"
                "A tool respondeu, mas a camada final de síntese da IA falhou. "
                "Considere reexecutar a consulta.\n\n"
                "Confianca operacional: low."
            )
            _save_memory(session_id, AgentRole.ORCHESTRATOR.value, "assistant", final_content)
            _update_agent_run(
                run_id,
                status="error",
                final_content=final_content,
                confidence="low",
                error_message=final_response.get("message", {}).get("content", "falha na síntese final"),
                completed_at=datetime.utcnow(),
            )
            return {
                "message": {"role": "assistant", "content": final_content},
                "generative_ui": inject_ui,
                "agent_meta": {
                    "request_id": request_id,
                    "specialist": routing.specialist_label,
                    "tool_name": chosen_tool,
                    "confidence": "low",
                },
            }
        final_content = final_response.get("message", {}).get("content") or ""

        if not final_content:
            final_content = "Recebi os dados da tool, mas a camada final de resposta veio vazia. Refaça a consulta."

        announcement = _specialist_announcement(specialist_role)
        if not final_content.startswith("Fala") and not final_content.startswith("Seguinte") and not final_content.startswith("É nóis") and not final_content.startswith("Bora"):
            final_content = f"{announcement}\n\n{final_content}"
        if confidence in {"low", "medium"}:
            final_content += f"\n\nConfianca operacional: {confidence}."

        _save_memory(session_id, AgentRole.ORCHESTRATOR.value, "assistant", final_content)
        _update_agent_run(
            run_id,
            status="success",
            final_content=final_content,
            confidence=confidence,
            completed_at=datetime.utcnow(),
        )
        return {
            "message": {"role": "assistant", "content": final_content},
            "generative_ui": inject_ui,
            "agent_meta": {
                "request_id": request_id,
                "specialist": routing.specialist_label,
                "tool_name": chosen_tool,
                "confidence": confidence,
            },
        }

    if specialist_role != AgentRole.ORCHESTRATOR:
        final_content = (
            f"{_specialist_announcement(specialist_role)}\n\n"
            f"{final_content or 'A IA não acionou tool para uma consulta técnica. Isso reduz a confiabilidade da resposta.'}\n\n"
            "Confianca operacional: low."
        )
        confidence = "low"
    else:
        confidence = "medium" if final_content else "low"

    _save_memory(session_id, AgentRole.ORCHESTRATOR.value, "assistant", final_content or "")
    _update_agent_run(
        run_id,
        status="success",
        final_content=final_content,
        confidence=confidence,
        completed_at=datetime.utcnow(),
    )
    return {
        "message": {"role": "assistant", "content": final_content or "Resposta vazia da IA."},
        "generative_ui": None,
        "agent_meta": {
            "request_id": request_id,
            "specialist": routing.specialist_label,
            "tool_name": None,
            "confidence": confidence,
        },
    }

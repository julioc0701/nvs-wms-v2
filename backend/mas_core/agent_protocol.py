import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


BUSINESS_TIMEZONE_OFFSET_HOURS = -3

ALLOWED_SALES_STATUS = [
    "aprovado",
    "preparando_envio",
    "preparando envio",
    "faturado",
    "pronto_para_envio",
    "pronto para envio",
    "enviado",
    "atendido",
    "entregue",
]

EXCLUDED_SALES_STATUS = [
    "em aberto",
    "em_aberto",
    "cancelado",
    "cancelada",
    "cancelado_parcialmente",
    "cancelado parcialmente",
]


@dataclass
class RoutingDecision:
    specialist_role: str
    specialist_label: str
    rationale: str


def parse_requested_days(value: Any, default: int = 1, min_days: int = 1, max_days: int = 30) -> int:
    try:
        days = int(str(value or default).strip())
    except (TypeError, ValueError):
        return default
    return max(min_days, min(max_days, days))


def normalize_status(raw_status: Optional[str]) -> str:
    if not raw_status:
        return "em_aberto"
    return str(raw_status).strip().lower()


def is_operational_sale_status(status: Optional[str]) -> bool:
    normalized = normalize_status(status)
    return normalized in ALLOWED_SALES_STATUS


def classify_user_intent(user_prompt: str) -> RoutingDecision:
    text = (user_prompt or "").lower()

    sales_markers = [
        "vendeu",
        "vendemos",
        "vendas",
        "faturamento",
        "receita",
        "pedido",
        "pedidos",
        "dashboard",
        "gráfico",
        "grafico",
        "kpi",
        "shopee",
        "mercado livre",
        "olist",
    ]
    inventory_markers = ["estoque", "sku", "giro", "ruptura", "reposição", "reposicao"]
    creative_markers = ["criativo", "copy", "briefing", "midjourney", "reels", "tiktok"]

    if any(marker in text for marker in sales_markers + inventory_markers):
        return RoutingDecision(
            specialist_role="cientista_dados",
            specialist_label="Cientista de Dados",
            rationale="pedido analítico/operacional com dependência explícita de dados",
        )

    if any(marker in text for marker in creative_markers):
        return RoutingDecision(
            specialist_role="diretor_arte",
            specialist_label="Diretor de Arte",
            rationale="pedido criativo com saída de briefing/prompt",
        )

    return RoutingDecision(
        specialist_role="orquestrador",
        specialist_label="NVS",
        rationale="pedido geral sem necessidade obrigatória de especialista técnico",
    )


def should_show_dashboard(user_prompt: str) -> bool:
    text = (user_prompt or "").lower()
    return any(token in text for token in ["dashboard", "gráfico", "grafico", "painel", "visão visual", "visao visual"])


def infer_metric_focus(user_prompt: str) -> str:
    text = (user_prompt or "").lower()
    revenue_markers = ["receita", "faturamento", "valor", "total vendido", "quanto vendemos", "quanto vendeu"]
    sales_markers = ["vendas", "vendemos", "vendeu", "faturado", "faturados"]
    order_markers = ["pedido", "pedidos", "quantos pedidos", "qtd pedidos", "número de pedidos", "numero de pedidos"]

    if any(marker in text for marker in revenue_markers):
        return "revenue"
    if any(marker in text for marker in order_markers) and not any(marker in text for marker in revenue_markers + sales_markers):
        return "orders"
    return "sales"


def build_runtime_system_prompt(orchestrator_prompt: str, specialist_prompt: str, routing: RoutingDecision) -> str:
    return (
        f"{orchestrator_prompt}\n\n"
        "RUNTIME GOVERNANCE:\n"
        f"- Especialista designado para esta tarefa: {routing.specialist_label}.\n"
        f"- Motivo do roteamento: {routing.rationale}.\n"
        "- A resposta final ao usuário sempre sai na voz do NVS.\n"
        "- O especialista atua nos bastidores e não assume a conversa com o usuário.\n"
        "- Nunca responda com números sem resultado de tool.\n"
        "- Se a tool retornar erro, vazio ou dado inconsistente, sinalize baixa confiança.\n"
        "- Se o usuário não pedir visualização, priorize resposta textual auditável.\n\n"
        f"SPECIALIST POLICY:\n{specialist_prompt}"
    )


def compute_confidence(
    *,
    has_data: bool,
    tool_status: str,
    warnings: Optional[list[str]] = None,
    last_sync_at: Optional[str] = None,
) -> str:
    warnings = [warning for warning in (warnings or []) if warning]
    if tool_status != "success":
        return "low"
    if not has_data:
        return "low"
    if warnings:
        return "medium"
    if last_sync_at:
        try:
            synced = datetime.fromisoformat(last_sync_at)
            if datetime.utcnow() - synced > timedelta(hours=12):
                return "medium"
        except ValueError:
            return "medium"
    return "high"


def validate_tool_result(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    warnings: list[str] = []
    status = result.get("status", "success")

    if tool_name == "get_sales_dashboard_data":
        if "total_vendas_reais_calc" not in result:
            status = "error"
            warnings.append("resultado sem total_vendas_reais_calc")
        if "diagnostico_completo" not in result:
            warnings.append("resultado sem diagnostico_completo")
        if result.get("data_quality", {}).get("freshness") == "stale":
            warnings.append("base aparentemente desatualizada")

    if tool_name == "show_dashboard_ui" and result.get("status") != "success":
        status = "error"
        warnings.append("falha ao ativar dashboard")

    if tool_name == "get_olist_status_summary":
        if "total_status_bucket" not in result:
            status = "error"
            warnings.append("resultado sem total_status_bucket")
        if "status_counts" not in result:
            status = "error"
            warnings.append("resultado sem status_counts")

    result["status"] = status
    if warnings:
        result["warnings"] = sorted(set(result.get("warnings", []) + warnings))
    return result


def safe_json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)

"""Cria massa de dados pra testar filtros e dashboard do Financeiro.

Roda direto via SQL (mais rápido que via API). Insere ~15 lançamentos
cobrindo:
  - Boletos da semana corrente (a pagar)
  - PIX para fornecedor/funcionário
  - Despesas (água, luz, internet, aluguel)
  - 3 atrasados (vencimento já passou, ainda como 'registrado')
  - 3 pagos (com pago_em em datas variadas)
  - 3 futuros (próximo mês)

Uso:
    python scripts/seed_financeiro.py [--limpar]

--limpar apaga TODOS os boletos/lancamentos antes (cuidado em prod).
"""
import argparse
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "backend" / "warehouse_v3_local.db"

HOJE = date.today()
SEMANA_FIM = HOJE + timedelta(days=(6 - HOJE.weekday()))  # domingo da semana
PROXIMA_SEMANA = SEMANA_FIM + timedelta(days=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limpar", action="store_true", help="Apaga tudo antes")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"DB não encontrado em {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Operador Master pra capturar/pagar
    master_id = cur.execute("SELECT id FROM operators WHERE name='Master'").fetchone()[0]

    # Mapa de categorias por nome
    cats = {r[1]: r[0] for r in cur.execute(
        "SELECT id, nome FROM lancamento_categorias"
    ).fetchall()}

    if args.limpar:
        cur.execute("DELETE FROM boletos")
        cur.execute("DELETE FROM boleto_beneficiarios")
        conn.commit()
        print("--- BD limpo antes da seed ---")

    # ── Lançamentos ──────────────────────────────────────────────────────────
    # (categoria, empresa, valor, vencimento, status, pago_em, descricao, chave_pix)
    HOJE_S = HOJE.isoformat()

    # Tupla: (categoria, empresa, valor, venc, status, pago_em, desc, chave_pix, nota_fiscal)
    lancamentos = [
        # ── ESTA SEMANA (a pagar) — 7 lançamentos ─────────────────────────────
        ("Luz", "Energisa Mato Grosso", 350.00,
         (HOJE + timedelta(days=2)).isoformat(), "registrado", None,
         "Conta de luz - maio", None, "NF-LUZ-0524"),
        ("Água", "Sabesp", 120.50,
         (HOJE + timedelta(days=3)).isoformat(), "registrado", None,
         "Conta de água - maio", None, "NF-AGU-0524"),
        ("Internet", "Vivo Fibra", 200.00,
         (HOJE + timedelta(days=5)).isoformat(), "registrado", None,
         "Internet 600MB", None, None),
        ("PIX Fornecedor", "João da Silva ME", 1500.00,
         (HOJE + timedelta(days=4)).isoformat(), "registrado", None,
         "Pagamento materiais elétricos", "12345678901", "NF-JSME-1872"),
        ("PIX Funcionário", "Maria Souza", 800.00,
         (HOJE + timedelta(days=6)).isoformat(), "registrado", None,
         "Adiantamento salário", "maria@email.com", None),
        ("Boleto", "Bradesco S.A.", 1245.80,
         (HOJE + timedelta(days=1)).isoformat(), "registrado", None,
         "Tarifa de cobrança", None, "NF-BRD-0099"),
        ("Outros", "Cartório Sé", 89.00,
         (HOJE + timedelta(days=6)).isoformat(), "registrado", None,
         "Reconhecimento de firma", None, None),

        # ── ATRASADOS — 5 lançamentos ─────────────────────────────────────────
        ("Multa", "DETRAN-SP", 350.00,
         (HOJE - timedelta(days=5)).isoformat(), "registrado", None,
         "Multa de trânsito veicular", None, "AIIP-2025-99821"),
        ("Taxa", "Receita Federal", 180.00,
         (HOJE - timedelta(days=10)).isoformat(), "registrado", None,
         "DAS - Simples Nacional", None, None),
        ("Luz", "Energisa Mato Grosso", 280.00,
         (HOJE - timedelta(days=3)).isoformat(), "registrado", None,
         "Conta de luz - atraso abril", None, "NF-LUZ-0424"),
        ("PIX Fornecedor", "Distribuidora ABC LTDA", 2150.00,
         (HOJE - timedelta(days=8)).isoformat(), "registrado", None,
         "Compra de matéria-prima", "11.222.333/0001-44", "NF-ABC-7710"),
        ("Internet", "Claro Brasil S.A.", 320.00,
         (HOJE - timedelta(days=15)).isoformat(), "registrado", None,
         "Link dedicado backup", None, "NF-CLR-3344"),

        # ── PRÓXIMO MÊS (futuros) — 6 lançamentos ─────────────────────────────
        ("Aluguel", "Imobiliária Central", 2800.00,
         (HOJE + timedelta(days=12)).isoformat(), "registrado", None,
         "Aluguel galpão", None, None),
        ("Boleto", "Banco Itaú", 450.00,
         (HOJE + timedelta(days=20)).isoformat(), "registrado", None,
         "Cobrança crédito empresarial", None, None),
        ("Boleto", "Fornecedor ABC LTDA", 780.00,
         (HOJE + timedelta(days=25)).isoformat(), "registrado", None,
         "Boleto fornecedor", None, "NF-ABC-7811"),
        ("PIX Fornecedor", "Office Suprimentos ME", 480.50,
         (HOJE + timedelta(days=10)).isoformat(), "registrado", None,
         "Material de escritório", "office@email.com", "NF-OFF-2020"),
        ("Reembolso", "Pedro Vendas", 215.00,
         (HOJE + timedelta(days=8)).isoformat(), "registrado", None,
         "Reembolso combustível", None, None),
        ("Taxa", "Prefeitura Campinas", 540.00,
         (HOJE + timedelta(days=18)).isoformat(), "registrado", None,
         "IPTU prédio comercial", None, "BOL-IPTU-2026"),

        # ── PAGOS — 6 lançamentos (variando pago_em) ──────────────────────────
        ("Reembolso", "Carlos Funcionário", 95.40,
         (HOJE - timedelta(days=3)).isoformat(), "pago",
         (HOJE - timedelta(days=2)).isoformat() + "T10:30:00",
         "Reembolso almoço cliente", None, None),
        ("Internet", "Vivo Fibra", 200.00,
         (HOJE - timedelta(days=25)).isoformat(), "pago",
         (HOJE - timedelta(days=24)).isoformat() + "T09:15:00",
         "Internet abril", None, "NF-VIVO-0424"),
        ("Água", "Sabesp", 115.30,
         (HOJE - timedelta(days=27)).isoformat(), "pago",
         (HOJE - timedelta(days=1)).isoformat() + "T14:20:00",
         "Conta de água abril", None, "NF-AGU-0424"),
        ("Boleto", "METALURGICA DDL LTDA.", 301.21,
         (HOJE + timedelta(days=5)).isoformat(), "pago",
         (HOJE - timedelta(days=2)).isoformat() + "T11:45:00",
         "Boleto pago antecipado", None, "NF-DDL-5544"),
        ("Aluguel", "Imobiliária Central", 2800.00,
         (HOJE - timedelta(days=23)).isoformat(), "pago",
         (HOJE - timedelta(days=22)).isoformat() + "T08:00:00",
         "Aluguel abril", None, None),
        ("PIX Funcionário", "Ana Beatriz", 1200.00,
         (HOJE - timedelta(days=4)).isoformat(), "pago",
         (HOJE - timedelta(days=3)).isoformat() + "T16:30:00",
         "Vale antecipação", "ana.beatriz@email.com", None),
    ]

    cap_em = datetime.now().isoformat()
    inseridos = 0

    for cat_nome, empresa, valor, venc, status, pago_em, desc, chave_pix, nota_fiscal in lancamentos:
        cat_id = cats.get(cat_nome)
        if not cat_id:
            print(f"⚠ Categoria '{cat_nome}' não existe, pulando")
            continue

        cur.execute("""
            INSERT INTO boletos (
                valor, vencimento, beneficiario_texto, descricao, chave_pix, nota_fiscal,
                categoria_id, status, capturado_por, capturado_em, pago_em, pago_por
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            valor, venc, empresa, desc, chave_pix, nota_fiscal,
            cat_id, status, master_id, cap_em,
            pago_em, master_id if pago_em else None,
        ))
        inseridos += 1

    conn.commit()
    print(f"\n✓ {inseridos} lançamentos inseridos")
    print(f"\nHoje: {HOJE.strftime('%d/%m/%Y')} ({HOJE.strftime('%A')})")
    print(f"Semana corrente: {HOJE.strftime('%d/%m')} → {SEMANA_FIM.strftime('%d/%m')}")
    conn.close()


if __name__ == "__main__":
    main()

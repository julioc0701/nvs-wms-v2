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

    lancamentos = [
        # ESTA SEMANA — A PAGAR (5 boletos)
        ("Luz", "Energisa Mato Grosso", 350.00,
         (HOJE + timedelta(days=2)).isoformat(), "registrado", None,
         "Conta de luz - maio", None),
        ("Água", "Sabesp", 120.50,
         (HOJE + timedelta(days=3)).isoformat(), "registrado", None,
         "Conta de água - maio", None),
        ("Internet", "Vivo Fibra", 200.00,
         (HOJE + timedelta(days=5)).isoformat(), "registrado", None,
         "Internet 600MB", None),
        ("PIX Fornecedor", "João da Silva ME", 1500.00,
         (HOJE + timedelta(days=4)).isoformat(), "registrado", None,
         "Pagamento materiais", "12345678901"),
        ("PIX Funcionário", "Maria Souza", 800.00,
         (HOJE + timedelta(days=6)).isoformat(), "registrado", None,
         "Adiantamento salário", "maria@email.com"),

        # ATRASADOS (3 lançamentos com vencimento passado, status registrado)
        ("Multa", "DETRAN-SP", 350.00,
         (HOJE - timedelta(days=5)).isoformat(), "registrado", None,
         "Multa de trânsito", None),
        ("Taxa", "Receita Federal", 180.00,
         (HOJE - timedelta(days=10)).isoformat(), "registrado", None,
         "DAS - Simples Nacional", None),
        ("Luz", "Energisa Mato Grosso", 280.00,
         (HOJE - timedelta(days=3)).isoformat(), "registrado", None,
         "Conta de luz - atraso", None),

        # FUTURO — PRÓXIMO MÊS (3 lançamentos)
        ("Aluguel", "Imobiliária Central", 2800.00,
         (HOJE + timedelta(days=12)).isoformat(), "registrado", None,
         "Aluguel galpão", None),
        ("Boleto", "Banco Itaú", 450.00,
         (HOJE + timedelta(days=20)).isoformat(), "registrado", None,
         None, None),
        ("Boleto", "Fornecedor ABC LTDA", 780.00,
         (HOJE + timedelta(days=25)).isoformat(), "registrado", None,
         None, None),

        # PAGOS (3 lançamentos com pago_em recente)
        ("Reembolso", "Carlos Funcionário", 95.40,
         (HOJE - timedelta(days=3)).isoformat(), "pago",
         (HOJE - timedelta(days=2)).isoformat() + "T10:30:00",
         "Reembolso almoço cliente", None),
        ("Internet", "Vivo Fibra", 200.00,
         (HOJE - timedelta(days=25)).isoformat(), "pago",
         (HOJE - timedelta(days=24)).isoformat() + "T09:15:00",
         "Internet abril", None),
        ("Água", "Sabesp", 115.30,
         (HOJE - timedelta(days=27)).isoformat(), "pago",
         (HOJE - timedelta(days=1)).isoformat() + "T14:20:00",
         "Conta de água abril", None),

        # Categoria "Outros" mais uma pra completar variedade
        ("Outros", "Cartório Sé", 89.00,
         (HOJE + timedelta(days=7)).isoformat(), "registrado", None,
         "Reconhecimento de firma", None),
    ]

    cap_em = datetime.now().isoformat()
    inseridos = 0

    for cat_nome, empresa, valor, venc, status, pago_em, desc, chave_pix in lancamentos:
        cat_id = cats.get(cat_nome)
        if not cat_id:
            print(f"⚠ Categoria '{cat_nome}' não existe, pulando")
            continue

        cur.execute("""
            INSERT INTO boletos (
                valor, vencimento, beneficiario_texto, descricao, chave_pix,
                categoria_id, status, capturado_por, capturado_em, pago_em, pago_por
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            valor, venc, empresa, desc, chave_pix,
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

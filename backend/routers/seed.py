"""
Endpoint de seed para testes — cria dados realistas sem precisar de PDF.
Remover antes de produção.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Operator, Printer, Session, PickingItem, Barcode, Label

router = APIRouter()

ITEMS = [
    {"sku": "MLB-001-A", "description": "Fone Bluetooth JBL Tune 510BT Preto", "qty": 3,
     "barcodes": ["7891234000001", "MLB-001-A"]},
    {"sku": "MLB-002-B", "description": "Carregador USB-C 65W Anker PowerPort", "qty": 5,
     "barcodes": ["7891234000002", "MLB-002-B"]},
    {"sku": "MLB-003-C", "description": "Capinha iPhone 15 Pro Silicone Azul",  "qty": 2,
     "barcodes": ["7891234000003", "MLB-003-C"]},
    {"sku": "MLB-004-D", "description": "Mousepad Gamer RGB XL 90x40cm",        "qty": 1,
     "barcodes": ["7891234000004", "MLB-004-D"]},
    {"sku": "MLB-005-E", "description": "Cabo HDMI 2.1 8K 2m Multilaser",       "qty": 4,
     "barcodes": ["7891234000005", "MLB-005-E"]},
]

ZPL_TEMPLATE = """^XA
^FO50,50^A0N,40,40^FDMLB Warehouse^FS
^FO50,110^A0N,30,30^FD{sku}^FS
^FO50,160^A0N,25,25^FD{description}^FS
^FO50,210^BY3^BCN,80,Y,N,N^FD{barcode}^FS
^FO50,320^A0N,25,25^FDEtiqueta {index} de {total}^FS
^XZ"""


@router.post("/seed", status_code=201)
def seed(db: DBSession = Depends(get_db)):
    # Operador
    op = db.query(Operator).filter(Operator.name == "Teste").first()
    if not op:
        op = Operator(name="Teste", badge="BADGE-TEST-001")
        db.add(op)
        db.flush()

    # Impressora fictícia
    pr = db.query(Printer).filter(Printer.name == "Zebra Teste").first()
    if not pr:
        pr = Printer(name="Zebra Teste", ip_address="192.168.1.100", port=9100)
        db.add(pr)

    # Sessão de teste
    code = "ML-TESTE-001"
    existing = db.query(Session).filter(Session.session_code == code).first()
    if existing:
        db.commit()
        return {"status": "já existe", "session_id": existing.id, "operator_id": op.id}

    sess = Session(session_code=code, operator_id=op.id, status="open")
    db.add(sess)
    db.flush()

    for item_data in ITEMS:
        pi = PickingItem(
            session_id=sess.id,
            sku=item_data["sku"],
            description=item_data["description"],
            qty_required=item_data["qty"],
        )
        db.add(pi)

        # Barcodes
        for bc in item_data["barcodes"]:
            if not db.query(Barcode).filter(Barcode.barcode == bc).first():
                db.add(Barcode(barcode=bc, sku=item_data["sku"],
                               is_primary=(bc == item_data["barcodes"][0])))

        # Etiquetas ZPL (uma por unidade)
        for i in range(1, item_data["qty"] + 1):
            zpl = ZPL_TEMPLATE.format(
                sku=item_data["sku"],
                description=item_data["description"][:30],
                barcode=item_data["barcodes"][0],
                index=i,
                total=item_data["qty"],
            )
            db.add(Label(session_id=sess.id, sku=item_data["sku"],
                         label_index=i, zpl_content=zpl))

    db.commit()
    return {
        "status": "ok",
        "session_id": sess.id,
        "session_code": code,
        "operator_id": op.id,
        "operator_badge": "BADGE-TEST-001",
        "itens": len(ITEMS),
        "barcodes_de_teste": {i["sku"]: i["barcodes"][0] for i in ITEMS},
    }

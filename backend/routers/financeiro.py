"""Rotas de Financeiro — Boletos a pagar."""
from datetime import date as DateType, datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Boleto, BoletoBeneficiario
from services.boleto_parser import parse_boleto, BoletoInvalidoError
from services.boleto_storage import salvar_foto_base64, caminho_foto, excluir_foto
from services.boleto_vision import extrair_linha_digitavel, BoletoVisionError
from services.boleto_pdf import extrair_linha_digitavel_de_pdf, BoletoPdfError

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────


class ScanRequest(BaseModel):
    codigo_ou_linha: str


class ScanFotoRequest(BaseModel):
    foto_base64: str


class CriarBoletoRequest(BaseModel):
    codigo_ou_linha: str
    operator_id: int
    beneficiario_id: int | None = None
    beneficiario_texto: str | None = None
    observacao: str | None = None
    foto_base64: str | None = None


class EditarBoletoRequest(BaseModel):
    beneficiario_id: int | None = None
    beneficiario_texto: str | None = None
    observacao: str | None = None


class PagarRequest(BaseModel):
    operator_id: int


# ── Helpers ───────────────────────────────────────────────────────────────────


def _boleto_to_dict(b: Boleto, db: DBSession) -> dict:
    """Serializa Boleto incluindo nome do beneficiário e operadores."""
    from models import Operator
    benef = (
        db.query(BoletoBeneficiario).filter_by(id=b.beneficiario_id).first()
        if b.beneficiario_id else None
    )
    capturador = db.query(Operator).filter_by(id=b.capturado_por).first()
    pagador = db.query(Operator).filter_by(id=b.pago_por).first() if b.pago_por else None
    return {
        "id": b.id,
        "codigo_barras": b.codigo_barras,
        "linha_digitavel": b.linha_digitavel,
        "banco_emissor": b.banco_emissor,
        "valor": b.valor,
        "vencimento": b.vencimento.isoformat(),
        "beneficiario_id": b.beneficiario_id,
        "beneficiario_razao_social": benef.razao_social if benef else None,
        "beneficiario_texto": b.beneficiario_texto,
        "observacao": b.observacao,
        "foto_path": b.foto_path,
        "status": b.status,
        "capturado_por": b.capturado_por,
        "capturado_por_nome": capturador.name if capturador else None,
        "capturado_em": b.capturado_em.isoformat(),
        "pago_em": b.pago_em.isoformat() if b.pago_em else None,
        "pago_por": b.pago_por,
        "pago_por_nome": pagador.name if pagador else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────


def _parsed_para_dict(parsed, db: DBSession) -> dict:
    """Monta a resposta do scan a partir de um BoletoParsed (com sugestão + duplicata)."""
    existente = db.query(Boleto).filter(Boleto.codigo_barras == parsed.codigo_barras).first()
    duplicata = None
    if existente:
        duplicata = {
            "id": existente.id,
            "capturado_em": existente.capturado_em.isoformat(),
            "capturado_por_id": existente.capturado_por,
        }

    prefix = parsed.campo_livre[:6]
    benef = (
        db.query(BoletoBeneficiario)
        .filter(BoletoBeneficiario.banco == parsed.banco)
        .filter(BoletoBeneficiario.campo_livre_prefix == prefix)
        .first()
    )
    beneficiario_sugerido = (
        {"id": benef.id, "razao_social": benef.razao_social} if benef else None
    )

    return {
        "codigo_barras": parsed.codigo_barras,
        "linha_digitavel": parsed.linha_digitavel,
        "banco": parsed.banco,
        "valor": float(parsed.valor),
        "vencimento": parsed.vencimento.isoformat(),
        "campo_livre": parsed.campo_livre,
        "dv_ok": parsed.dv_ok,
        "beneficiario_sugerido": beneficiario_sugerido,
        "duplicata": duplicata,
    }


@router.post("/boletos/scan")
def scan_boleto(body: ScanRequest, db: DBSession = Depends(get_db)):
    """Parseia o código sem salvar. Retorna dados + sugestão de beneficiário + duplicata."""
    try:
        parsed = parse_boleto(body.codigo_ou_linha)
    except BoletoInvalidoError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _parsed_para_dict(parsed, db)


@router.post("/boletos/scan-pdf")
async def scan_boleto_pdf(file: UploadFile = File(...), db: DBSession = Depends(get_db)):
    """Recebe upload de PDF de boleto, extrai linha digitável via pdfplumber e parseia.

    Retorna o mesmo shape do `/scan` e `/scan-foto` para que o frontend possa usar
    o mesmo fluxo de confirmação.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Arquivo precisa ser PDF")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=400, detail="PDF maior que 10 MB")

    try:
        linha = extrair_linha_digitavel_de_pdf(content)
    except BoletoPdfError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        parsed = parse_boleto(linha)
    except BoletoInvalidoError as e:
        raise HTTPException(
            status_code=422,
            detail=f"PDF tem '{linha[:20]}...' mas não é um boleto válido: {e}",
        )
    return _parsed_para_dict(parsed, db)


@router.post("/boletos/scan-foto")
async def scan_boleto_foto(body: ScanFotoRequest, db: DBSession = Depends(get_db)):
    """Recebe foto base64, extrai linha digitável via Gemini Vision e parseia.

    Retorna o mesmo shape do `/scan` (dados parseados + sugestão de beneficiário
    + duplicata) para que o frontend possa usar o mesmo fluxo de confirmação.
    """
    try:
        linha = await extrair_linha_digitavel(body.foto_base64)
    except BoletoVisionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        parsed = parse_boleto(linha)
    except BoletoInvalidoError as e:
        raise HTTPException(
            status_code=422,
            detail=f"A IA leu '{linha[:20]}...' mas não é um boleto válido: {e}",
        )
    return _parsed_para_dict(parsed, db)


@router.post("/boletos", status_code=201)
def criar_boleto(body: CriarBoletoRequest, db: DBSession = Depends(get_db)):
    try:
        parsed = parse_boleto(body.codigo_ou_linha)
    except BoletoInvalidoError as e:
        raise HTTPException(status_code=400, detail=str(e))

    existente = db.query(Boleto).filter(Boleto.codigo_barras == parsed.codigo_barras).first()
    if existente:
        from models import Operator
        cap = db.query(Operator).filter_by(id=existente.capturado_por).first()
        quem = cap.name if cap else "operador desconhecido"
        quando = existente.capturado_em.strftime("%d/%m/%Y %H:%M")
        raise HTTPException(
            status_code=409,
            detail=f"Este boleto já consta registrado (capturado por {quem} em {quando}).",
        )

    benef_id = body.beneficiario_id
    if not benef_id and body.beneficiario_texto:
        prefix = parsed.campo_livre[:6]
        match = (
            db.query(BoletoBeneficiario)
            .filter(BoletoBeneficiario.banco == parsed.banco)
            .filter(BoletoBeneficiario.campo_livre_prefix == prefix)
            .first()
        )
        if match:
            benef_id = match.id
        else:
            novo_benef = BoletoBeneficiario(
                razao_social=body.beneficiario_texto.strip(),
                banco=parsed.banco,
                campo_livre_prefix=prefix,
                criado_por=body.operator_id,
            )
            db.add(novo_benef)
            db.flush()
            benef_id = novo_benef.id

    boleto = Boleto(
        codigo_barras=parsed.codigo_barras,
        linha_digitavel=parsed.linha_digitavel,
        banco_emissor=parsed.banco,
        valor=float(parsed.valor),
        vencimento=parsed.vencimento,
        beneficiario_id=benef_id,
        beneficiario_texto=body.beneficiario_texto,
        observacao=body.observacao,
        status="registrado",
        capturado_por=body.operator_id,
        capturado_em=datetime.utcnow(),
    )
    db.add(boleto)
    try:
        db.flush()
    except IntegrityError:
        # Race condition: dois requests simultâneos tentaram salvar o mesmo boleto.
        # O UNIQUE no codigo_barras impede a duplicação no banco.
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Este boleto já consta registrado.",
        )

    if body.foto_base64:
        nome_arquivo = salvar_foto_base64(boleto.id, body.foto_base64)
        boleto.foto_path = nome_arquivo

    db.commit()
    db.refresh(boleto)
    return _boleto_to_dict(boleto, db)


@router.get("/boletos")
def listar_boletos(
    status: str | None = None,
    vencimento_de: str | None = None,
    vencimento_ate: str | None = None,
    beneficiario_id: int | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    db: DBSession = Depends(get_db),
):
    q = db.query(Boleto)
    if status:
        q = q.filter(Boleto.status == status)
    if vencimento_de:
        q = q.filter(Boleto.vencimento >= DateType.fromisoformat(vencimento_de))
    if vencimento_ate:
        q = q.filter(Boleto.vencimento <= DateType.fromisoformat(vencimento_ate))
    if beneficiario_id:
        q = q.filter(Boleto.beneficiario_id == beneficiario_id)
    if valor_min is not None:
        q = q.filter(Boleto.valor >= valor_min)
    if valor_max is not None:
        q = q.filter(Boleto.valor <= valor_max)

    q = q.order_by(Boleto.vencimento.asc(), Boleto.id.desc())
    boletos = q.all()
    return {
        "boletos": [_boleto_to_dict(b, db) for b in boletos],
        "total": len(boletos),
        "valor_total": sum(b.valor for b in boletos),
    }


@router.get("/boletos/{boleto_id}")
def detalhar_boleto(boleto_id: int, db: DBSession = Depends(get_db)):
    b = db.query(Boleto).filter_by(id=boleto_id).first()
    if not b:
        raise HTTPException(404, "Boleto não encontrado")
    return _boleto_to_dict(b, db)


@router.patch("/boletos/{boleto_id}")
def editar_boleto(boleto_id: int, body: EditarBoletoRequest, db: DBSession = Depends(get_db)):
    b = db.query(Boleto).filter_by(id=boleto_id).first()
    if not b:
        raise HTTPException(404, "Boleto não encontrado")
    if body.beneficiario_id is not None:
        b.beneficiario_id = body.beneficiario_id
    if body.beneficiario_texto is not None:
        b.beneficiario_texto = body.beneficiario_texto
    if body.observacao is not None:
        b.observacao = body.observacao
    db.commit()
    db.refresh(b)
    return _boleto_to_dict(b, db)


@router.post("/boletos/{boleto_id}/pagar")
def marcar_pago(boleto_id: int, body: PagarRequest, db: DBSession = Depends(get_db)):
    b = db.query(Boleto).filter_by(id=boleto_id).first()
    if not b:
        raise HTTPException(404, "Boleto não encontrado")
    b.status = "pago"
    b.pago_em = datetime.utcnow()
    b.pago_por = body.operator_id
    db.commit()
    db.refresh(b)
    return _boleto_to_dict(b, db)


@router.post("/boletos/{boleto_id}/reabrir")
def reabrir_boleto(boleto_id: int, db: DBSession = Depends(get_db)):
    b = db.query(Boleto).filter_by(id=boleto_id).first()
    if not b:
        raise HTTPException(404, "Boleto não encontrado")
    b.status = "registrado"
    b.pago_em = None
    b.pago_por = None
    db.commit()
    db.refresh(b)
    return _boleto_to_dict(b, db)


@router.delete("/boletos/{boleto_id}")
def excluir_boleto(boleto_id: int, db: DBSession = Depends(get_db)):
    b = db.query(Boleto).filter_by(id=boleto_id).first()
    if not b:
        raise HTTPException(404, "Boleto não encontrado")
    if b.foto_path:
        excluir_foto(b.foto_path)
    db.delete(b)
    db.commit()
    return {"status": "ok"}


@router.get("/foto/{boleto_id}")
def baixar_foto(boleto_id: int, db: DBSession = Depends(get_db)):
    b = db.query(Boleto).filter_by(id=boleto_id).first()
    if not b or not b.foto_path:
        raise HTTPException(404, "Foto não encontrada")
    caminho = caminho_foto(b.foto_path)
    if not caminho:
        raise HTTPException(404, "Arquivo de foto não existe no disco")
    return FileResponse(caminho, media_type="image/jpeg")


@router.get("/beneficiarios")
def listar_beneficiarios(q: str | None = None, db: DBSession = Depends(get_db)):
    query = db.query(BoletoBeneficiario)
    if q:
        query = query.filter(BoletoBeneficiario.razao_social.ilike(f"%{q}%"))
    query = query.order_by(BoletoBeneficiario.razao_social.asc()).limit(20)
    return [
        {"id": b.id, "razao_social": b.razao_social, "banco": b.banco}
        for b in query.all()
    ]

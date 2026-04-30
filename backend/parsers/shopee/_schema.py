from dataclasses import dataclass, field
from typing import List


@dataclass
class SKU:
    sku_vendedor: str
    shopee_sku_id: str
    nome_produto: str
    variacao: str
    sku_armazem: str
    qnt_aprovada: int


@dataclass
class ParseResult:
    asn_id: str
    data_inbound: str
    metodo_entrega: str
    skus: List[SKU]
    total_declarado: int
    total_calculado: int
    paginas_com_dedupe: List[int] = field(default_factory=list)


class PickingListIntegrityError(Exception):
    """Raised when total_calculado != total_declarado."""
    def __init__(self, total_calculado: int, total_declarado: int):
        diff = total_calculado - total_declarado
        super().__init__(
            f"Integrity check failed: calculated={total_calculado}, "
            f"declared={total_declarado}, diff={diff:+d}"
        )
        self.total_calculado = total_calculado
        self.total_declarado = total_declarado
        self.diff = diff

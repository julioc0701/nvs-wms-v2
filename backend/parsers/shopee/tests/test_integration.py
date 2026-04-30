"""
Integration tests — usa o PDF real FBSINBR2026042800054.pdf.
Critérios obrigatórios do prompt:
  1. total_calculado == total_declarado == 11820
  2. Páginas bugadas (4 e 6) extraídas corretamente
  3. SKUs numéricos (588, 576, 502) válidos
  4. Retorna ParseResult (não dict)
  5. paginas_com_dedupe inclui [4, 6]
"""
import pytest
from parsers.shopee import parse_picking_list, ParseResult, SKU, PickingListIntegrityError

FIXTURE_PDF = "parsers/shopee/tests/fixtures/FBSINBR2026042800054.pdf"

EXPECTED_TOTAL = 11820
EXPECTED_ASN = "INBRFSP12604290170"
EXPECTED_DATA = "2026-05-06 06:00 (GMT-03)"
EXPECTED_METODO = "Pickup"
EXPECTED_BUGGY_PAGES = [4, 6]


@pytest.fixture(scope="module")
def result():
    return parse_picking_list(FIXTURE_PDF)


class TestReturnType:
    def test_returns_parse_result(self, result):
        assert isinstance(result, ParseResult)

    def test_skus_are_sku_objects(self, result):
        for s in result.skus:
            assert isinstance(s, SKU)


class TestMetadata:
    def test_asn_id(self, result):
        assert result.asn_id == EXPECTED_ASN

    def test_data_inbound(self, result):
        assert result.data_inbound == EXPECTED_DATA

    def test_metodo_entrega(self, result):
        assert result.metodo_entrega == EXPECTED_METODO


class TestTotalIntegrity:
    def test_total_calculado_equals_declarado(self, result):
        assert result.total_calculado == result.total_declarado

    def test_total_is_11820(self, result):
        assert result.total_calculado == EXPECTED_TOTAL

    def test_total_declarado_is_11820(self, result):
        assert result.total_declarado == EXPECTED_TOTAL


class TestDedupeObservability:
    def test_buggy_pages_detected(self, result):
        assert set(EXPECTED_BUGGY_PAGES).issubset(set(result.paginas_com_dedupe))


class TestSKUCount:
    def test_minimum_sku_count(self, result):
        assert len(result.skus) >= 60


class TestNumericSKUs:
    """SKUs numéricos são válidos — não filtrar."""

    def test_sku_588_present(self, result):
        vendors = [s.sku_vendedor for s in result.skus]
        assert "588" in vendors

    def test_sku_576_present(self, result):
        vendors = [s.sku_vendedor for s in result.skus]
        assert "576" in vendors

    def test_sku_502_present(self, result):
        vendors = [s.sku_vendedor for s in result.skus]
        assert "502" in vendors


class TestBuggyPages:
    """Páginas 4 e 6 devem ter todos os SKUs corretos."""

    def test_farol_intruder_qty(self, result):
        item = next((s for s in result.skus if "FarolIntruder" in s.sku_vendedor), None)
        assert item is not None
        assert item.qnt_aprovada == 100

    def test_vlib45_qty(self, result):
        item = next((s for s in result.skus if s.sku_vendedor == "VLIB45"), None)
        assert item is not None
        assert item.qnt_aprovada == 200

    def test_cavletao_qty(self, result):
        item = next((s for s in result.skus if "CAVLET" in s.sku_vendedor), None)
        assert item is not None
        assert item.qnt_aprovada == 300

    def test_kit_visrepspi_qty(self, result):
        item = next((s for s in result.skus if "KIT-VISREPSPI" in s.sku_vendedor), None)
        assert item is not None
        assert item.qnt_aprovada == 200


class TestCleanPages:
    """Páginas íntegras devem extrair corretamente — regressão zero."""

    def test_veox_qty(self, result):
        item = next((s for s in result.skus if s.sku_vendedor == "VEOX"), None)
        assert item is not None
        assert item.qnt_aprovada == 200

    def test_viscamvision_qty(self, result):
        item = next((s for s in result.skus if s.sku_vendedor == "VISCAMVISION"), None)
        assert item is not None
        assert item.qnt_aprovada == 100

    def test_embr125_qty(self, result):
        item = next((s for s in result.skus if s.sku_vendedor == "EMBR125"), None)
        assert item is not None
        assert item.qnt_aprovada == 200

    def test_kitls2_qty(self, result):
        item = next((s for s in result.skus if s.sku_vendedor == "KITLS2"), None)
        assert item is not None
        assert item.qnt_aprovada == 1000

    def test_no_zero_qty_items(self, result):
        zero_items = [s for s in result.skus if s.qnt_aprovada == 0]
        assert zero_items == [], f"Items with qty=0: {[s.sku_vendedor for s in zero_items]}"

    def test_no_garbled_vendor_names(self, result):
        # Garbled names would have doubled chars like "SSKKUU" or "NNoo"
        for s in result.skus:
            assert "NNoo" not in s.sku_vendedor
            assert "SSKKUU" not in s.sku_vendedor


class TestIntegrityError:
    def test_wrong_pdf_raises_or_succeeds(self):
        # If this PDF is valid it should not raise
        result = parse_picking_list(FIXTURE_PDF)
        assert result.total_calculado == result.total_declarado


class TestCompatWrapper:
    def test_parse_picking_pdf_returns_list_of_dicts(self):
        from parsers.shopee import parse_picking_pdf
        with open(FIXTURE_PDF, "rb") as f:
            pdf_bytes = f.read()
        items = parse_picking_pdf(pdf_bytes)
        assert isinstance(items, list)
        assert len(items) >= 60
        for item in items:
            assert "sku" in item
            assert "qty_required" in item
            assert item["qty_required"] > 0

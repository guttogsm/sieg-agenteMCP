from ..ports import GeradorPdfLocalPort
from ...domain.value_objects import ResultadoPdf


class GerarDanfceViaXml:
    """Gera a DANFCE (NFC-e) a partir do XML — via GeradorPdfLocalPort, não
    da API SIEG (que não tem essa rota; ver node_gerador_pdf_local.py)."""

    def __init__(self, gerador: GeradorPdfLocalPort):
        self._gerador = gerador

    def executar(self, xml_bytes: bytes) -> ResultadoPdf:
        return self._gerador.gerar_danfce_via_xml(xml_bytes)

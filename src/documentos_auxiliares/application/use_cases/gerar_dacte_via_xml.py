from ..ports import DocumentoAuxiliarGatewayPort
from ...domain.value_objects import ResultadoPdf


class GerarDacteViaXml:
    def __init__(self, gateway: DocumentoAuxiliarGatewayPort):
        self._gateway = gateway

    def executar(self, xml_base64: str) -> ResultadoPdf:
        return self._gateway.gerar_dacte_via_xml(xml_base64)

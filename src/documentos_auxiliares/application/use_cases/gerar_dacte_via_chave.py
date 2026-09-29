from ..ports import DocumentoAuxiliarGatewayPort
from ...domain.value_objects import ResultadoPdf


class GerarDacteViaChave:
    def __init__(self, gateway: DocumentoAuxiliarGatewayPort):
        self._gateway = gateway

    def executar(self, xml_key: str) -> ResultadoPdf:
        return self._gateway.gerar_dacte_via_chave(xml_key)

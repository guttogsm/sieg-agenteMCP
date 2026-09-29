from ..ports import DocumentoFiscalGatewayPort
from ...domain.value_objects import ResultadoDownload, TipoDocumentoFiscal


class BaixarXmlEspecifico:
    def __init__(self, gateway: DocumentoFiscalGatewayPort):
        self._gateway = gateway

    def executar(
        self,
        xml_key: str,
        xml_type: TipoDocumentoFiscal,
        download_event: bool = False,
    ) -> ResultadoDownload:
        return self._gateway.baixar_xml_especifico(xml_key, xml_type, download_event)

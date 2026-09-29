from ..ports import DocumentoFiscalGatewayPort
from ...domain.value_objects import FiltroXmlsLote, ResultadoDownload


class BaixarXmlsEmLote:
    def __init__(self, gateway: DocumentoFiscalGatewayPort):
        self._gateway = gateway

    def executar(self, filtro: FiltroXmlsLote) -> ResultadoDownload:
        return self._gateway.baixar_xmls_em_lote(filtro)

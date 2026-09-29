"""Porta do contexto Documentos Fiscais.

A camada de aplicação depende só desta interface — nunca de requests,
da SiegHttpClient ou de qualquer detalhe de HTTP diretamente.
"""
from typing import Protocol

from ..domain.value_objects import FiltroXmlsLote, ResultadoDownload, TipoDocumentoFiscal


class DocumentoFiscalGatewayPort(Protocol):
    def baixar_xml_especifico(
        self,
        xml_key: str,
        xml_type: TipoDocumentoFiscal,
        download_event: bool = False,
    ) -> ResultadoDownload: ...

    def baixar_xmls_em_lote(self, filtro: FiltroXmlsLote) -> ResultadoDownload: ...

"""Porta do contexto Relatórios.

A camada de aplicação depende só desta interface — nunca de requests,
da SiegHttpClient ou de qualquer detalhe de HTTP diretamente.
"""
from typing import Protocol

from ..domain.value_objects import ResultadoRelatorio, SolicitacaoRelatorio


class RelatorioGatewayPort(Protocol):
    def gerar_relatorio_xml(self, solicitacao: SolicitacaoRelatorio) -> ResultadoRelatorio: ...

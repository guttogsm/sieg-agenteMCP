from ..ports import RelatorioGatewayPort
from ...domain.value_objects import ResultadoRelatorio, SolicitacaoRelatorio


class GerarRelatorioXml:
    def __init__(self, gateway: RelatorioGatewayPort):
        self._gateway = gateway

    def executar(self, solicitacao: SolicitacaoRelatorio) -> ResultadoRelatorio:
        return self._gateway.gerar_relatorio_xml(solicitacao)

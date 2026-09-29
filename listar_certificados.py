from ...domain.entities import CertificadoResumo
from ..ports import CertificadoGatewayPort


class ListarCertificados:
    def __init__(self, gateway: CertificadoGatewayPort):
        self._gateway = gateway

    def executar(self, active: bool = True, pagina: int = 0) -> list[CertificadoResumo]:
        return self._gateway.listar(active=active, pagina=pagina)

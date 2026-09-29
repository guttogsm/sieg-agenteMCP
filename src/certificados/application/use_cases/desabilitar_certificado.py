from ..ports import CertificadoGatewayPort


class DesabilitarCertificado:
    """Ação sensível: a confirmação explícita do usuário é responsabilidade
    da política de confirmação da Orquestração, executada ANTES de chegar
    aqui. Este caso de uso assume que a intenção já foi confirmada."""

    def __init__(self, gateway: CertificadoGatewayPort):
        self._gateway = gateway

    def executar(self, certificado_id: str) -> None:
        self._gateway.desabilitar(certificado_id)

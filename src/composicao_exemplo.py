"""Exemplo de composição (o embrião do futuro app_factory.py).

Mostra como as peças se encaixam: infraestrutura concreta é criada aqui,
na borda do sistema, e injetada nos casos de uso através das portas. Nada
em domain/ ou application/ aparece neste arquivo por acidente — só
SiegJwtProvider, SiegHttpClient e SiegCertificadoGateway, que são os
únicos que conhecem HTTP/JWT/API Key.

Rode com as variáveis de ambiente definidas (ver .env.example) para ver a
listagem de certificados de verdade.
"""
import os

from dotenv import load_dotenv

from certificados.application.use_cases.listar_certificados import ListarCertificados
from certificados.infrastructure.sieg_certificado_gateway import SiegCertificadoGateway
from shared.infrastructure.auth.sieg_jwt_provider import SiegJwtProvider
from shared.infrastructure.sieg_http_client import SiegHttpClient


def montar_gateway_certificados() -> SiegCertificadoGateway:
    base_url = os.environ.get("SIEG_BASE_URL", "https://api.sieg.com")

    token_provider = SiegJwtProvider(
        base_url=base_url,
        client_id=os.environ["SIEG_CLIENT_ID"],
        secret_key=os.environ["SIEG_SECRET_KEY"],
    )
    http = SiegHttpClient(
        base_url=base_url,
        token_provider=token_provider,
        chave_leitura=os.environ["SIEG_API_KEY_LEITURA"],
        chave_escrita=os.environ["SIEG_API_KEY_ESCRITA"],
    )
    return SiegCertificadoGateway(http)


if __name__ == "__main__":
    load_dotenv()  # lê o arquivo .env na raiz do projeto (não o .env.example)
    gateway = montar_gateway_certificados()
    listar = ListarCertificados(gateway)

    certificados = listar.executar(active=True, pagina=0)
    for c in certificados:
        situacao = "ativo" if c.ativo and not c.deletado else "inativo/deletado"
        print(f"{c.id} — {c.nome} ({situacao})")

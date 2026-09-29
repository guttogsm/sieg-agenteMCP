"""Testa status / habilitar / desabilitar contra um certificado real.

Fecha o item 1 dos proximos passos do documento de registro: validar
esses tres endpoints, ate agora implementados mas nunca chamados de
verdade.

O certificado-alvo eh localizado pelo CNPJ (mais robusto que fixar um
id de certificado que pode ter mudado/expirado) — CNPJ valido para
teste: 69192961000141. O script lista os certificados, acha o que
bate com esse CNPJ, e usa o id dele nas chamadas de status/habilitar/
desabilitar.

Rode de dentro de sieg-agente/src, com o .env na raiz do projeto:
    cd sieg-agente/src
    python testar_status_habilitar_desabilitar.py
"""
import json
import os
import re
import sys

from dotenv import load_dotenv

from certificados.application.use_cases.consultar_status_certificado import (
    ConsultarStatusCertificado,
)
from certificados.application.use_cases.desabilitar_certificado import DesabilitarCertificado
from certificados.application.use_cases.habilitar_certificado import HabilitarCertificado
from certificados.application.use_cases.listar_certificados import ListarCertificados
from certificados.domain.exceptions import CertificadoRequisicaoInvalidaError
from certificados.infrastructure.sieg_certificado_gateway import SiegCertificadoGateway
from shared.infrastructure.auth.sieg_jwt_provider import SiegJwtProvider
from shared.infrastructure.sieg_http_client import SiegHttpClient

CNPJ_ALVO = "69192961000141"


def _so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def montar_gateway() -> SiegCertificadoGateway:
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


def localizar_certificado_por_cnpj(gateway: SiegCertificadoGateway, cnpj: str):
    listar = ListarCertificados(gateway)
    alvo = _so_digitos(cnpj)
    # varre ativos e inativos, algumas paginas (ajuste se a conta tiver mais)
    for active in (True, False):
        for pagina in range(0, 5):
            try:
                certificados = listar.executar(active=active, pagina=pagina)
            except CertificadoRequisicaoInvalidaError:
                # CONFIRMADO em teste real (21/09/2026): paginar alem do
                # total de certificados devolve HTTP 404, nao lista vazia.
                # Trata como "acabaram as paginas" pra esse filtro de active.
                break
            if not certificados:
                break
            for c in certificados:
                if _so_digitos(c.cnpj_cpf) == alvo:
                    return c
    return None


def passo(titulo, fn):
    print(f"\n=== {titulo} ===")
    try:
        resultado = fn()
        print(f"OK -> {resultado!r}")
        return {"titulo": titulo, "ok": True, "resultado": resultado}
    except CertificadoRequisicaoInvalidaError as exc:
        print(f"ERRO (CertificadoRequisicaoInvalidaError) -> {exc.args}")
        return {"titulo": titulo, "ok": False, "erro": str(exc.args)}
    except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer coisa pro relatorio
        print(f"ERRO ({type(exc).__name__}) -> {exc}")
        return {"titulo": titulo, "ok": False, "erro": f"{type(exc).__name__}: {exc}"}


def main():
    load_dotenv()
    gateway = montar_gateway()

    print(f"Procurando certificado com CNPJ {CNPJ_ALVO}...")
    certificado = localizar_certificado_por_cnpj(gateway, CNPJ_ALVO)
    if certificado is None:
        print(
            f"Nenhum certificado encontrado com CNPJ {CNPJ_ALVO} nas paginas "
            "verificadas (active=True/False, paginas 0-4). Ajuste o range de "
            "paginas no script ou confirme o CNPJ."
        )
        sys.exit(1)

    print(f"Certificado encontrado: id={certificado.id} nome={certificado.nome!r}")

    status_uc = ConsultarStatusCertificado(gateway)
    habilitar_uc = HabilitarCertificado(gateway)
    desabilitar_uc = DesabilitarCertificado(gateway)

    certificado_id = certificado.id
    resultados = []
    resultados.append(passo("status (inicial)", lambda: status_uc.executar(certificado_id)))
    resultados.append(passo("habilitar", lambda: habilitar_uc.executar(certificado_id)))
    resultados.append(passo("status (apos habilitar)", lambda: status_uc.executar(certificado_id)))
    resultados.append(passo("desabilitar", lambda: desabilitar_uc.executar(certificado_id)))
    resultados.append(passo("status (apos desabilitar)", lambda: status_uc.executar(certificado_id)))

    print("\n\n===== RESUMO (JSON) =====")
    saida = {
        "cnpj_alvo": CNPJ_ALVO,
        "certificado_id": certificado_id,
        "certificado_nome": certificado.nome,
        "passos": resultados,
    }
    print(json.dumps(saida, indent=2, ensure_ascii=False))

    with open("resultado_teste_status_habilitar_desabilitar.json", "w") as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()

"""Descobre, entre os certificados reais e ativos da conta, quais CNPJs tem
consulta de CT-e/NFC-e/CF-e(SAT) ativada — pra shortlist de candidatos pro
teste de BaixarXmlsEmLote desses tres tipos (ver
testar_documentos_fiscais_pdfs_relatorios.py).

Motivacao (22/09/2026): o Guto apontou que nem todo CNPJ baixa CT-e/NFC-e/
CF-e — os dois CNPJs de teste ate agora (CNPJ_ALVO, CNPJ_NFSE) podem
simplesmente nao ter esses tipos, o que explicaria os HTTP 404 "Nenhum
arquivo XML localizado" sem ser bug nenhum. Em vez de adivinhar, este script
usa dois endpoints ja confirmados e so-leitura do contexto Certificados:

- /api/v1/listar (active=True) — pega os certificados reais que ja estao
  habilitados na conta (nao habilita/desabilita nada, so le).
- /api/v1/status — CONFIRMADO em teste real (21/09/2026) que devolve uma
  string multi-linha, uma linha por tipo de documento, separadas por
  "\\r\\n", no formato "Status <Tipo>: <detalhe ou 'Desativado'>". Um tipo
  com o valor literal "Desativado" significa que esse certificado nem
  monitora esse tipo de documento — nao adianta tentar baixar em lote pra
  ele. Qualquer outro valor (mesmo "nenhum documento localizado na ultima
  consulta") significa que a consulta esta ativa, e vale a pena tentar.

So chama status() pra certificados com ativo=True (status so retorna dado
util nesse caso, confirmado na secao 9 do documento de registro) — nao
habilita nem desabilita nada, e um scan 100% read-only.

Rode de dentro de C:\\Apps\\Sieg_agenteteste\\sieg-agente\\src, com o .env
na raiz do projeto:
    cd C:\\Apps\\Sieg_agenteteste\\sieg-agente\\src
    python descobrir_cnpjs_com_cte_nfce_cfe.py
"""
from __future__ import annotations

import json
import os
import re
import time

from dotenv import load_dotenv

from certificados.application.use_cases.consultar_status_certificado import (
    ConsultarStatusCertificado,
)
from certificados.application.use_cases.listar_certificados import ListarCertificados
from certificados.domain.exceptions import CertificadoRequisicaoInvalidaError
from certificados.infrastructure.sieg_certificado_gateway import SiegCertificadoGateway
from shared.infrastructure.auth.sieg_jwt_provider import SiegJwtProvider
from shared.infrastructure.sieg_http_client import SiegHttpClient

# Mesma cautela de rate-limit descoberta em BaixarXmlsEmLote (ver
# testar_documentos_fiscais_pdfs_relatorios.py) — nao confirmado que
# /api/v1/status tenha o mesmo limite, mas e barato ser conservador aqui
# tambem em vez de descobrir com 28 chamadas seguidas.
PAUSA_ENTRE_STATUS_SEGUNDOS = 2

# Regex pra separar cada linha "Status <Tipo>: <resto>" da string bruta.
PADRAO_LINHA_STATUS = re.compile(r"^Status\s+([^:]+):\s*(.*)$")


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


def listar_todos_ativos(gateway: SiegCertificadoGateway) -> list:
    listar = ListarCertificados(gateway)
    todos = []
    pagina = 0
    while True:
        try:
            pagina_atual = listar.executar(active=True, pagina=pagina)
        except CertificadoRequisicaoInvalidaError:
            # CONFIRMADO em teste real (21/09/2026): paginar alem do total
            # devolve HTTP 404, nao lista vazia — fim das paginas.
            break
        if not pagina_atual:
            break
        todos.extend(pagina_atual)
        pagina += 1
    return todos


def parsear_status(status_bruto: str) -> dict[str, str]:
    """Separa a string bruta de /api/v1/status em {tipo: detalhe}."""
    resultado = {}
    for linha in status_bruto.replace("\r\n", "\n").split("\n"):
        linha = linha.strip()
        if not linha:
            continue
        m = PADRAO_LINHA_STATUS.match(linha)
        if m:
            tipo, detalhe = m.group(1).strip(), m.group(2).strip()
            resultado[tipo] = detalhe
    return resultado


def main():
    load_dotenv()
    gateway = montar_gateway()
    status_uc = ConsultarStatusCertificado(gateway)

    print("Listando certificados ativos da conta...")
    certificados = listar_todos_ativos(gateway)
    certificados = [c for c in certificados if not c.deletado]
    print(f"{len(certificados)} certificado(s) ativo(s) e nao deletado(s) encontrado(s).")

    detalhes = []
    candidatos_cte = []
    candidatos_nfce = []
    candidatos_cfe = []

    for i, cert in enumerate(certificados):
        print(f"\n[{i + 1}/{len(certificados)}] status de {cert.nome!r} (CNPJ {cert.cnpj_cpf})...")
        try:
            status_bruto = status_uc.executar(cert.id)
        except CertificadoRequisicaoInvalidaError as exc:
            print(f"   ERRO -> {exc.args}")
            detalhes.append(
                {
                    "cnpj": cert.cnpj_cpf,
                    "nome": cert.nome,
                    "id": cert.id,
                    "erro": str(exc.args),
                }
            )
            time.sleep(PAUSA_ENTRE_STATUS_SEGUNDOS)
            continue

        tipos = parsear_status(status_bruto)
        print(f"   OK -> {tipos}")
        detalhes.append({"cnpj": cert.cnpj_cpf, "nome": cert.nome, "id": cert.id, "status": tipos})

        cte = tipos.get("CT-e", "")
        nfce = tipos.get("NFC-e", "")
        cfe = tipos.get("CF-e(SAT)", "") or tipos.get("CF-e", "")

        if cte and cte != "Desativado":
            candidatos_cte.append({"cnpj": cert.cnpj_cpf, "nome": cert.nome, "detalhe": cte})
        if nfce and nfce != "Desativado":
            candidatos_nfce.append({"cnpj": cert.cnpj_cpf, "nome": cert.nome, "detalhe": nfce})
        if cfe and cfe != "Desativado":
            candidatos_cfe.append({"cnpj": cert.cnpj_cpf, "nome": cert.nome, "detalhe": cfe})

        time.sleep(PAUSA_ENTRE_STATUS_SEGUNDOS)

    print("\n\n===== RESUMO (JSON) =====")
    saida = {
        "total_certificados_ativos": len(certificados),
        "candidatos_cte": candidatos_cte,
        "candidatos_nfce": candidatos_nfce,
        "candidatos_cfe": candidatos_cfe,
        "detalhes_por_certificado": detalhes,
    }
    print(json.dumps(saida, indent=2, ensure_ascii=False))

    with open("resultado_descobrir_cnpjs_com_cte_nfce_cfe.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)

    print("\n\nCandidatos com CT-e ativado:", len(candidatos_cte))
    print("Candidatos com NFC-e ativado:", len(candidatos_nfce))
    print("Candidatos com CF-e(SAT) ativado:", len(candidatos_cfe))


if __name__ == "__main__":
    main()

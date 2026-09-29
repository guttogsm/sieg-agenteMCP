"""Testa, contra a API real, os endpoints legados de Documentos Fiscais
(BaixarXmls em lote e BaixarXml especifico), Documentos Auxiliares (Pdf:
Danfe/Dacte/Danfse) e Relatorios (relatorio/xml).

Decisao explicita do escopo (21/09/2026): o fluxo NSU fica pra depois —
aqui testamos so o que foi pedido: baixar xmls em lote e especifico, pdfs
e relatorios. Todos os paths usados aqui vieram do Swagger legado
(https://api.sieg.com/swagger/ui/index), que ja se mostrou defasado antes
(caso Certificados) — este script existe justamente pra confirmar ou
refutar essas hipoteses contra dado real, do mesmo jeito que
testar_status_habilitar_desabilitar.py fez pro contexto Certificados.

CNPJ valido de teste: 69192961000141 (mesmo usado no teste de
status/habilitar/desabilitar) — porem, segundo o Guto (21/09/2026), esse
CNPJ nao tem nenhum XML baixado no hub, entao qualquer teste de lote/
relatorio com ele tende a vir vazio (nao e erro, so nao ha dado pra
mostrar). Pra lote/relatorio, o CNPJ com dado real confirmado e
32324444000179, que TEM NFS-e — usado como CNPJ_NFSE abaixo.

Atualizado (22/09/2026): o Guto forneceu uma NFS-e real (chave de acesso +
XML) do CNPJ_NFSE, entao BaixarXml especifico, GerarDanfseViaChave e as 3
rotas ...ViaXml agora rodam de verdade (ver XML_KEY_TESTE/XML_KEY_TIPO/
XML_ARQUIVO_TESTE abaixo). GerarDanfeViaChave/GerarDacteViaChave tambem
rodam com essa mesma chave so pra confirmar que a API rejeita chave de tipo
errado (a chave e de NFS-e, nao de NF-e/CT-e) — falha esperada, nao e bug.

NOTA: chave de acesso NFS-e nacional tem 50 digitos, diferente da chave de
44 digitos de NF-e/CT-e/NFC-e (confirmado no proprio XML de exemplo).

Atualizado de novo (22/09/2026, rodada 5): o teste de lote pra NFe
(CnpjDest=CNPJ_ALVO) devolveu 5 NF-e reais — usamos a primeira delas
(NFE_KEY_TESTE/NFE_ARQUIVO_TESTE abaixo) pra testar GerarDanfeViaChave/
ViaXml com sucesso de verdade, nao so a rejeicao de tipo errado. O Guto
tambem apontou que faltava cobertura de CT-e, NFC-e e CF-e (os outros 3
tipos de TipoDocumentoFiscal, alem de NF-e/NFS-e ja cobertos) — o script
agora tambem tenta BaixarXmls em lote pra esses 3 tipos (CNPJ_ALVO e
CNPJ_NFSE), tanto pra confirmar que o download funciona pra eles quanto
pra, se achar CT-e real, alimentar um teste dinamico de GerarDacteViaXml
com sucesso de verdade (Danfe/Dacte/Danfse sao os 3 unicos endpoints de
Documentos Auxiliares confirmados no Swagger "engine" — NFC-e e CF-e nao
tem endpoint de geracao de PDF equivalente documentado, entao pra esses
dois so testamos o download em lote mesmo, sem Danfe/Dacte).

Atualizado de novo (22/09/2026, rodada 8): a rodada anterior achou CT-e
real de verdade pra CNPJ_ALVO (com o retry de 429 do SiegHttpClient ja
em producao, sem rate limiting) e o teste dinamico de GerarDacteViaXml
com ela deu certo (fecha a ultima lacuna de Documentos Auxiliares que
faltava). So faltava GerarDacteViaChave com a CHAVE dessa mesma CT-e
(o teste dinamico so usa o XML, nao isola a chave) — CTE_KEY_TESTE/
CTE_ARQUIVO_TESTE abaixo agora fazem isso, mesmo padrao ja usado pra
NF-e (NFE_KEY_TESTE/NFE_ARQUIVO_TESTE). Documentos Auxiliares ja esta
100% confirmado com essa rodada.

Atualizado de novo (22/09/2026, rodada 9): o Guto indicou um CNPJ
(07144980000145) que ele confirmou pelo hub.sieg.com ter NFC-e real
como emitente em setembro/2026 — candidato melhor que os genericos
CNPJ_ALVO/CNPJ_NFSE usados no loop 1c, que nunca acharam NFC-e/CF-e.
Novo teste 1d tenta BaixarXmls em lote (NFC-e) com esse CNPJ via
CnpjEmit (NFC-e normalmente nao tem destinatario) — ainda nao se sabe
se essas credenciais de API tem acesso a ele.

Atualizado de novo (22/09/2026, rodadas 10-11): o Guto trocou as
credenciais do .env pra uma conta que tem CNPJ_NFCE_CANDIDATO — o
teste 1d confirmou NFC-e real (fecha o mistrerio de escopo por conta).
Mas o CNPJ_ALVO antigo (69192961000141) nao esta cadastrado nessa
conta nova (os testes com ele agora voltam 404 real), entao Danfe/
Dacte ViaChave com as chaves antigas (NFE_KEY_TESTE/CTE_KEY_TESTE)
tambem passaram a falhar (a chave pertence a um documento fora da
conta) — so ViaXml continua funcionando com esses dados antigos, pois
nao depende da conta possuir o documento. O Guto entao achou, direto
no hub dessa conta nova, uma NF-e real (nNF 3361, CNPJ dest
49861189000104, emit 29759774000182/LUBRIFIL, emitida 04/09/2026) e
forneceu a chave + XML completo — candidato novo pra CNPJ_ALVO nessa
conta (NFE_KEY_CANDIDATO/NFE_ARQUIVO_CANDIDATO/CNPJ_ALVO_CANDIDATO
abaixo). Novo teste 1e tenta o lote (CnpjDest) e ViaChave/ViaXml
direto com essa chave/XML, pra confirmar se esse documento esta
mesmo dentro do escopo da conta atual (nao so visivel no hub).

Atualizado de novo (22/09/2026, rodada 13): CNPJ_ALVO_CANDIDATO
confirmou NF-e real nessa conta (lote, ViaChave e ViaXml todos com
sucesso, fixture do XML corrigida — tinha sido corrompida na
transcricao do anexo original, ver nota em NFE_ARQUIVO_CANDIDATO).
O Guto apontou que esse CNPJ nao tem CF-e, mas indicou outro
(32872159000192) que tem — unico tipo de documento fiscal (dos 5 de
TipoDocumentoFiscal) sem nenhum sucesso real confirmado na sessao
inteira. Novo teste 1f tenta o lote (CF-e, CnpjEmit) com esse
candidato, mesma janela dinamica de 60 dias ja usada no loop 1c.

Atualizado de novo (22/09/2026, rodada 14): CF-e confirmado (janela
corrigida pra dezembro/2025, ver JANELA_CFE_INICIO/FIM) — fecha os 5
de 5 tipos de documento fiscal com sucesso real na sessao. Unica
ressalva: CT-e so foi confirmado na conta ANTIGA, nunca reconfirmado
no escopo da conta atual. O Guto achou um candidato
(CNPJ_CTE_CANDIDATO=58079011000199, 2 CT-e reais, 08/09/2026) — novo
teste 1g tenta o lote (CnpjEmit) e reusa o helper _apos_lote_cte pra
testar GerarDacteViaXml automaticamente se achar XML de verdade, sem
precisar da chave (evita o risco de transcricao a mao que ja causou
um bug real na secao 25).

Rode de dentro de C:\\Apps\\Sieg_agenteteste\\sieg-agente\\src, com o .env
na raiz do projeto:
    cd C:\\Apps\\Sieg_agenteteste\\sieg-agente\\src
    python testar_documentos_fiscais_pdfs_relatorios.py
"""
from __future__ import annotations

import base64
import json
import os
import time
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from documentos_auxiliares.application.use_cases.gerar_dacte_via_chave import GerarDacteViaChave
from documentos_auxiliares.application.use_cases.gerar_dacte_via_xml import GerarDacteViaXml
from documentos_auxiliares.application.use_cases.gerar_danfe_via_chave import GerarDanfeViaChave
from documentos_auxiliares.application.use_cases.gerar_danfe_via_xml import GerarDanfeViaXml
from documentos_auxiliares.application.use_cases.gerar_danfse_via_chave import (
    GerarDanfseViaChave,
)
from documentos_auxiliares.application.use_cases.gerar_danfse_via_xml import GerarDanfseViaXml
from documentos_auxiliares.domain.exceptions import DocumentoAuxiliarRequisicaoInvalidaError
from documentos_auxiliares.infrastructure.sieg_documento_auxiliar_gateway import (
    SiegDocumentoAuxiliarGateway,
)
from documentos_fiscais.application.use_cases.baixar_xml_especifico import BaixarXmlEspecifico
from documentos_fiscais.application.use_cases.baixar_xmls_em_lote import BaixarXmlsEmLote
from documentos_fiscais.domain.exceptions import DocumentoFiscalRequisicaoInvalidaError
from documentos_fiscais.domain.value_objects import FiltroXmlsLote, TipoDocumentoFiscal
from documentos_fiscais.infrastructure.sieg_documento_fiscal_gateway import (
    SiegDocumentoFiscalGateway,
)
from relatorios.application.use_cases.gerar_relatorio_xml import GerarRelatorioXml
from relatorios.domain.exceptions import RelatorioRequisicaoInvalidaError
from relatorios.domain.value_objects import (
    SolicitacaoRelatorio,
    TipoDocumentoFiscal as TipoDocumentoFiscalRelatorio,
    TipoRelatorio,
)
from relatorios.infrastructure.sieg_relatorio_gateway import SiegRelatorioGateway
from shared.infrastructure.auth.sieg_jwt_provider import SiegJwtProvider
from shared.infrastructure.sieg_http_client import SiegHttpClient

CNPJ_ALVO = "69192961000141"

# Confirmado pelo Guto (21/09/2026): tem NFS-e de verdade no hub — melhor
# candidato pra testar BaixarXmls em lote e Relatorio, ja que CNPJ_ALVO
# nao tem nada baixado.
CNPJ_NFSE = "32324444000179"

# CONFIRMADO em teste real (22/09/2026): uma janela relativa a "hoje" (ex.:
# ultimos 60 dias) deixa de bater com o unico documento real que sabemos
# que existe assim que o tempo passa — o documento de dados_teste/ (chave
# em XML_KEY_TESTE abaixo) foi emitido em 2026-07-02. Fixamos a janela do
# teste de lote NFS-e nesse mes em vez de relativa a "hoje", ate termos um
# jeito melhor de descobrir o periodo certo automaticamente (ex.: via NSU,
# ainda adiado).
JANELA_NFSE_INICIO = date(2026, 6, 15)
JANELA_NFSE_FIM = date(2026, 7, 15)

# CNPJ candidato a NFC-e (22/09/2026) — o Guto confirmou pelo hub.sieg.com
# (cofre.sieg.com/lista-nfce?cnpjemit=07144980000145&year=2026&month=09)
# que esse CNPJ tem NFC-e reais como EMITENTE em setembro/2026. Diferente
# de CNPJ_ALVO/CNPJ_NFSE (achados por tentativa), esse veio direto do hub —
# mas ainda nao sabemos se essas credenciais de API (ClientId/SecretKey)
# tem acesso a ele, entao o teste abaixo usa CnpjEmit (nao CnpjDest — NFC-e
# normalmente nao tem destinatario, e de venda a consumidor).
CNPJ_NFCE_CANDIDATO = "07144980000145"
JANELA_NFCE_INICIO = date(2026, 9, 1)
JANELA_NFCE_FIM = date(2026, 9, 22)

# CNPJ candidato a novo CNPJ_ALVO (22/09/2026, rodada 11) — o CNPJ_ALVO
# antigo (69192961000141) nao esta cadastrado na conta nova (ver nota no
# topo do arquivo), entao precisamos de um NF-e que esteja. O Guto achou
# esse direto no hub da conta atual (nNF 3361, destinatario, 04/09/2026) e
# forneceu chave + XML completo — diferente do CNPJ_NFCE_CANDIDATO (so
# tinhamos o CNPJ), aqui ja temos o documento inteiro, entao testamos lote
# E ViaChave/ViaXml direto, sem depender de achar nada num loop antes.
CNPJ_ALVO_CANDIDATO = "49861189000104"
JANELA_NFE_CANDIDATO_INICIO = date(2026, 9, 1)
JANELA_NFE_CANDIDATO_FIM = date(2026, 9, 22)
NFE_KEY_CANDIDATO = "35260929759774000182550010000033611795383552"
NFE_ARQUIVO_CANDIDATO = os.path.join(
    os.path.dirname(__file__),
    "dados_teste",
    "nfe_exemplo_35260929759774000182550010000033611795383552.xml",
)

# CNPJ candidato a CF-e (22/09/2026, rodada 13) — CNPJ_ALVO_CANDIDATO
# (49861189000104) confirmou NF-e mas o Guto apontou que nao tem CF-e; esse
# aqui (32872159000192) ele confirmou que TEM. Unico tipo de
# TipoDocumentoFiscal sem nenhum sucesso real confirmado ate agora (nem
# endpoint de Pdf existe pra CF-e, so download em lote mesmo). CONFIRMADO
# pelo hub (screenshot, rodada 13): nota 55188, emitida 31/12/2025 — fora
# da janela dinamica de 60 dias (que so cobre ~jul-set/2026), por isso a
# janela abaixo e fixa em dezembro/2025, nao mais relativa a "hoje". Nota
# do Guto: CF-e e um modelo descontinuado (substituido por NFC-e/SAT na
# maioria dos estados), mas a SIEG mantem o historico armazenado — nao
# invalida o teste, so explica por que o documento e antigo.
CNPJ_CFE_CANDIDATO = "32872159000192"
JANELA_CFE_INICIO = date(2025, 12, 1)
JANELA_CFE_FIM = date(2025, 12, 31)

# CNPJ candidato a CT-e na conta atual (22/09/2026, rodada 14) — o CT-e
# confirmado ate agora (CTE_KEY_TESTE) e da conta ANTIGA (CNPJ_ALVO), nunca
# reconfirmado no escopo da conta atual (nota de precisao da secao 28). O
# Guto achou pelo hub esse CNPJ (58079011000199) com 2 CT-e reais como
# EMITENTE, emitidas 08/09/2026 (screenshot, filtro "CNPJ Tomador" no hub,
# mas a coluna "CNPJ Emitente" bate com esse CNPJ nas duas linhas). NAO
# usamos a chave do screenshot aqui de proposito — chave de 44 digitos e
# fragil de transcrever a mao (ja tivemos um bug real de transcricao com
# um XML nessa mesma sessao, secao 25) — o teste abaixo so usa o CNPJ e
# reaproveita o helper _apos_lote_cte (mesmo da secao 1c) que extrai o
# XML de dentro do proprio ZIP devolvido pela API e testa GerarDacteViaXml
# automaticamente, sem precisar digitar chave nenhuma.
CNPJ_CTE_CANDIDATO = "58079011000199"
JANELA_CTE_CANDIDATO_INICIO = date(2026, 9, 1)
JANELA_CTE_CANDIDATO_FIM = date(2026, 9, 22)

# CONFIRMADO em teste real (22/09/2026, rodada 6): a API devolve HTTP 429
# "Too Many Requests. Try again later." quando BaixarXmlsEmLote e chamado
# repetidas vezes sem pausa — 3 das 9 chamadas de lote desse teste vieram
# 429 em vez de um resultado de verdade (positivo ou 404 real). Adicionamos
# uma pausa entre cada chamada de lote pra nao confundir rate-limit com
# "esse CNPJ nao tem esse tipo de documento".
PAUSA_ENTRE_LOTES_SEGUNDOS = 5

# Chave de acesso real (22/09/2026), de uma NFS-e de verdade do CNPJ_NFSE
# (AEC.RIO INTELIGENCIA CONTABIL LTDA, nNFSe 1183) — fornecida pelo Guto.
# NOTA: chave de acesso NFS-e nacional tem 50 digitos, nao 44 como
# NFe/CTe/NFCe (confirmado contando o Id do proprio XML:
# "NFS33045572232324444000179000000000118326079508856719").
XML_KEY_TESTE = "33045572232324444000179000000000118326079508856719"

# Tipo do documento dono de XML_KEY_TESTE acima — precisa bater com o tipo
# real da chave, senao a API deve rejeitar (chave e TipoXml sao validados
# juntos). Essa chave e de uma NFS-e.
XML_KEY_TIPO = TipoDocumentoFiscal.NFSE

# XML real (mesmo documento da chave acima) usado pra testar as rotas
# ...ViaXml — lido do arquivo local abaixo (nao embutido no script pra nao
# inflar o diff). XML_BASE64_TESTE tem prioridade se preenchido direto.
XML_BASE64_TESTE = ""
XML_ARQUIVO_TESTE = os.path.join(
    os.path.dirname(__file__), "dados_teste", "nfse_exemplo_32324444000179.xml"
)

# Chave de acesso real de NF-e (22/09/2026, rodada 5) — extraida do ZIP que
# BaixarXmlsEmLote devolveu pro CNPJ_ALVO (F.B.Variedades Limitada-ME,
# emitida 2026-07-25). 44 digitos, como esperado pra NF-e (diferente dos 50
# da NFS-e acima). Usada pra testar GerarDanfeViaChave/ViaXml com sucesso
# de verdade, alem do teste de rejeicao de tipo errado que ja usa
# XML_KEY_TESTE (NFS-e).
NFE_KEY_TESTE = "35260716965362000157550010000005831046403276"
NFE_ARQUIVO_TESTE = os.path.join(
    os.path.dirname(__file__),
    "dados_teste",
    "nfe_exemplo_35260716965362000157550010000005831046403276.xml",
)

# Chave de acesso real de CT-e (22/09/2026, rodada 8) — extraida do ZIP que
# BaixarXmlsEmLote devolveu pro CNPJ_ALVO (chCTe do primeiro XML do lote,
# emitido 2026-08-05, mesma CT-e ja usada com sucesso em GerarDacteViaXml
# no teste dinamico da secao 1c). 44 digitos, como esperado. Usada pra
# testar GerarDacteViaChave com sucesso de verdade, alem do teste de
# rejeicao de tipo errado que ja usa XML_KEY_TESTE (NFS-e) na secao 3 —
# ultimo item de Documentos Auxiliares sem sucesso real confirmado.
CTE_KEY_TESTE = "35260867380600000101570010003340061004341871"
CTE_ARQUIVO_TESTE = os.path.join(
    os.path.dirname(__file__),
    "dados_teste",
    "cte_exemplo_35260867380600000101570010003340061004341871.xml",
)

ERROS_ESPERADOS = (
    DocumentoFiscalRequisicaoInvalidaError,
    DocumentoAuxiliarRequisicaoInvalidaError,
    RelatorioRequisicaoInvalidaError,
)


def montar_gateways():
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
    return (
        SiegDocumentoFiscalGateway(http),
        SiegDocumentoAuxiliarGateway(http),
        SiegRelatorioGateway(http),
    )


def _resultado_para_dict(resultado):
    if resultado is None:
        return None
    if hasattr(resultado, "__dataclass_fields__"):
        bruto = {k: getattr(resultado, k) for k in resultado.__dataclass_fields__}
    else:
        return resultado
    # base64 pode vir gigante — nao despeja isso inteiro no resumo/JSON.
    for campo_base64 in ("conteudo_base64", "conteudo_zip_base64"):
        if campo_base64 in bruto:
            conteudo = bruto[campo_base64] or ""
            bruto[campo_base64] = (
                f"<{len(conteudo)} chars, comeca com {conteudo[:40]!r}>" if conteudo else ""
            )
    # CONFIRMADO em teste real (22/09/2026): `status` de ResultadoDownload
    # pode ser o XML inteiro do documento (ver _salvar_xml) — igualmente
    # grande demais pra despejar no resumo/JSON/console.
    if "status" in bruto:
        status = bruto["status"] or ""
        if len(status) > 200:
            bruto["status"] = f"<{len(status)} chars, comeca com {status[:60]!r}>"
    return bruto


def _extrair_primeiro_xml_do_zip(resultado) -> str | None:
    # Pega o primeiro XML de dentro do ZIP de um ResultadoDownloadLote (ver
    # _salvar_lote) — usado pra alimentar um teste dinamico de Danfe/Dacte
    # com dado de verdade quando o lote acha CT-e/NF-e reais, sem depender
    # de um arquivo de fixture preparado na mao.
    import io
    import zipfile

    conteudo_b64 = getattr(resultado, "conteudo_zip_base64", None)
    if not conteudo_b64:
        return None
    try:
        dados_zip = base64.b64decode(conteudo_b64, validate=True)
        with zipfile.ZipFile(io.BytesIO(dados_zip)) as z:
            nomes = z.namelist()
            if not nomes:
                return None
            return z.read(nomes[0]).decode("utf-8-sig")
    except Exception:  # noqa: BLE001
        return None


def _salvar_lote(resultado, caminho: str) -> str | None:
    # CONFIRMADO em teste real (22/09/2026): BaixarXmlsEmLote devolve
    # ResultadoDownloadLote (ZIP de verdade) quando acha XMLs, ou
    # ResultadoDownload (envelope, sem conteudo) quando nao acha nada —
    # so o primeiro tem algo pra salvar.
    conteudo_b64 = getattr(resultado, "conteudo_zip_base64", None)
    if not conteudo_b64:
        return None
    return _salvar_base64(conteudo_b64, caminho)


def _salvar_xml(conteudo: str, caminho: str) -> str | None:
    # CONFIRMADO em teste real (22/09/2026): BaixarXmlEspecifico devolve o
    # XML completo (texto cru, nao base64) no campo `status` da resposta —
    # ver nota em documentos_fiscais/domain/value_objects.py. Antes disso
    # o script so imprimia esse campo, sem salvar em arquivo.
    if not conteudo:
        return None
    if not conteudo.lstrip().startswith("<?xml") and "<" not in conteudo:
        return f"Conteudo nao parece XML, nao foi salvo: {conteudo[:200]!r}"
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)
    return f"{len(conteudo)} caracteres salvos em {caminho}"


def _salvar_base64(conteudo_base64: str, caminho: str) -> str | None:
    if not conteudo_base64:
        return None
    # CONFIRMADO em teste real (22/09/2026): quando não há relatório/pdf
    # pra gerar, a API às vezes devolve uma mensagem em português nesse
    # mesmo campo (ex.: "Nenhum arquivo xml encontrado...") em vez de
    # base64 de verdade. Espaço é um sinal decisivo — base64 nunca tem
    # espaço — então tratamos isso como mensagem informativa, não erro.
    if " " in conteudo_base64:
        return f"API devolveu uma mensagem (não é base64): {conteudo_base64!r}"
    try:
        dados = base64.b64decode(conteudo_base64, validate=True)
    except Exception as exc:  # noqa: BLE001
        return f"FALHA AO DECODIFICAR BASE64: {exc} | conteúdo bruto: {conteudo_base64[:200]!r}"
    with open(caminho, "wb") as f:
        f.write(dados)
    return f"{len(dados)} bytes salvos em {caminho}"


def passo(titulo, fn, apos=None):
    print(f"\n=== {titulo} ===")
    try:
        resultado = fn()
        resumo = _resultado_para_dict(resultado)
        print(f"OK -> {resumo!r}")
        extra = None
        if apos is not None:
            try:
                extra = apos(resultado)
                if extra:
                    print(f"   {extra}")
            except Exception as exc:  # noqa: BLE001
                extra = f"(falha ao processar resultado: {exc})"
        saida = {"titulo": titulo, "ok": True, "resultado": resumo}
        if extra:
            saida["nota"] = extra
        return saida
    except ERROS_ESPERADOS as exc:
        print(f"ERRO ({type(exc).__name__}) -> {exc.args}")
        return {"titulo": titulo, "ok": False, "erro": f"{type(exc).__name__}: {exc.args}"}
    except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer coisa pro relatorio
        print(f"ERRO ({type(exc).__name__}) -> {exc}")
        return {"titulo": titulo, "ok": False, "erro": f"{type(exc).__name__}: {exc}"}


def main():
    load_dotenv()
    gw_fiscal, gw_auxiliar, gw_relatorio = montar_gateways()

    baixar_lote = BaixarXmlsEmLote(gw_fiscal)
    baixar_especifico = BaixarXmlEspecifico(gw_fiscal)
    danfe_chave = GerarDanfeViaChave(gw_auxiliar)
    dacte_chave = GerarDacteViaChave(gw_auxiliar)
    danfse_chave = GerarDanfseViaChave(gw_auxiliar)
    danfe_xml = GerarDanfeViaXml(gw_auxiliar)
    dacte_xml = GerarDacteViaXml(gw_auxiliar)
    danfse_xml = GerarDanfseViaXml(gw_auxiliar)
    gerar_relatorio = GerarRelatorioXml(gw_relatorio)

    resultados = []
    hoje = datetime.now()
    # CONFIRMADO em teste real (22/09/2026): a API rejeita com HTTP 400 se
    # o intervalo entre DataEmissaoInicio/Fim passar de 2 meses — reduzido
    # de 180 pra 60 dias por causa disso.
    inicio = hoje - timedelta(days=60)

    # Pra NFSe a API tambem exige (confirmado, mesmo teste real) que as
    # datas venham só com dia/mês/ano, sem hora/minuto/segundo — por isso
    # usamos `date` (não `datetime`) nos filtros de NFSe abaixo. `_fmt` no
    # gateway já trata isso certo (date.isoformat() não inclui hora). A
    # janela em si vem de JANELA_NFSE_INICIO/FIM (fixa, ver nota no topo
    # do arquivo) em vez de relativa a "hoje".

    # --- 1a. BaixarXmls em lote (NFS-e, CNPJ_NFSE, que tem dado real) ---
    # Roda com CnpjDest e com CnpjEmit — nao sabemos ainda qual papel o
    # CNPJ_NFSE ocupa nos documentos (tomador ou prestador do servico),
    # entao testamos os dois pra descobrir qual (se algum) traz resultado.
    filtro_nfse_dest = FiltroXmlsLote(
        xml_type=TipoDocumentoFiscal.NFSE,
        take=5,
        skip=0,
        data_emissao_inicio=JANELA_NFSE_INICIO,
        data_emissao_fim=JANELA_NFSE_FIM,
        cnpj_dest=CNPJ_NFSE,
    )
    resultados.append(
        passo(
            "BaixarXmls em lote (NFS-e, CnpjDest=CNPJ_NFSE, jun-jul/2026)",
            lambda: baixar_lote.executar(filtro_nfse_dest),
            apos=lambda r: _salvar_lote(r, "teste_lote_nfse_dest.zip"),
        )
    )
    time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)
    filtro_nfse_emit = FiltroXmlsLote(
        xml_type=TipoDocumentoFiscal.NFSE,
        take=5,
        skip=0,
        data_emissao_inicio=JANELA_NFSE_INICIO,
        data_emissao_fim=JANELA_NFSE_FIM,
        cnpj_emit=CNPJ_NFSE,
    )
    resultados.append(
        passo(
            "BaixarXmls em lote (NFS-e, CnpjEmit=CNPJ_NFSE, jun-jul/2026)",
            lambda: baixar_lote.executar(filtro_nfse_emit),
            apos=lambda r: _salvar_lote(r, "teste_lote_nfse_emit.zip"),
        )
    )
    time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

    # --- 1b. BaixarXmls em lote (NFe, CNPJ_ALVO) — CONFIRMADO em teste real
    # (22/09/2026, rodada 5) que CNPJ_ALVO TEM NF-e reais no hub (o
    # comentario antigo aqui, "esperado vazio", estava errado — o zip
    # trouxe 5 documentos de verdade). NFe aceita hora/min/seg, então aqui
    # mantemos datetime — só encurtamos o intervalo pra <= 2 meses.
    filtro_nfe = FiltroXmlsLote(
        xml_type=TipoDocumentoFiscal.NFE,
        take=5,
        skip=0,
        data_emissao_inicio=inicio,
        data_emissao_fim=hoje,
        cnpj_dest=CNPJ_ALVO,
    )
    resultados.append(
        passo(
            "BaixarXmls em lote (NFe, CnpjDest=CNPJ_ALVO)",
            lambda: baixar_lote.executar(filtro_nfe),
            apos=lambda r: _salvar_lote(r, "teste_lote_nfe_alvo.zip"),
        )
    )
    time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

    # --- 1c. BaixarXmls em lote (CT-e, NFC-e, CF-e) — cobertura pedida pelo
    # Guto (22/09/2026): alem de NF-e/NFS-e ja testados, TipoDocumentoFiscal
    # tem mais 3 valores (CTE, NFCE, CFE) ainda sem nenhum teste real. Roda
    # pros dois CNPJs conhecidos (CNPJ_ALVO e CNPJ_NFSE) com CnpjDest, so
    # pra descobrir se ha dado real neles — nao e erro se vier vazio (so
    # significa que esse CNPJ nao tem esse tipo de documento no hub). Se o
    # de CT-e achar dado real, o mesmo XML alimenta um teste dinamico de
    # GerarDacteViaXml com sucesso de verdade (ver _apos_lote_cte abaixo) —
    # NFC-e/CF-e nao tem endpoint de geracao de Pdf confirmado no Swagger
    # "engine" (so Danfe/Dacte/Danfse existem), entao pra esses dois so
    # confirmamos que o download em si funciona.
    def _apos_lote_cte(resultado, caminho_zip):
        nota = _salvar_lote(resultado, caminho_zip)
        xml_cte = _extrair_primeiro_xml_do_zip(resultado)
        if not xml_cte:
            return nota
        xml_cte_base64 = base64.b64encode(xml_cte.encode("utf-8")).decode("ascii")
        resultados.append(
            passo(
                "GerarDacteViaXml (CT-e real, extraida do lote acima)",
                lambda: dacte_xml.executar(xml_cte_base64),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_dacte_via_xml_real.pdf"),
            )
        )
        return f"{nota} | CT-e extraida e usada em GerarDacteViaXml acima"

    def _apos_lote_so_confirma_download(resultado, caminho_zip, tipo_nome):
        nota = _salvar_lote(resultado, caminho_zip)
        xml_doc = _extrair_primeiro_xml_do_zip(resultado)
        if not xml_doc:
            return nota
        return f"{nota} | {tipo_nome} real confirmada no download (sem endpoint de Pdf pra esse tipo)"

    for cnpj_nome, cnpj_valor in (("CNPJ_ALVO", CNPJ_ALVO), ("CNPJ_NFSE", CNPJ_NFSE)):
        filtro_cte = FiltroXmlsLote(
            xml_type=TipoDocumentoFiscal.CTE,
            take=5,
            skip=0,
            data_emissao_inicio=inicio,
            data_emissao_fim=hoje,
            cnpj_dest=cnpj_valor,
        )
        resultados.append(
            passo(
                f"BaixarXmls em lote (CT-e, CnpjDest={cnpj_nome})",
                lambda f=filtro_cte: baixar_lote.executar(f),
                apos=lambda r, c=cnpj_nome: _apos_lote_cte(r, f"teste_lote_cte_{c.lower()}.zip"),
            )
        )
        time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)
        filtro_nfce = FiltroXmlsLote(
            xml_type=TipoDocumentoFiscal.NFCE,
            take=5,
            skip=0,
            data_emissao_inicio=inicio,
            data_emissao_fim=hoje,
            cnpj_dest=cnpj_valor,
        )
        resultados.append(
            passo(
                f"BaixarXmls em lote (NFC-e, CnpjDest={cnpj_nome})",
                lambda f=filtro_nfce: baixar_lote.executar(f),
                apos=lambda r, c=cnpj_nome: _apos_lote_so_confirma_download(
                    r, f"teste_lote_nfce_{c.lower()}.zip", "NFC-e"
                ),
            )
        )
        time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)
        filtro_cfe = FiltroXmlsLote(
            xml_type=TipoDocumentoFiscal.CFE,
            take=5,
            skip=0,
            data_emissao_inicio=inicio,
            data_emissao_fim=hoje,
            cnpj_dest=cnpj_valor,
        )
        resultados.append(
            passo(
                f"BaixarXmls em lote (CF-e, CnpjDest={cnpj_nome})",
                lambda f=filtro_cfe: baixar_lote.executar(f),
                apos=lambda r, c=cnpj_nome: _apos_lote_so_confirma_download(
                    r, f"teste_lote_cfe_{c.lower()}.zip", "CF-e"
                ),
            )
        )
        time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

    # --- 1d. BaixarXmls em lote (NFC-e, CnpjEmit=CNPJ_NFCE_CANDIDATO) —
    # candidato indicado pelo Guto direto do hub (ver nota em
    # CNPJ_NFCE_CANDIDATO acima), nao um CNPJ generico como os do loop 1c.
    # Se der certo, encerra a busca por NFC-e/CF-e real que ate agora nao
    # achou nada nem no teste direto nem no scan de certificados.
    filtro_nfce_candidato = FiltroXmlsLote(
        xml_type=TipoDocumentoFiscal.NFCE,
        take=5,
        skip=0,
        data_emissao_inicio=JANELA_NFCE_INICIO,
        data_emissao_fim=JANELA_NFCE_FIM,
        cnpj_emit=CNPJ_NFCE_CANDIDATO,
    )
    resultados.append(
        passo(
            "BaixarXmls em lote (NFC-e, CnpjEmit=CNPJ_NFCE_CANDIDATO, set/2026)",
            lambda: baixar_lote.executar(filtro_nfce_candidato),
            apos=lambda r: _apos_lote_so_confirma_download(
                r, "teste_lote_nfce_candidato.zip", "NFC-e"
            ),
        )
    )
    time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

    # --- 1e. BaixarXmls em lote (NFe, CnpjDest=CNPJ_ALVO_CANDIDATO) — novo
    # candidato a CNPJ_ALVO nessa conta (ver nota no topo do arquivo), achado
    # direto no hub, com chave e XML completo em maos. Confirma se esse
    # documento esta mesmo dentro do escopo da conta atual (nao so visivel
    # no hub) — mesma logica das secoes 21-23 do registro de sessao.
    filtro_nfe_candidato = FiltroXmlsLote(
        xml_type=TipoDocumentoFiscal.NFE,
        take=5,
        skip=0,
        data_emissao_inicio=JANELA_NFE_CANDIDATO_INICIO,
        data_emissao_fim=JANELA_NFE_CANDIDATO_FIM,
        cnpj_dest=CNPJ_ALVO_CANDIDATO,
    )
    resultados.append(
        passo(
            "BaixarXmls em lote (NFe, CnpjDest=CNPJ_ALVO_CANDIDATO, set/2026)",
            lambda: baixar_lote.executar(filtro_nfe_candidato),
            apos=lambda r: _apos_lote_so_confirma_download(
                r, "teste_lote_nfe_candidato.zip", "NF-e"
            ),
        )
    )
    time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

    # --- 1f. BaixarXmls em lote (CF-e, CnpjEmit=CNPJ_CFE_CANDIDATO) — CF-e e
    # o unico tipo de TipoDocumentoFiscal sem sucesso real confirmado ate
    # agora. Candidato indicado pelo Guto (ver nota em CNPJ_CFE_CANDIDATO
    # acima), CnpjEmit igual NFC-e (CF-e tambem e venda a consumidor, sem
    # destinatario real). Janela fixa em dezembro/2025 (nota real confirmada
    # pelo hub, emitida 31/12/2025 — modelo descontinuado, documento antigo
    # de proposito). Sem endpoint de Pdf pra esse tipo, entao so confirma o
    # download mesmo.
    filtro_cfe_candidato = FiltroXmlsLote(
        xml_type=TipoDocumentoFiscal.CFE,
        take=5,
        skip=0,
        data_emissao_inicio=JANELA_CFE_INICIO,
        data_emissao_fim=JANELA_CFE_FIM,
        cnpj_emit=CNPJ_CFE_CANDIDATO,
    )
    resultados.append(
        passo(
            "BaixarXmls em lote (CF-e, CnpjEmit=CNPJ_CFE_CANDIDATO, dez/2025)",
            lambda: baixar_lote.executar(filtro_cfe_candidato),
            apos=lambda r: _apos_lote_so_confirma_download(
                r, "teste_lote_cfe_candidato.zip", "CF-e"
            ),
        )
    )
    time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

    # --- 1g. BaixarXmls em lote (CT-e, CnpjEmit=CNPJ_CTE_CANDIDATO) — CT-e so
    # foi confirmado ate agora na conta ANTIGA (CTE_KEY_TESTE), nunca
    # reconfirmado no escopo da conta atual. Candidato indicado pelo Guto
    # (ver nota em CNPJ_CTE_CANDIDATO acima), 08/09/2026, como EMITENTE.
    # Reusa _apos_lote_cte (mesmo helper do loop 1c) pra, se achar XML real,
    # testar GerarDacteViaXml na hora tambem — sem precisar digitar chave
    # nenhuma a mao (evita o risco de transcricao que ja causou um bug real
    # com um XML nessa sessao, ver secao 25 do registro).
    filtro_cte_candidato = FiltroXmlsLote(
        xml_type=TipoDocumentoFiscal.CTE,
        take=5,
        skip=0,
        data_emissao_inicio=JANELA_CTE_CANDIDATO_INICIO,
        data_emissao_fim=JANELA_CTE_CANDIDATO_FIM,
        cnpj_emit=CNPJ_CTE_CANDIDATO,
    )
    resultados.append(
        passo(
            "BaixarXmls em lote (CT-e, CnpjEmit=CNPJ_CTE_CANDIDATO, set/2026)",
            lambda: baixar_lote.executar(filtro_cte_candidato),
            apos=lambda r: _apos_lote_cte(r, "teste_lote_cte_candidato.zip"),
        )
    )
    time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

    # --- 2. BaixarXml especifico (so roda se XML_KEY_TESTE estiver preenchida) ---
    if XML_KEY_TESTE:
        resultados.append(
            passo(
                "BaixarXml especifico",
                lambda: baixar_especifico.executar(
                    XML_KEY_TESTE, XML_KEY_TIPO, download_event=False
                ),
                apos=lambda r: _salvar_xml(r.status, "teste_baixar_xml_especifico.xml"),
            )
        )
    else:
        print("\n=== BaixarXml especifico ===\nPULADO — preencha XML_KEY_TESTE pra rodar.")
        resultados.append({"titulo": "BaixarXml especifico", "ok": None, "erro": "pulado (sem XML_KEY_TESTE)"})

    # --- 3. Danfe/Dacte/Danfse via chave (so rodam se XML_KEY_TESTE estiver preenchida) ---
    if XML_KEY_TESTE:
        resultados.append(
            passo(
                "GerarDanfeViaChave",
                lambda: danfe_chave.executar(XML_KEY_TESTE),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_danfe.pdf"),
            )
        )
        resultados.append(
            passo(
                "GerarDacteViaChave",
                lambda: dacte_chave.executar(XML_KEY_TESTE),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_dacte.pdf"),
            )
        )
        resultados.append(
            passo(
                "GerarDanfseViaChave",
                lambda: danfse_chave.executar(XML_KEY_TESTE),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_danfse.pdf"),
            )
        )
    else:
        print(
            "\n=== GerarDanfeViaChave / GerarDacteViaChave / GerarDanfseViaChave ===\n"
            "PULADOS — preencha XML_KEY_TESTE pra rodar."
        )
        for nome in ("GerarDanfeViaChave", "GerarDacteViaChave", "GerarDanfseViaChave"):
            resultados.append({"titulo": nome, "ok": None, "erro": "pulado (sem XML_KEY_TESTE)"})

    # --- 3b. GerarDanfeViaChave/ViaXml com NF-e real (sucesso de verdade,
    # nao so a rejeicao de tipo errado do bloco 3 acima) — NFE_KEY_TESTE
    # extraida do lote da secao 1b (rodada 5, ver nota no topo do arquivo).
    if NFE_KEY_TESTE:
        resultados.append(
            passo(
                "GerarDanfeViaChave (NF-e real)",
                lambda: danfe_chave.executar(NFE_KEY_TESTE),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_danfe_real.pdf"),
            )
        )
    nfe_xml_base64 = ""
    if NFE_ARQUIVO_TESTE and os.path.exists(NFE_ARQUIVO_TESTE):
        with open(NFE_ARQUIVO_TESTE, "rb") as f:
            nfe_xml_base64 = base64.b64encode(f.read()).decode("ascii")
    if nfe_xml_base64:
        resultados.append(
            passo(
                "GerarDanfeViaXml (NF-e real)",
                lambda: danfe_xml.executar(nfe_xml_base64),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_danfe_real_via_xml.pdf"),
            )
        )

    # --- 3c. GerarDacteViaChave com CT-e real (sucesso de verdade, nao so a
    # rejeicao de tipo errado do bloco 3 acima) — CTE_KEY_TESTE extraida do
    # lote da secao 1c (rodada 8, ver nota no topo do arquivo). Ultimo item
    # de Documentos Auxiliares sem sucesso real confirmado ate essa rodada.
    if CTE_KEY_TESTE:
        resultados.append(
            passo(
                "GerarDacteViaChave (CT-e real)",
                lambda: dacte_chave.executar(CTE_KEY_TESTE),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_dacte_real.pdf"),
            )
        )

    # --- 3d. GerarDanfeViaChave/ViaXml com o NF-e candidato a novo CNPJ_ALVO
    # (rodada 11, ver nota no topo do arquivo) — testa se esse documento,
    # achado no hub da conta atual, esta mesmo dentro do escopo dela via
    # ViaChave (que exige o documento estar cadastrado na conta) e confirma
    # ViaXml funcionando independente disso (recebe o XML pronto).
    if NFE_KEY_CANDIDATO:
        resultados.append(
            passo(
                "GerarDanfeViaChave (NF-e candidato)",
                lambda: danfe_chave.executar(NFE_KEY_CANDIDATO),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_danfe_candidato_chave.pdf"),
            )
        )
    nfe_candidato_xml_base64 = ""
    if NFE_ARQUIVO_CANDIDATO and os.path.exists(NFE_ARQUIVO_CANDIDATO):
        with open(NFE_ARQUIVO_CANDIDATO, "rb") as f:
            nfe_candidato_xml_base64 = base64.b64encode(f.read()).decode("ascii")
    if nfe_candidato_xml_base64:
        resultados.append(
            passo(
                "GerarDanfeViaXml (NF-e candidato)",
                lambda: danfe_xml.executar(nfe_candidato_xml_base64),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_danfe_candidato_xml.pdf"),
            )
        )

    # --- 4. Danfe/Dacte/Danfse via XML (so rodam se houver base64 ou arquivo local) ---
    xml_base64 = XML_BASE64_TESTE
    if not xml_base64 and XML_ARQUIVO_TESTE and os.path.exists(XML_ARQUIVO_TESTE):
        with open(XML_ARQUIVO_TESTE, "rb") as f:
            xml_base64 = base64.b64encode(f.read()).decode("ascii")

    if xml_base64:
        resultados.append(
            passo(
                "GerarDanfeViaXml",
                lambda: danfe_xml.executar(xml_base64),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_danfe_via_xml.pdf"),
            )
        )
        resultados.append(
            passo(
                "GerarDacteViaXml",
                lambda: dacte_xml.executar(xml_base64),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_dacte_via_xml.pdf"),
            )
        )
        resultados.append(
            passo(
                "GerarDanfseViaXml",
                lambda: danfse_xml.executar(xml_base64),
                apos=lambda r: _salvar_base64(r.conteudo_base64, "teste_danfse_via_xml.pdf"),
            )
        )
    else:
        print(
            "\n=== GerarDanfeViaXml / GerarDacteViaXml / GerarDanfseViaXml ===\n"
            "PULADOS — preencha XML_BASE64_TESTE ou XML_ARQUIVO_TESTE pra rodar."
        )
        for nome in ("GerarDanfeViaXml", "GerarDacteViaXml", "GerarDanfseViaXml"):
            resultados.append({"titulo": nome, "ok": None, "erro": "pulado (sem XML base64)"})

    # --- 5. Relatorio (NFS-e, CNPJ_NFSE que tem dado real) ---
    # TipoRelatorio.NFSE (5) em vez de BASICO — e o tipo de relatorio
    # especifico pra NFS-e, mais provavel de bater com o dado real desse
    # CNPJ do que o relatorio basico generico (mas a numeracao de
    # TipoDownload nao esta confirmada — ver ressalva no domain/value_objects.py).
    # Roda pro mes atual e os 2 anteriores, ja que o mes atual sozinho
    # pode nao ter dado ainda (foi o que aconteceu no teste de 22/09: "Nenhum
    # arquivo xml encontrado" pro mes corrente).
    for meses_atras in (0, 1, 2):
        mes_ref = hoje.month - meses_atras
        ano_ref = hoje.year
        while mes_ref <= 0:
            mes_ref += 12
            ano_ref -= 1
        solicitacao = SolicitacaoRelatorio(
            cnpj=CNPJ_NFSE,
            tipo_relatorio=TipoRelatorio.NFSE,
            xml_type=TipoDocumentoFiscalRelatorio.NFSE,
            month=mes_ref,
            year=ano_ref,
        )
        nome_arquivo = f"teste_relatorio_{ano_ref:04d}-{mes_ref:02d}.xlsx"
        resultados.append(
            passo(
                f"GerarRelatorioXml (NFS-e, CNPJ_NFSE, {ano_ref:04d}-{mes_ref:02d})",
                lambda s=solicitacao: gerar_relatorio.executar(s),
                apos=lambda r, f=nome_arquivo: _salvar_base64(r.conteudo_base64, f),
            )
        )

    print("\n\n===== RESUMO (JSON) =====")
    saida = {
        "cnpj_alvo": CNPJ_ALVO,
        "cnpj_nfse": CNPJ_NFSE,
        "xml_key_teste_preenchida": bool(XML_KEY_TESTE),
        "xml_base64_teste_preenchida": bool(xml_base64),
        "passos": resultados,
    }
    print(json.dumps(saida, indent=2, ensure_ascii=False))

    # CONFIRMADO em teste real (22/09/2026): sem encoding explicito, o
    # Windows abre em cp1252 por padrao, que quebra com UnicodeEncodeError
    # em qualquer caractere fora dessa tabela (ex.: um � vindo de
    # bytes binarios decodificados errado num campo de erro).
    with open(
        "resultado_teste_documentos_fiscais_pdfs_relatorios.json", "w", encoding="utf-8"
    ) as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()

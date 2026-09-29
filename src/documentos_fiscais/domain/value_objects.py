"""Value Objects do contexto Documentos Fiscais.

Cobre só o download por CNPJ/data/chave (específico ou em lote), via
/api/v1/baixar-xml e /api/v1/baixar-xmls — o fluxo NSU (também real e
documentado, /api/v1/baixar-xml/nsu e afins) fica pra depois, por decisão
explícita (ver documento de registro do projeto, seção 10).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class TipoDocumentoFiscal(Enum):
    """CONFIRMADO no Swagger "engine" real (https://api.sieg.com/swagger/docs/engine,
    22/09/2026) — campo TipoXml, usado em /api/v1/baixar-xml,
    /api/v1/baixar-xmls e /api/v1/relatorios-pre-configurados, com a
    ordem NFe/CTe/NFSe/NFCe/CFe explicada nas Implementation Notes de
    /api/v1/baixar-eventos. O enum completo tem mais valores possíveis
    (6, 7, 8, 10, 99, 100) sem explicação — deixados de fora até serem
    confirmados. Ainda não testado com uma resposta de sucesso real.
    """

    NFE = 1
    CTE = 2
    NFSE = 3
    NFCE = 4
    CFE = 5


@dataclass
class ResultadoDownload:
    """Envelope devolvido pelos endpoints de Download (DownloadResponse no
    Swagger "engine": {Status, Codigo, Mensagens}).

    CORRIGIDO (22/09/2026), CONFIRMADO em teste real com BaixarXmlEspecifico
    (chave real de NFS-e): apesar do nome, o campo `status` na verdade
    contém o XML COMPLETO do documento (string XML crua, não base64, não
    um código de status) quando o download tem sucesso. A hipótese anterior
    (fluxo assíncrono via webhook/SystemUrlInfo, por não haver conteúdo no
    corpo) estava ERRADA — pelo menos pra download específico, o conteúdo
    vem direto, síncrono, no próprio `status`. Ainda não confirmado se
    BaixarXmlsEmLote (lote) segue o mesmo padrão quando encontra XMLs —
    só testamos até agora com HTTP 404 (nenhum XML localizado pro filtro).
    `codigo`/`mensagens` continuam sem uso real observado.
    """

    status: str
    codigo: str
    mensagens: list[str]


@dataclass
class ResultadoDownloadLote:
    """CONFIRMADO em teste real (22/09/2026), achado maior: quando
    /api/v1/baixar-xmls (lote) encontra XMLs que batem com o filtro, a
    resposta NÃO é o envelope IsSuccess/Data nem o DownloadResponse
    {Status, Codigo, Mensagens} documentado no Swagger — é um arquivo ZIP
    binário puro (assinatura "PK\\x03\\x04"), contendo um arquivo XML por
    documento encontrado (nomeados tipo "xml_1.xml", "xml_2.xml", ...).
    Só quando NÃO há XMLs pro filtro (ou há erro de validação) é que vem
    o envelope JSON normal — por isso BaixarXmlsEmLote pode devolver
    ResultadoDownload (envelope, sem XMLs) OU ResultadoDownloadLote (ZIP
    com XMLs de verdade), dependendo do resultado da busca.
    """

    conteudo_zip_base64: str


@dataclass
class FiltroXmlsLote:
    """Filtro pra /api/v1/baixar-xmls (download em lote). Espelha o
    modelo DownloadRequestDtoV2 do Swagger "engine" real (22/09/2026) —
    os nomes de campo aqui são os do domínio (em inglês, por já estarem
    estabelecidos no código); o gateway traduz pros nomes reais da API
    (TipoXml, BaixarEventos, TipoEvento, Valor, IntervaloValorNota).

    Nota do Swagger: o filtro de data de emissão aceita hora/minuto/segundo
    pra NFe/NFCe/CTe/CFe, mas só dia/mês/ano pra NFSe. O filtro de valor
    usa margem padrão de R$1,00 se ValueRange (IntervaloValorNota) não for
    informado.
    """

    xml_type: TipoDocumentoFiscal
    take: int = 0
    skip: int = 0
    data_emissao_inicio: datetime | date | None = None
    data_emissao_fim: datetime | date | None = None
    data_upload_inicio: datetime | date | None = None
    data_upload_fim: datetime | date | None = None
    cnpj_emit: str | None = None
    cnpj_dest: str | None = None
    cnpj_rem: str | None = None
    cnpj_tom: str | None = None
    tag: str | None = None
    download_event: bool = False
    type_event: int | None = None
    value: float | None = None
    value_range: float | None = None

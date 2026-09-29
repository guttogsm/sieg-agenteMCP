"""Value Objects do contexto Relatórios.

NÃO TESTADO ainda contra a API real com sucesso — mas o endpoint e o
schema de request agora vêm do Swagger "engine" real (22/09/2026,
https://api.sieg.com/swagger/docs/engine), não mais do Swagger legado
"ver" (que se confirmou errado — ver sieg_relatorio_gateway.py).

Nota de design: `TipoDocumentoFiscal` é redefinido aqui em vez de importado
do contexto Documentos Fiscais. Os bounded contexts não compartilham modelo
de domínio entre si (só infraestrutura compartilhada, como o HTTP client) —
mesmo os dois enums tendo os mesmos valores hoje (ambos vêm do mesmo campo
TipoXml do Swagger), cada contexto é dono do seu próprio vocabulário.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TipoDocumentoFiscal(Enum):
    """CONFIRMADO no Swagger "engine" real (campo TipoXml de
    XmlReportsRequestDto, 22/09/2026), mesmo enum já usado em
    documentos_fiscais.domain.value_objects — reproduzido aqui por
    ownership de domínio (ver nota do módulo). Não testado ainda contra
    dado real com sucesso.
    """

    NFE = 1
    CTE = 2
    NFSE = 3
    NFCE = 4
    CFE = 5


class TipoRelatorio(Enum):
    """ATENÇÃO — NÃO CONFIRMADO (22/09/2026): o Swagger "engine" real
    documenta o campo como `TipoDownload`, inteiro, enum [0, 1, 2, 3, 4, 5]
    — SEM nomear os valores. Os nomes abaixo vêm de uma fonte diferente
    (o Swagger legado "ver", campo `TypeXmlDownloadReport`, mesmo range
    mas 1-5, sem o 0) e podem não bater 1:1 com o `TipoDownload` atual:
    pode ser que a API real seja os mesmos 5 valores só que 0-indexed
    (então MONOFASICO seria 0, não 1) ou que o 0 seja uma opção nova sem
    relação com o Swagger legado. Não force esse mapeamento sem testar —
    se o relatório vier com o tipo errado, tente os valores como inteiro
    puro (0-5) em vez de confiar nesses nomes.
    """

    MONOFASICO = 1
    BASICO = 2
    DETALHAMENTO_PRODUTOS = 3
    CTE = 4
    NFSE = 5


@dataclass
class SolicitacaoRelatorio:
    """Espelha o modelo `XmlReportsRequestDto` do Swagger "engine" real:
    {"Cnpj": "string", "TipoDownload": 0, "TipoXml": 1, "Mes": 0,
    "Ano": 0}. Ver a ressalva em TipoRelatorio sobre a numeração de
    TipoDownload não estar confirmada.
    """

    cnpj: str
    tipo_relatorio: TipoRelatorio
    xml_type: TipoDocumentoFiscal
    month: int
    year: int


@dataclass
class ResultadoRelatorio:
    """CONFIRMADO no Swagger: "O retorno da api é em Base 64" — um
    arquivo Excel. Ainda não confirmado o formato exato do envelope de
    resposta (se vem string pura ou dict com outro campo) contra dado
    real.
    """

    conteudo_base64: str

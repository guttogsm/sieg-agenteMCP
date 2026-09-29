"""Implementa RelatorioGatewayPort chamando a API SIEG.

CORRIGIDO (22/09/2026): a versão anterior usava POST /api/relatorio/xml,
do Swagger legado "ver" — o mesmo padrão que se confirmou ERRADO pros
outros dois contextos (HTTP 401 "Api Key Não Informada"). O Guto
encontrou o Swagger certo: "engine" (https://api.sieg.com/swagger/docs/engine),
que documenta POST /api/v1/relatorios-pre-configurados, corpo
`XmlReportsRequestDto` = {"Cnpj": string, "TipoDownload": int (enum
0-5), "TipoXml": int, "Mes": int, "Ano": int} — nomes de campo diferentes
do Swagger legado (TipoDownload no lugar de TypeXmlDownloadReport, Mes/Ano
no lugar de Month/Year). Resposta: 200/400/404/500, sem schema de sucesso
definido no Swagger ("verificar corpo da resposta").

Ainda não testado contra dado real com sucesso.
"""
from __future__ import annotations

import requests

from shared.infrastructure.sieg_http_client import NivelAcesso, SiegApiError, SiegHttpClient

from ..domain.exceptions import RelatorioRequisicaoInvalidaError
from ..domain.value_objects import ResultadoRelatorio, SolicitacaoRelatorio


class SiegRelatorioGateway:
    def __init__(self, http: SiegHttpClient):
        self._http = http

    def gerar_relatorio_xml(self, solicitacao: SolicitacaoRelatorio) -> ResultadoRelatorio:
        payload = {
            "Cnpj": solicitacao.cnpj,
            "TipoDownload": solicitacao.tipo_relatorio.value,
            "TipoXml": solicitacao.xml_type.value,
            "Mes": solicitacao.month,
            "Ano": solicitacao.year,
        }
        dados = self._chamar(
            lambda: self._http.post(
                "/api/v1/relatorios-pre-configurados", NivelAcesso.LEITURA, payload
            )
        )
        return self._para_resultado(dados)

    # --- infraestrutura interna ---

    @staticmethod
    def _chamar(fn):
        try:
            return fn()
        except requests.HTTPError as exc:
            # CONFIRMADO em teste real (22/09/2026): esta rota vem falhando
            # com exceção genérica, sem detalhe — sinal de que o corpo pode
            # não ser o envelope IsSuccess/Data esperado (ou nem ser
            # JSON). Por isso capturamos status HTTP + corpo bruto aqui,
            # pra diagnosticar path errado (404), auth/escopo (401/403) ou
            # payload rejeitado (400).
            status = exc.response.status_code if exc.response is not None else None
            corpo = {}
            texto_bruto = ""
            if exc.response is not None:
                texto_bruto = (exc.response.text or "")[:500]
                try:
                    corpo = exc.response.json()
                except ValueError:
                    pass
            mensagens = corpo.get("Mensagens") if isinstance(corpo, dict) else None
            detalhe = "; ".join(mensagens) if mensagens else "Erro ao processar requisição."
            if status is not None:
                detalhe = f"{detalhe} (HTTP {status})"
            if texto_bruto and not mensagens:
                detalhe = f"{detalhe} | corpo bruto: {texto_bruto!r}"
            raise RelatorioRequisicaoInvalidaError([detalhe]) from exc
        except SiegApiError as exc:
            detalhe = exc.mensagem
            if exc.status_code is not None:
                detalhe = f"{detalhe} (StatusCode={exc.status_code})"
            extras = {
                k: v
                for k, v in (exc.corpo or {}).items()
                if k not in ("IsSuccess", "ErrorMessage", "StatusCode", "Data", "IsFailure")
            }
            if extras:
                detalhe = f"{detalhe} | campos extras do corpo: {extras}"
            elif exc.corpo:
                detalhe = f"{detalhe} | corpo completo: {exc.corpo}"
            raise RelatorioRequisicaoInvalidaError([detalhe]) from exc

    @staticmethod
    def _para_resultado(dados) -> ResultadoRelatorio:
        # HIPÓTESE: igual ao Pdf, a Data já desembrulhada é a própria
        # string Base64 do Excel, sem envelope adicional. Ainda não
        # confirmado contra dado real.
        if isinstance(dados, dict):
            conteudo = (
                dados.get("Arquivo")
                or dados.get("Data")
                or dados.get("Base64")
                or ""
            )
            return ResultadoRelatorio(conteudo_base64=str(conteudo))
        return ResultadoRelatorio(conteudo_base64=str(dados or ""))

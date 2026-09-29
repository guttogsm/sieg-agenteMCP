"""Implementa DocumentoAuxiliarGatewayPort chamando a API SIEG.

CORRIGIDO (22/09/2026): a versão anterior usava paths do Swagger legado
"ver" (`/api/Arquivos/Gerar...`), sem prefixo `/api/v1/` — o mesmo
padrão que se confirmou ERRADO pro contexto Documentos Fiscais (HTTP 401
"Api Key Não Informada"). O Guto encontrou o Swagger certo: "engine"
(https://api.sieg.com/swagger/docs/engine), que documenta as 6 rotas com
prefixo `/api/v1/` e nomes em camelCase minúsculo:
`/api/v1/gerarDanfeViaChave`, `/api/v1/gerarDanfeViaXml`,
`/api/v1/gerarDacteViaChave`, `/api/v1/gerarDacteViaXml`,
`/api/v1/gerarDanfseViaChave`, `/api/v1/gerarDanfseViaXml`.

CONFIRMADO nesse Swagger (não mais suposição): as 6 rotas existem de
verdade, inclusive Danfse (antes só assumida simétrica a Danfe/Dacte).
Query `xmlKey` (rotas ViaChave) e corpo `{"ArquivoXml": "<base64>"}`
(rotas ViaXml) continuam os mesmos de antes — só o path mudou. Nota do
Swagger: "O Danfe/Dacte/Danfse é retornado em bytes[] e criptografado em
Base64", sem schema de resposta definido (Inline Model vazio) — consistente
com a hipótese de que é uma string Base64 pura, sem envelope adicional.

CORRIGIDO (22/09/2026), CONFIRMADO em teste real: as 6 rotas devolviam
HTTP 403 "Acesso negado. Nível de acesso requerido: Write. Nível atual:
Read" quando chamadas com NivelAcesso.LEITURA — apesar de serem
operações de geração/leitura de documento, a API exige a chave de
ESCRITA (acesso total) pra esse grupo de rotas. Corrigido pra usar
NivelAcesso.ESCRITA nas 6 chamadas. Ainda não confirmado se o retorno em
si (conteúdo do PDF) está correto — só resolveu o 403, o próximo teste
real precisa confirmar o corpo da resposta.
"""
from __future__ import annotations

import requests

from shared.infrastructure.sieg_http_client import NivelAcesso, SiegApiError, SiegHttpClient

from ..domain.exceptions import DocumentoAuxiliarRequisicaoInvalidaError
from ..domain.value_objects import ResultadoPdf


class SiegDocumentoAuxiliarGateway:
    def __init__(self, http: SiegHttpClient):
        self._http = http

    def gerar_danfe_via_chave(self, xml_key: str) -> ResultadoPdf:
        return self._via_chave("/api/v1/gerarDanfeViaChave", xml_key)

    def gerar_danfe_via_xml(self, xml_base64: str) -> ResultadoPdf:
        return self._via_xml("/api/v1/gerarDanfeViaXml", xml_base64)

    def gerar_dacte_via_chave(self, xml_key: str) -> ResultadoPdf:
        return self._via_chave("/api/v1/gerarDacteViaChave", xml_key)

    def gerar_dacte_via_xml(self, xml_base64: str) -> ResultadoPdf:
        return self._via_xml("/api/v1/gerarDacteViaXml", xml_base64)

    def gerar_danfse_via_chave(self, xml_key: str) -> ResultadoPdf:
        return self._via_chave("/api/v1/gerarDanfseViaChave", xml_key)

    def gerar_danfse_via_xml(self, xml_base64: str) -> ResultadoPdf:
        return self._via_xml("/api/v1/gerarDanfseViaXml", xml_base64)

    # --- infraestrutura interna ---

    def _via_chave(self, path: str, xml_key: str) -> ResultadoPdf:
        # NivelAcesso.ESCRITA e nao LEITURA: CONFIRMADO em teste real
        # (22/09/2026) que a API exige a chave de acesso total aqui — ver
        # nota no docstring do modulo.
        dados = self._chamar(
            lambda: self._http.get(path, NivelAcesso.ESCRITA, params={"xmlKey": xml_key})
        )
        return self._para_resultado(dados)

    def _via_xml(self, path: str, xml_base64: str) -> ResultadoPdf:
        dados = self._chamar(
            lambda: self._http.post(
                path, NivelAcesso.ESCRITA, payload={"ArquivoXml": xml_base64}
            )
        )
        return self._para_resultado(dados)

    @staticmethod
    def _chamar(fn):
        try:
            return fn()
        except requests.HTTPError as exc:
            # CONFIRMADO em teste real (22/09/2026): o gateway irmão
            # (documentos_fiscais) vem falhando nessas rotas legadas com
            # exceção genérica, sem detalhe — sinal de que o corpo pode
            # não ser o envelope IsSuccess/Data esperado (ou nem ser
            # JSON). Por isso capturamos status HTTP + corpo bruto aqui,
            # pra diagnosticar path errado (404), auth/escopo (401/403)
            # ou payload rejeitado (400).
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
            raise DocumentoAuxiliarRequisicaoInvalidaError([detalhe]) from exc
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
            raise DocumentoAuxiliarRequisicaoInvalidaError([detalhe]) from exc

    @staticmethod
    def _para_resultado(dados) -> ResultadoPdf:
        # HIPÓTESE: o `Data` já desembrulhado pelo SiegHttpClient é a
        # própria string Base64 do PDF, sem envelope adicional (é o que o
        # Swagger sugere ao dizer que "é retornado em bytes[]... em
        # Base64", sem descrever um objeto de resposta). Ainda não
        # confirmado contra dado real — se vier um dict com outro nome de
        # campo, os fallbacks abaixo tentam os nomes mais prováveis antes
        # de desistir.
        if isinstance(dados, dict):
            conteudo = (
                dados.get("ArquivoPdf")
                or dados.get("Arquivo")
                or dados.get("Data")
                or dados.get("Base64")
                or ""
            )
            return ResultadoPdf(conteudo_base64=str(conteudo))
        return ResultadoPdf(conteudo_base64=str(dados or ""))

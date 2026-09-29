"""Implementa DocumentoFiscalGatewayPort chamando a API SIEG.

CORRIGIDO (22/09/2026): a versão anterior usava o Swagger legado
"ver" (https://api.sieg.com/swagger/docs/ver), sem prefixo /api/v1/
(ex.: /BaixarXml) — testado contra a API real e confirmado ERRADO: toda
chamada voltava HTTP 401 "Api Key Não Informada", ou seja, essas rotas
legadas nem reconhecem a autenticação usada no resto do projeto.

O Guto encontrou o Swagger certo: "engine" (https://api.sieg.com/swagger/docs/engine,
UI em https://api.sieg.com/swagger/ui/index#/), que documenta as rotas
REAIS com prefixo /api/v1/ — o mesmo padrão já confirmado funcionando em
Certificados (/api/v1/listar, /api/v1/status, etc.). Os paths e nomes de
campo abaixo vêm de lá:

- POST /api/v1/baixar-xml — body DownloadIndividualXmlRequestDto:
  {"ChaveXml": string, "TipoXml": int, "BaixarEventos": bool}. CONFIRMADO
  em teste real (22/09/2026, chave de NFS-e real): o campo `Status` da
  resposta contém o XML COMPLETO do documento (texto cru, não base64,
  não um código curto) — ver nota em ResultadoDownload no domain.

- POST /api/v1/baixar-xmls — body DownloadRequestDtoV2, com nomes de
  campo diferentes do Swagger legado: TipoXml (não XmlType), BaixarEventos
  (não Downloadevent), TipoEvento (não TypeEvent), Valor (não Value),
  IntervaloValorNota (não ValueRange). CONFIRMADO em teste real
  (22/09/2026), achado maior: quando encontra XMLs de verdade, a resposta
  é um ZIP binário puro (sem envelope JSON nenhum) — ver
  ResultadoDownloadLote no domain e a nota em SiegHttpClient._unwrap.
  Só sem match (ou erro de validação) é que vem o envelope JSON normal
  {Status, Codigo, Mensagens} documentado no Swagger.
"""
from __future__ import annotations

import base64

import requests

from shared.infrastructure.sieg_http_client import NivelAcesso, SiegApiError, SiegHttpClient

from ..domain.exceptions import DocumentoFiscalRequisicaoInvalidaError
from ..domain.value_objects import (
    FiltroXmlsLote,
    ResultadoDownload,
    ResultadoDownloadLote,
    TipoDocumentoFiscal,
)


class SiegDocumentoFiscalGateway:
    def __init__(self, http: SiegHttpClient):
        self._http = http

    def baixar_xml_especifico(
        self,
        xml_key: str,
        xml_type: TipoDocumentoFiscal,
        download_event: bool = False,
    ) -> ResultadoDownload:
        payload = {
            "ChaveXml": xml_key,
            "TipoXml": xml_type.value,
            "BaixarEventos": download_event,
        }
        dados = self._chamar(
            lambda: self._http.post("/api/v1/baixar-xml", NivelAcesso.LEITURA, payload)
        )
        return self._para_resultado(dados)

    def baixar_xmls_em_lote(
        self, filtro: FiltroXmlsLote
    ) -> ResultadoDownload | ResultadoDownloadLote:
        payload = self._filtro_para_payload(filtro)
        dados = self._chamar(
            lambda: self._http.post("/api/v1/baixar-xmls", NivelAcesso.LEITURA, payload)
        )
        if isinstance(dados, (bytes, bytearray)):
            # CONFIRMADO em teste real (22/09/2026): resposta binária
            # (ZIP) quando há XMLs de verdade pro filtro — ver
            # ResultadoDownloadLote.
            return ResultadoDownloadLote(
                conteudo_zip_base64=base64.b64encode(dados).decode("ascii")
            )
        return self._para_resultado(dados)

    # --- infraestrutura interna ---

    @staticmethod
    def _chamar(fn):
        try:
            return fn()
        except requests.HTTPError as exc:
            # CONFIRMADO em teste real (22/09/2026): rotas legadas deste
            # gateway (/BaixarXmls, ...) vêm falhando com essa exceção,
            # sem detalhe nenhum ("Erro ao processar requisição.") —
            # sinal de que o corpo não é o envelope IsSuccess/Data
            # esperado (ou nem chega a ser JSON). Por isso capturamos
            # status HTTP + corpo bruto aqui, pra diagnosticar se é path
            # errado (404), problema de auth/escopo da API key (401/403)
            # ou payload rejeitado (400) — sem isso é impossível saber.
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
            raise DocumentoFiscalRequisicaoInvalidaError([detalhe]) from exc
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
                # Sem campos extras, mas o corpo bruto existe — mostra ele
                # inteiro (inclui StatusCode/IsSuccess/etc.) pra não perder
                # nenhum detalhe quando a mensagem vem genérica.
                detalhe = f"{detalhe} | corpo completo: {exc.corpo}"
            raise DocumentoFiscalRequisicaoInvalidaError([detalhe]) from exc

    @staticmethod
    def _para_resultado(dados) -> ResultadoDownload:
        # CONFIRMADO em teste real (22/09/2026) pra baixar-xml específico:
        # {"Status": "<xml completo>", "Codigo": ..., "Mensagens": [...]}.
        # Pra baixar-xmls (lote), esse envelope só aparece quando NÃO há
        # XMLs de verdade (ver baixar_xmls_em_lote acima pro caso ZIP).
        if not isinstance(dados, dict):
            return ResultadoDownload(status=str(dados), codigo="", mensagens=[])
        return ResultadoDownload(
            status=dados.get("Status", ""),
            codigo=dados.get("Codigo", ""),
            mensagens=dados.get("Mensagens") or [],
        )

    @staticmethod
    def _fmt(valor):
        if valor is None:
            return None
        if hasattr(valor, "isoformat"):
            return valor.isoformat()
        return valor

    def _filtro_para_payload(self, f: FiltroXmlsLote) -> dict:
        # Nomes de campo confirmados no Swagger "engine" (DownloadRequestDtoV2,
        # /api/v1/baixar-xmls) — diferentes do Swagger legado "ver" que
        # usávamos antes (XmlType/Downloadevent/TypeEvent/Value/ValueRange).
        payload = {
            "TipoXml": f.xml_type.value,
            "Take": f.take,
            "Skip": f.skip,
            "DataEmissaoInicio": self._fmt(f.data_emissao_inicio),
            "DataEmissaoFim": self._fmt(f.data_emissao_fim),
            "DataUploadInicio": self._fmt(f.data_upload_inicio),
            "DataUploadFim": self._fmt(f.data_upload_fim),
            "CnpjEmit": f.cnpj_emit,
            "CnpjDest": f.cnpj_dest,
            "CnpjRem": f.cnpj_rem,
            "CnpjTom": f.cnpj_tom,
            "Tag": f.tag,
            "BaixarEventos": f.download_event,
            "TipoEvento": f.type_event,
            "Valor": f.value,
            "IntervaloValorNota": f.value_range,
        }
        return {k: v for k, v in payload.items() if v is not None}

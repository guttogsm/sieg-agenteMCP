"""Implementa CertificadoGatewayPort chamando a API SIEG (/api/v1/...).

Único lugar do contexto Certificados que conhece o formato exato dos
payloads da API — domain/ e application/ não sabem que "Nome", "CnpjCpf"
etc. existem, só conhecem a entidade Certificado.
"""
from __future__ import annotations

import requests

from shared.infrastructure.sieg_http_client import NivelAcesso, SiegApiError, SiegHttpClient

from ..domain.entities import Certificado, CertificadoResumo
from ..domain.exceptions import CertificadoRequisicaoInvalidaError
from ..domain.value_objects import (
    ConfiguracaoConsultas,
    CredenciaisCertificado,
    CredenciaisPortalMunicipal,
    JanelaHorarioConsulta,
    Prestador,
    TipoCertificado,
    TipoConsultaNfse,
)


class SiegCertificadoGateway:
    def __init__(self, http: SiegHttpClient):
        self._http = http

    def listar(self, active: bool, pagina: int = 0) -> list[CertificadoResumo]:
        itens = self._chamar(
            lambda: self._http.get(
                "/api/v1/listar",
                NivelAcesso.LEITURA,
                params={"active": active, "pagina": pagina},
            )
        )
        return [
            CertificadoResumo(
                id=item["Id"],
                nome=item["Nome"],
                cnpj_cpf=item["CnpjCpf"],
                uf_certificado=item["UfCertificado"],
                data_expira=item["DataExpira"],
                consulta_noturna=item["ConsultaNoturna"],
                ativo=item["Ativo"],
                deletado=item["Deletado"],
            )
            for item in (itens or [])
        ]

    def registrar(self, certificado: Certificado) -> Certificado:
        payload = self._para_payload(certificado)
        resposta = self._chamar(
            lambda: self._http.post("/api/v1/registrar", NivelAcesso.ESCRITA, payload)
        )
        certificado.id = resposta.get("Id")
        certificado.status = resposta.get("Status")
        return certificado

    def editar(self, certificado: Certificado) -> Certificado:
        payload = self._para_payload(certificado, incluir_id=True)
        resposta = self._chamar(
            lambda: self._http.post("/api/v1/editar", NivelAcesso.ESCRITA, payload)
        )
        certificado.status = resposta.get("Status")
        return certificado

    def habilitar(self, certificado_id: str) -> None:
        self._chamar(
            lambda: self._http.post_query(
                "/api/v1/habilitar", NivelAcesso.ESCRITA, {"id": certificado_id}
            )
        )

    def desabilitar(self, certificado_id: str) -> None:
        self._chamar(
            lambda: self._http.post_query(
                "/api/v1/desabilitar", NivelAcesso.ESCRITA, {"id": certificado_id}
            )
        )

    def deletar(self, certificado_id: str) -> None:
        # DELETE /api/v1/deletar com id via query — confirmado na v1 nova
        # (era POST .../deletar/{id} com id no path na versão anterior).
        self._chamar(
            lambda: self._http.delete(
                "/api/v1/deletar", NivelAcesso.ESCRITA, params={"id": certificado_id}
            )
        )

    def status(self, certificado_id: str) -> str:
        dados = self._chamar(
            lambda: self._http.get(
                "/api/v1/status", NivelAcesso.LEITURA, params={"id": certificado_id}
            )
        )
        # CONFIRMADO em teste real (21/09/2026): "Data" vem como string crua
        # com o status (ex.: "Ativo"/"Desativado"), NÃO como objeto
        # {"Status": "..."} como o Swagger documentado sugeria. Aceita os
        # dois formatos por segurança, mas o caminho real é a string.
        if isinstance(dados, dict):
            return dados.get("Status", "")
        return dados or ""

    # --- infraestrutura interna ---

    @staticmethod
    def _chamar(fn):
        """Centraliza o tratamento de erro -> exceção de domínio.

        Dois casos distintos, os dois confirmados como possíveis:
        - requests.HTTPError: a API respondeu um status HTTP de erro.
        - SiegApiError: a API respondeu HTTP 200, mas com IsSuccess=false
          no corpo (o SiegHttpClient já detecta isso e lança essa exceção).

        Quando IsSuccess=false, a API frequentemente não distingue "não
        encontrado" de outros erros de validação (ErrorMessage vem vazio).
        Por isso incluímos o StatusCode do próprio corpo (quando presente)
        na mensagem — é o único sinal extra disponível pra diagnosticar sem
        inventar uma distinção que a API não garante.
        """
        try:
            return fn()
        except requests.HTTPError as exc:
            corpo = {}
            if exc.response is not None:
                try:
                    corpo = exc.response.json()
                except ValueError:
                    pass
            raise CertificadoRequisicaoInvalidaError(corpo.get("Mensagens")) from exc
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
            raise CertificadoRequisicaoInvalidaError([detalhe]) from exc

    def _para_payload(self, c: Certificado, incluir_id: bool = False) -> dict:
        payload = {
            "Nome": c.nome,
            "CnpjCpf": c.cnpj_cpf,
            "IntegracaoEstadual": c.integracao_estadual,
            "CnpjIntegracaoEstadual": c.cnpj_integracao_estadual,
            "ConsultaSat": c.configuracao_consultas.sat,
            "ConsultaNfe": c.configuracao_consultas.nfe,
            "ConsultaCte": c.configuracao_consultas.cte,
            "ConsultaNfse": c.configuracao_consultas.nfse,
            "ConsultaNfce": c.configuracao_consultas.nfce,
            "BaixarCancelados": c.configuracao_consultas.baixar_cancelados,
            "ConsultaNoturna": c.configuracao_consultas.consulta_noturna,
            "ExcluirTransferenciaFiliais": c.configuracao_consultas.excluir_transferencia_filiais,
            "UfCertificado": c.uf_certificado,
            "SenhaCertificado": c.credenciais.senha,
            "TipoCertificado": c.credenciais.tipo.value,
            "Certificado": c.credenciais.arquivo_base64,
            "TipoConsultaNfse": c.tipo_consulta_nfse.value,
            "ConsultaRegiaoHorario": c.janela_horario.ativa,
            "DataInicialConsultaRegiaoHorario": c.janela_horario.data_inicial,
            "DataFinalConsultaRegiaoHorario": c.janela_horario.data_final,
            "ServicoPrestador": c.servico_prestador,
            "ServicoTomador": c.servico_tomador,
            "NomeMunicipio": c.nome_municipio,
            "InscricaoMunicipal": c.inscricao_municipal,
            "DiasRetroativos": c.dias_retroativos,
        }
        if c.credenciais_portal:
            payload["NomeUsuario"] = c.credenciais_portal.nome_usuario
            payload["SenhaUsuario"] = c.credenciais_portal.senha
        if c.lista_prestador:
            # Nomes "limpos" — o Swagger mostrou "<Cnpj>k__BackingField",
            # que tudo indica ser artefato de serialização, não o contrato
            # real. AINDA NÃO TESTADO contra a API — validar antes de usar
            # em produção com ListaPrestador não vazia.
            payload["ListaPrestador"] = [
                {"Cnpj": p.cnpj, "InscMunicipal": p.inscricao_municipal}
                for p in c.lista_prestador
            ]
        if incluir_id:
            payload["CertificadoId"] = c.id
        return payload

"""Implementa CertificadoGatewayPort chamando a API SIEG (/api/v1/...).

Único lugar do contexto Certificados que conhece o formato exato dos
payloads da API — domain/ e application/ não sabem que "Nome", "CnpjCpf"
etc. existem, só conhecem a entidade Certificado.
"""
from __future__ import annotations

import requests

from shared.infrastructure.sieg_http_client import NivelAcesso, SiegHttpClient

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
        dados = self._chamar(
            lambda: self._http.get(
                "/api/v1/listar",
                NivelAcesso.LEITURA,
                params={"active": active, "pagina": pagina},
            )
        )
        # dados pode vir como lista direta ou envelopado — ainda não
        # confirmado contra a API real; ajustar aqui quando testado.
        itens = dados if isinstance(dados, list) else dados.get("Data", [])
        return [CertificadoResumo(id=item["Id"], status=item["Status"]) for item in itens]

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
        return dados.get("Status", "")

    # --- infraestrutura interna ---

    @staticmethod
    def _chamar(fn):
        """Centraliza o tratamento de erro HTTP -> exceção de domínio."""
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

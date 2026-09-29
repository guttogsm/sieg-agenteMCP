"""Entidades do contexto Certificados."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .value_objects import (
    ConfiguracaoConsultas,
    CredenciaisCertificado,
    CredenciaisPortalMunicipal,
    JanelaHorarioConsulta,
    Prestador,
    TipoConsultaNfse,
)


class SituacaoVencimento(Enum):
    """As 3 categorias que o hub da SIEG usa pra classificar vencimento —
    CONFIRMADAS contra export real do hub (23/09/2026, ver
    sieg-agente-registro-sessao.docx, seção 36): dias_para_vencer < 0 =
    VENCIDO; 0 a 30 (inclusive) = A_VENCER; > 30 = NO_PRAZO.

    Existe como Enum (e o cálculo abaixo vive em `CertificadoResumo`, não
    em texto de prompt) de propósito: o modelo de IA já errou esse cálculo
    mais de uma vez sobre listas de só ~26 itens (item duplicado/inventado
    pra fechar um total, comparação por hora em vez de dia, total que não
    batia com a própria lista enumerada — ver addenda da seção 36). Contar
    e comparar datas é determinístico — não devia depender do modelo
    acertar aritmética em texto.
    """

    VENCIDO = "Vencido"
    A_VENCER = "À Vencer"
    NO_PRAZO = "No Prazo"


@dataclass
class Certificado:
    """Aggregate root do contexto Certificados.

    `id` é None para um certificado ainda não registrado — RegistrarCertificado
    o cria; EditarCertificado exige que já exista (`id` obrigatório nesse caso,
    validado no caso de uso, não aqui no construtor, para manter o dataclass
    simples de usar em ambos os fluxos).
    """

    nome: str
    cnpj_cpf: str
    uf_certificado: int  # código IBGE da UF — confirmado como número em teste real
    credenciais: CredenciaisCertificado
    configuracao_consultas: ConfiguracaoConsultas
    id: str | None = None
    status: str | None = None  # somente leitura, devolvido pela API
    integracao_estadual: bool = False
    cnpj_integracao_estadual: str | None = None
    janela_horario: JanelaHorarioConsulta = field(default_factory=JanelaHorarioConsulta)
    tipo_consulta_nfse: TipoConsultaNfse = TipoConsultaNfse.MUNICIPAL
    servico_prestador: bool = False
    servico_tomador: bool = False
    lista_prestador: list[Prestador] = field(default_factory=list)
    nome_municipio: str | None = None
    inscricao_municipal: str | None = None
    dias_retroativos: int = 0
    credenciais_portal: CredenciaisPortalMunicipal | None = None


@dataclass
class CertificadoResumo:
    """O que `listar` realmente devolve — CONFIRMADO em teste real (18/09/2026),
    depois de desembrulhar o envelope IsSuccess/Data do SiegHttpClient.

    Note: não existe campo "Status" nenhum. O conceito de status se
    resolve em duas flags booleanas (ativo/deletado), e uf_certificado
    vem como número (código IBGE da UF), não string.
    """

    id: str
    nome: str
    cnpj_cpf: str
    uf_certificado: int
    data_expira: str  # ISO 8601 cru; decidir depois se converte pra date
    consulta_noturna: bool
    ativo: bool
    deletado: bool

    def data_expira_date(self) -> date:
        """Só a DATA de `data_expira`, ignorando o horário.

        `data_expira` vem como data-hora (ex.: "2026-09-23T18:47:00Z"), mas
        o hub da SIEG classifica vencimento por DIA, não por horário exato
        — um certificado que vence hoje às 18:47 ainda não está vencido às
        9h do mesmo dia (CONFIRMADO contra export real do hub, seção 36).
        Comparar a data-hora completa já causou um certificado do dia ser
        contado como vencido por engano.
        """
        return date.fromisoformat(self.data_expira[:10])

    def dias_para_vencer(self, data_referencia: date) -> int:
        return (self.data_expira_date() - data_referencia).days

    def situacao_vencimento(self, data_referencia: date) -> SituacaoVencimento:
        dias = self.dias_para_vencer(data_referencia)
        if dias < 0:
            return SituacaoVencimento.VENCIDO
        if dias <= 30:
            return SituacaoVencimento.A_VENCER
        return SituacaoVencimento.NO_PRAZO


@dataclass
class ResumoVencimentoCertificados:
    """Resultado de `ResumirCertificadosPorVencimento` — já paginado e já
    classificado em código, pronto pra Claude só apresentar, sem precisar
    contar nem comparar data nenhuma por conta própria."""

    data_referencia: date
    total_com_monitoramento_ativo: int
    vencidos: list[CertificadoResumo]
    a_vencer: list[CertificadoResumo]
    no_prazo: list[CertificadoResumo]

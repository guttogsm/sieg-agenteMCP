"""Entidades do contexto Certificados."""
from __future__ import annotations

from dataclasses import dataclass, field

from .value_objects import (
    ConfiguracaoConsultas,
    CredenciaisCertificado,
    CredenciaisPortalMunicipal,
    JanelaHorarioConsulta,
    Prestador,
    TipoConsultaNfse,
)


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
    uf_certificado: str
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
    """O que `listar` realmente devolve.

    O exemplo documentado no Swagger mostra só {Id, Status} — a nota da rota
    promete "validar as informações do certificado, incluindo os tipos de
    notas ativadas", o que sugere um payload mais rico, mas isso não está
    confirmado. Por isso este é um modelo de leitura separado do aggregate
    `Certificado` (que carrega os campos completos de registrar/editar), em
    vez de forçar os dois no mesmo tipo com campos incertos.
    """

    id: str
    status: str

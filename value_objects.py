"""Value Objects do contexto Certificados.

CredenciaisCertificado e CredenciaisPortalMunicipal carregam dados
sensíveis (senha do certificado, base64 do arquivo, login do portal da
prefeitura) — isolados em objetos próprios para que a porta de Auditoria
saiba, por contrato, nunca logar o conteúdo desses dois tipos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TipoCertificado(Enum):
    PFX = "Pfx"
    P12 = "P12"


class TipoConsultaNfse(Enum):
    MUNICIPAL = "Municipal"
    NACIONAL = "Nacional"


@dataclass(frozen=True)
class CredenciaisCertificado:
    """Dados sensíveis do arquivo do certificado digital. Nunca logar."""

    senha: str
    arquivo_base64: str
    tipo: TipoCertificado


@dataclass(frozen=True)
class CredenciaisPortalMunicipal:
    """Login no portal da prefeitura para consulta de NFS-e. Nunca logar."""

    nome_usuario: str
    senha: str


@dataclass(frozen=True)
class Prestador:
    """Item de ListaPrestador.

    Atenção: o exemplo do Swagger mostrou as chaves como
    "<Cnpj>k__BackingField" / "<InscMunicipal>k__BackingField", um padrão
    típico de serialização de tipo anônimo do C#. Isso pode ser um bug de
    documentação — o mapeamento para o payload real (em
    SiegCertificadoGateway) usa os nomes "limpos" abaixo, mas isso ainda
    precisa ser validado contra a API de verdade antes de confiar cegamente.
    """

    cnpj: str
    inscricao_municipal: str


@dataclass(frozen=True)
class JanelaHorarioConsulta:
    """Janela de ConsultaRegiaoHorario — datas só fazem sentido se ativa=True."""

    ativa: bool = False
    data_inicial: str | None = None
    data_final: str | None = None


@dataclass(frozen=True)
class ConfiguracaoConsultas:
    """Quais tipos de documento este certificado está autorizado a capturar."""

    sat: bool = False
    nfe: bool = False
    cte: bool = False
    nfse: bool = False
    nfce: bool = False
    baixar_cancelados: bool = False
    consulta_noturna: bool = False
    excluir_transferencia_filiais: bool = False

"""Exceções do contexto Orquestração (Agente).

Mesmo raciocínio dos demais contextos: uma exceção enxuta, sem inventar
hierarquia que ainda não tem uso real."""


class AgenteError(Exception):
    """Erro base do contexto Orquestração."""


class LimiteIteracoesExcedidoError(AgenteError):
    """O loop de tool use passou de MAX_ITERACOES sem a Claude devolver uma
    resposta final — proteção contra loop infinito (ex.: a Claude insistindo
    em chamar a mesma ferramenta que sempre falha). Não esperado em uso
    normal; se acontecer na prática, é sinal de prompt ruim ou ferramenta
    com contrato ambíguo, vale investigar em vez de só aumentar o limite."""

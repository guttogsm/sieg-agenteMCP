"""Catálogo de ferramentas (tools) expostas à Claude — puro dado (JSON
Schema no formato que a Messages API espera), sem nenhuma lógica.

Cobre os 4 bounded contexts já implementados e testados contra a API real
(ver sieg-agente-registro-sessao.docx): Certificados, Documentos Fiscais
(download legado por filtro, não o fluxo NSU — adiado por decisão do
Guto), Documentos Auxiliares (Pdf) e Relatórios.

Deliberadamente FORA deste catálogo por enquanto: RegistrarCertificado e
EditarCertificado — o payload inclui o arquivo do certificado digital em
base64 mais a senha (CredenciaisCertificado), o que não é um fluxo natural
de chat em linguagem natural (o usuário seria obrigado a colar um base64
gigante na mensagem) e ainda não foi testado contra a API real nesta
sessão. Ficam para uma iteração futura, possivelmente com upload de
arquivo fora do chat de texto.

Cada tool que aparece em domain.politica_confirmacao.FERRAMENTAS_DESTRUTIVAS
declara o parâmetro `confirmado` — ver a política pra entender por que ele
existe e como é aplicado.
"""

_ENUM_TIPO_DOCUMENTO = ["NFE", "CTE", "NFSE", "NFCE", "CFE"]

_DESCRICAO_TIPO_DOCUMENTO = (
    "Tipo de documento fiscal. NFE=Nota Fiscal eletrônica, CTE=Conhecimento "
    "de Transporte eletrônico, NFSE=Nota Fiscal de Serviço eletrônica, "
    "NFCE=Nota Fiscal de Consumidor eletrônica, CFE=Cupom Fiscal eletrônico "
    "(modelo descontinuado, mas a SIEG mantém histórico)."
)

FERRAMENTAS: list[dict] = [
    # ---------- Certificados ----------
    {
        "name": "listar_certificados",
        "description": (
            "Lista os certificados digitais cadastrados na conta SIEG. Use "
            "para responder perguntas como 'quais certificados eu tenho', "
            "'quais estão ativos/desativados' ou para descobrir o "
            "certificado_id de um CNPJ antes de chamar outra ferramenta. "
            "Pagina de 0 em 0 — se a primeira página não tiver o que "
            "procura, tente páginas seguintes até vir vazia."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "active": {
                    "type": "boolean",
                    "description": "true para listar só certificados ativos (padrão); false lista todos, incluindo desativados/deletados.",
                    "default": True,
                },
                "pagina": {
                    "type": "integer",
                    "description": "Número da página, começando em 0.",
                    "default": 0,
                },
            },
        },
    },
    {
        "name": "resumo_certificados_vencimento",
        "description": (
            "Devolve, já paginado e já calculado em código (não pela IA), "
            "quantos certificados com monitoramento ativo estão Vencidos, "
            "À Vencer (vencem hoje ou nos próximos 30 dias) e No Prazo "
            "(mais de 30 dias) — com a lista de cada categoria. USE ESTA "
            "FERRAMENTA para qualquer pergunta sobre quantos certificados "
            "estão vencidos/a vencer/no prazo (total ou lista), em vez de "
            "chamar listar_certificados e contar/comparar datas na mão — o "
            "resultado aqui já é exato, não precisa recalcular nem "
            "conferir a soma. Cobre só certificados com monitoramento "
            "ativo (Ativo=True); não inclui os desativados, porque a API "
            "não devolve esses de forma confiável para esta conta."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "consultar_status_certificado",
        "description": (
            "Consulta o status de monitoramento de um certificado por tipo "
            "de documento (NF-e, CT-e, NFS-e, NFC-e, CF-e/SAT) — devolve, "
            "por exemplo, se a consulta de cada tipo está ativa ou "
            "'Desativado'. Só retorna dado útil se o certificado estiver "
            "ativo. Use certificado_id obtido via listar_certificados."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "certificado_id": {"type": "string", "description": "Id do certificado (vem de listar_certificados)."},
            },
            "required": ["certificado_id"],
        },
    },
    {
        "name": "habilitar_certificado",
        "description": "Habilita (reativa) um certificado desativado. Ação reversível — não exige confirmação extra.",
        "input_schema": {
            "type": "object",
            "properties": {
                "certificado_id": {"type": "string", "description": "Id do certificado (vem de listar_certificados)."},
            },
            "required": ["certificado_id"],
        },
    },
    {
        "name": "desabilitar_certificado",
        "description": (
            "Desativa um certificado — ele para de ser monitorado/consultado "
            "pela SIEG. AÇÃO DESTRUTIVA: NUNCA chame com confirmado=true na "
            "primeira vez. Primeiro explique ao usuário o que vai acontecer "
            "e pergunte se ele confirma; só chame de novo com "
            "confirmado=true depois de uma resposta afirmativa explícita "
            "dele nesta conversa."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "certificado_id": {"type": "string", "description": "Id do certificado (vem de listar_certificados)."},
                "confirmado": {
                    "type": "boolean",
                    "description": "Só true depois que o usuário confirmou explicitamente nesta conversa. Nunca assuma — pergunte primeiro.",
                    "default": False,
                },
            },
            "required": ["certificado_id"],
        },
    },
    {
        "name": "deletar_certificado",
        "description": (
            "Remove definitivamente um certificado. AÇÃO DESTRUTIVA E "
            "IRREVERSÍVEL: NUNCA chame com confirmado=true na primeira vez. "
            "Primeiro explique ao usuário que a exclusão não pode ser "
            "desfeita e pergunte se ele confirma; só chame de novo com "
            "confirmado=true depois de uma resposta afirmativa explícita "
            "dele nesta conversa."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "certificado_id": {"type": "string", "description": "Id do certificado (vem de listar_certificados)."},
                "confirmado": {
                    "type": "boolean",
                    "description": "Só true depois que o usuário confirmou explicitamente nesta conversa. Nunca assuma — pergunte primeiro.",
                    "default": False,
                },
            },
            "required": ["certificado_id"],
        },
    },
    # ---------- Documentos Fiscais ----------
    {
        "name": "baixar_xml_especifico",
        "description": (
            "Baixa o XML de UM documento fiscal específico, dada a chave de "
            "acesso. Use quando o usuário já sabe a chave exata (44 dígitos "
            "para NF-e/CT-e/NFC-e/CF-e, 50 para NFS-e nacional). A chave de "
            "acesso NÃO é o CNPJ (que tem só 14 dígitos) — se o usuário só "
            "der CNPJ + número do documento + data (sem a chave completa), "
            "NÃO tente adivinhar/montar a chave e não chame esta ferramenta "
            "com o CNPJ no lugar dela; use baixar_xmls_em_lote com "
            "cnpj_emitente e a data como filtro em vez disso. Devolve um "
            "trecho do XML mais uma referencia_documento — use essa "
            "referência (não o texto) se precisar gerar um PDF depois com "
            "gerar_danfe_via_xml/gerar_dacte_via_xml/gerar_danfse_via_xml."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chave_acesso": {"type": "string", "description": "Chave de acesso do documento (44 ou 50 dígitos) — nunca o CNPJ do emitente/destinatário."},
                "tipo_documento": {"type": "string", "enum": _ENUM_TIPO_DOCUMENTO, "description": _DESCRICAO_TIPO_DOCUMENTO},
                "baixar_eventos": {
                    "type": "boolean",
                    "description": "Se true, tenta também baixar eventos associados (cancelamento, carta de correção). Padrão false.",
                    "default": False,
                },
            },
            "required": ["chave_acesso", "tipo_documento"],
        },
    },
    {
        "name": "baixar_xmls_em_lote",
        "description": (
            "Busca e baixa vários XMLs de documentos fiscais por filtro "
            "(CNPJ, tipo, período) — inclusive quando o usuário quer UM "
            "documento específico mas só deu CNPJ + número + data em vez "
            "da chave de acesso completa (nesse caso use data_emissao_inicio "
            "= data_emissao_fim = a data informada; se vier mais de um "
            "documento no resultado, confira qual bate com o número pedido "
            "antes de gerar o PDF). Pelo menos um de cnpj_emitente/"
            "cnpj_destinatario ajuda a API a encontrar dado real — sem "
            "nenhum CNPJ a busca tende a vir vazia. IMPORTANTE: o intervalo "
            "entre data_emissao_inicio e data_emissao_fim não pode passar "
            "de 60 dias — se o usuário pedir um período maior, quebre em "
            "várias chamadas sequenciais. Se não houver XML nenhum pro "
            "filtro, a API não retorna erro, só um resultado vazio — não é "
            "bug, é sinal de que o filtro não bate com nenhum documento "
            "real (tente ampliar CNPJ/período antes de concluir que algo "
            "está quebrado). Quando encontra documentos reais, o resultado "
            "vem com uma referencia_documento por item — use-as (não o "
            "texto do XML) para gerar PDFs depois, e o ZIP completo fica "
            "disponível como anexo para o usuário baixar. PAGINAÇÃO É "
            "AUTOMÁTICA: por padrão (sem informar take) a ferramenta já "
            "busca e junta TODOS os documentos que baterem com o filtro, "
            "não só os primeiros — não existe 'take padrão baixo' pra se "
            "preocupar, e o texto de resposta sempre deixa explícito se a "
            "busca esgotou de verdade ou parou antes por algum motivo "
            "(nesse caso, nunca trate como se fosse o total)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo_documento": {"type": "string", "enum": _ENUM_TIPO_DOCUMENTO, "description": _DESCRICAO_TIPO_DOCUMENTO},
                "data_emissao_inicio": {"type": "string", "description": "Data ISO (AAAA-MM-DD). Janela máxima de 60 dias em relação a data_emissao_fim."},
                "data_emissao_fim": {"type": "string", "description": "Data ISO (AAAA-MM-DD)."},
                "cnpj_emitente": {"type": "string", "description": "CNPJ de quem emitiu o documento (só números)."},
                "cnpj_destinatario": {"type": "string", "description": "CNPJ de quem recebeu o documento (só números)."},
                "take": {
                    "type": "integer",
                    "description": (
                        "Limite OPCIONAL do total de documentos desejado (ex.: usuário pediu "
                        "'só os 5 primeiros'). Deixe de fora pra trazer TODOS os documentos do "
                        "filtro — a ferramenta pagina automaticamente por baixo dos panos "
                        "(a API real só aceita até 50 por chamada; isso é tratado sozinho, "
                        "não informe skip nem tente simular paginação manualmente)."
                    ),
                },
            },
            "required": ["tipo_documento"],
        },
    },
    # ---------- Documentos Auxiliares (Pdf) ----------
    {
        "name": "gerar_danfe_via_chave",
        "description": "Gera o PDF do DANFE (representação gráfica da NF-e) a partir da chave de acesso do documento (precisa já estar cadastrado nesta conta SIEG).",
        "input_schema": {
            "type": "object",
            "properties": {"chave_acesso": {"type": "string", "description": "Chave de acesso da NF-e (44 dígitos)."}},
            "required": ["chave_acesso"],
        },
    },
    {
        "name": "gerar_danfe_via_xml",
        "description": (
            "Gera o PDF do DANFE a partir do XML completo da NF-e — use "
            "quando o documento não está cadastrado nesta conta, mas você "
            "já tem o XML em mãos (obtido via baixar_xml_especifico ou "
            "baixar_xmls_em_lote). PREFIRA SEMPRE referencia_documento "
            "quando uma ferramenta anterior devolveu uma (ex.: "
            "'referencia_documento=xml_a1b2c3') em vez de copiar o XML/"
            "base64 manualmente — retranscrever um XML grande token por "
            "token tem risco real de corromper o conteúdo (já aconteceu "
            "nesta base de código); use xml_base64 só se você mesmo gerou "
            "esse conteúdo ou o usuário colou o XML na conversa."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "xml_base64": {"type": "string", "description": "Conteúdo do XML da NF-e, codificado em base64. Use só se não houver referencia_documento disponível."},
                "referencia_documento": {"type": "string", "description": "Referência curta de um XML já baixado nesta conversa (devolvida por baixar_xml_especifico/baixar_xmls_em_lote) — evita retranscrever o conteúdo."},
            },
        },
    },
    {
        "name": "gerar_dacte_via_chave",
        "description": "Gera o PDF do DACTE (representação gráfica do CT-e) a partir da chave de acesso do documento (precisa já estar cadastrado nesta conta SIEG).",
        "input_schema": {
            "type": "object",
            "properties": {"chave_acesso": {"type": "string", "description": "Chave de acesso do CT-e (44 dígitos)."}},
            "required": ["chave_acesso"],
        },
    },
    {
        "name": "gerar_dacte_via_xml",
        "description": (
            "Gera o PDF do DACTE a partir do XML completo do CT-e. PREFIRA "
            "referencia_documento (de uma ferramenta anterior) em vez de "
            "xml_base64 manual — ver observação de gerar_danfe_via_xml "
            "sobre risco de retranscrição."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "xml_base64": {"type": "string", "description": "Conteúdo do XML do CT-e, codificado em base64. Use só se não houver referencia_documento disponível."},
                "referencia_documento": {"type": "string", "description": "Referência curta de um XML já baixado nesta conversa — evita retranscrever o conteúdo."},
            },
        },
    },
    {
        "name": "gerar_danfce_via_chave",
        "description": (
            "Gera o PDF da DANFCE (representação gráfica da NFC-e, modelo 65) a partir da "
            "chave de acesso — busca o XML nesta conta SIEG e gera o PDF numa única chamada. "
            "Geração LOCAL (não é a API SIEG, que não tem essa rota) — mesmo motor já usado e "
            "validado na extensão Chrome de DANFE do usuário. NÃO use gerar_danfe_via_chave "
            "pra uma chave de NFC-e — o modelo (posições 21-22 da chave) tem que ser 65."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"chave_acesso": {"type": "string", "description": "Chave de acesso da NFC-e (44 dígitos, modelo 65)."}},
            "required": ["chave_acesso"],
        },
    },
    {
        "name": "gerar_danfce_via_xml",
        "description": (
            "Gera o PDF da DANFCE a partir do XML completo da NFC-e — use quando o documento "
            "não está cadastrado nesta conta, mas você já tem o XML em mãos (obtido via "
            "baixar_xml_especifico ou baixar_xmls_em_lote). Geração LOCAL, mesmo motor de "
            "gerar_danfce_via_chave. PREFIRA SEMPRE referencia_documento — ver observação de "
            "gerar_danfe_via_xml sobre risco de retranscrição."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "xml_base64": {"type": "string", "description": "Conteúdo do XML da NFC-e, codificado em base64. Use só se não houver referencia_documento disponível."},
                "referencia_documento": {"type": "string", "description": "Referência curta de um XML já baixado nesta conversa — evita retranscrever o conteúdo."},
            },
        },
    },
    {
        "name": "gerar_danfse_via_chave",
        "description": "Gera o PDF do DANFSE (representação gráfica da NFS-e nacional) a partir da chave de acesso do documento.",
        "input_schema": {
            "type": "object",
            "properties": {"chave_acesso": {"type": "string", "description": "Chave de acesso da NFS-e (50 dígitos)."}},
            "required": ["chave_acesso"],
        },
    },
    {
        "name": "gerar_danfse_via_xml",
        "description": (
            "Gera o PDF do DANFSE a partir do XML completo da NFS-e. "
            "PREFIRA referencia_documento (de uma ferramenta anterior) em "
            "vez de xml_base64 manual — ver observação de "
            "gerar_danfe_via_xml sobre risco de retranscrição."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "xml_base64": {"type": "string", "description": "Conteúdo do XML da NFS-e, codificado em base64. Use só se não houver referencia_documento disponível."},
                "referencia_documento": {"type": "string", "description": "Referência curta de um XML já baixado nesta conversa — evita retranscrever o conteúdo."},
            },
        },
    },
    {
        "name": "gerar_pdfs_em_lote",
        "description": (
            "Gera o PDF (Danfe/Dacte/Danfse/Danfce) de VÁRIOS documentos do MESMO tipo de uma "
            "vez, todos compactados num ZIP SÓ — use esta ferramenta (não gerar_danfe_via_chave/"
            "via_xml e equivalentes repetidas várias vezes) sempre que o usuário pedir PDF de "
            "mais de um documento e não disser explicitamente que quer os arquivos separados "
            "('cada um separado', 'individualmente', 'um por um' etc.) — nesse caso, aí sim "
            "chame a ferramenta de documento único uma vez por documento, como já era feito. "
            "Aceita chaves_acesso (busca o XML na API antes de gerar, uma por chave) e/ou "
            "referencias_documento (documentos já baixados nesta conversa via "
            "baixar_xml_especifico/baixar_xmls_em_lote — PREFIRA isso, evita rebaixar da API e "
            "retranscrever). Pode combinar os dois numa chamada só. Um documento que falhar "
            "(chave errada, não encontrado) não derruba os outros — o resultado avisa quais "
            "falharam e o ZIP vem só com os que deram certo. NFC-e usa geração local (mesmo "
            "motor de gerar_danfce_via_chave/via_xml) por baixo dos panos — não precisa se "
            "preocupar com isso, só passar tipo_documento=NFCE. CF-e não tem PDF (rejeitado)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo_documento": {
                    "type": "string",
                    "enum": _ENUM_TIPO_DOCUMENTO,
                    "description": "Tipo dos documentos do lote (todos precisam ser do mesmo tipo). CFE não tem PDF.",
                },
                "chaves_acesso": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Chaves de acesso dos documentos — a ferramenta busca o XML de cada uma na API antes de gerar o PDF.",
                },
                "referencias_documento": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "referencias_documento de documentos já baixados nesta conversa (baixar_xml_especifico/baixar_xmls_em_lote) — evita rebaixar da API e retranscrever XML.",
                },
            },
            "required": ["tipo_documento"],
        },
    },
    # ---------- Relatórios ----------
    {
        "name": "gerar_relatorio_xml",
        "description": (
            "Gera um relatório pré-configurado (Excel) sobre os XMLs de um "
            "CNPJ num mês/ano específico. ATENÇÃO: o mapeamento exato de "
            "tipo_relatorio contra a API ainda não está 100% confirmado — "
            "se o usuário disser que o relatório veio com o conteúdo "
            "errado (tipo errado de relatório), avise-o dessa limitação "
            "conhecida em vez de insistir tentando outros valores sem "
            "avisar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cnpj": {"type": "string", "description": "CNPJ alvo do relatório (só números)."},
                "tipo_relatorio": {
                    "type": "string",
                    "enum": ["MONOFASICO", "BASICO", "DETALHAMENTO_PRODUTOS", "CTE", "NFSE"],
                    "description": "Tipo de relatório pré-configurado.",
                },
                "tipo_documento": {"type": "string", "enum": _ENUM_TIPO_DOCUMENTO, "description": _DESCRICAO_TIPO_DOCUMENTO},
                "mes": {"type": "integer", "description": "Mês (1-12)."},
                "ano": {"type": "integer", "description": "Ano (ex.: 2026)."},
            },
            "required": ["cnpj", "tipo_relatorio", "tipo_documento", "mes", "ano"],
        },
    },
]

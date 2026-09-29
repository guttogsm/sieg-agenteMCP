# Agente SIEG

Agente conversacional (Python/Flask + Claude com tool use) pra consultar
e gerenciar certificados digitais e documentos fiscais da SIEG em
linguagem natural. Ver `sieg-agente-registro-sessao.docx` (no projeto
"Agente SIEG MVC") pro registro completo, passo a passo, de tudo que foi
testado contra a API real.

## O que está implementado

**Autenticação compartilhada** (`src/shared/infrastructure/`)
- `auth/ports.py` + `auth/sieg_jwt_provider.py`: gera e cacheia o JWT
  (24h) via `ClientId`/`SecretKey`, renovando sozinho quando necessário.
- `sieg_http_client.py`: injeta `Authorization: Bearer {jwt}` +
  `X-API-Key` em toda chamada, escolhendo a chave de leitura ou de
  escrita conforme `NivelAcesso`, com retry automático em rate limiting
  (HTTP 429).

**Certificados** (`src/certificados/`) — ciclo de vida completo: listar,
registrar, editar, habilitar, desabilitar, deletar, status. Testado
contra API real (listar/status/habilitar/desabilitar); registrar/editar/
deletar ainda não.

**Documentos Fiscais** (`src/documentos_fiscais/`) — download de XML por
chave específica ou em lote (filtro CNPJ/data/tipo), pros 5 tipos
(NF-e/CT-e/NFS-e/NFC-e/CF-e). Testado contra API real, 5/5 tipos
confirmados.

**Documentos Auxiliares** (`src/documentos_auxiliares/`) — geração de PDF
(Danfe/Dacte/Danfse), via chave ou via XML. Testado contra API real, 6/6
rotas confirmadas.

**Relatórios** (`src/relatorios/`) — relatório pré-configurado em Excel
por CNPJ/mês/ano. Testado contra API real; mapeamento exato de
`TipoRelatorio` ainda não 100% confirmado (ver ressalva no código).

**Orquestração/Agente** (`src/orquestracao/`) — o agente conversacional
propriamente dito, que recebe mensagem em linguagem natural e decide
sozinho quais dos casos de uso acima chamar, via tool use da Claude. Ver
seção própria abaixo.

`src/composicao_exemplo.py` mostra a injeção de dependência manual (só
Certificados) — `src/app_factory.py` é a versão completa, usada pelo
Flask (`src/app.py`).

## Como rodar o exemplo

```bash
cd src
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r ../requirements.txt
cp ../.env.example ../.env
# preencha o .env com credenciais reais, depois:
export $(cat ../.env | xargs)  # ou use python-dotenv no seu entrypoint
python composicao_exemplo.py
```

## Contexto Orquestração (Agente) — chat em linguagem natural

**MVP fechado** (22/09/2026): o agente conversacional de verdade, que
recebe uma mensagem em português e decide sozinho quais ferramentas
chamar via tool use da Claude, está implementado em `src/orquestracao/` e
exposto por um controller Flask fino (`src/app.py`).

Cobre as 14 operações já confirmadas contra a API real nos outros 4
bounded contexts: listar/consultar status/habilitar/desabilitar/deletar
certificado, baixar XML específico/em lote, gerar Danfe/Dacte/Danfse (via
chave e via XML) e gerar relatório. Fora do escopo por enquanto:
Registrar/EditarCertificado (payload sensível demais pra um fluxo de
chat) e o fluxo NSU (adiado desde o início do projeto).

Duas decisões de design que valem a pena conhecer antes de mexer no
código:

- **Confirmação de ações destrutivas** é aplicada em código
  (`orquestracao/domain/politica_confirmacao.py` +
  `ExecutorFerramentasSieg.executar`), não só via instrução no prompt —
  `desabilitar_certificado`/`deletar_certificado` só executam de verdade
  com `confirmado=true`, e isso nunca é assumido, é checado.
- **XML nunca é retranscrito pela Claude**: quando um download encontra
  documento real, o resultado inclui uma `referencia_documento` curta
  (cacheada em memória por sessão) que as ferramentas `...via_xml`
  aceitam no lugar do XML/base64 cru — evita a classe de bug de
  corrupção de XML já vista nesta base de código (ver seção 25 do
  registro de sessão do projeto).

### Como rodar o chat

```bash
cd src
pip install -r ../requirements.txt
# no .env da raiz, preencha as credenciais SIEG (já devem estar lá) +
# a chave do provedor de IA escolhido (ver seção "Provedor de IA" abaixo)
python app.py
```

### Provedor de IA: Claude ou Gemini

O agente não fala com nenhum provedor de IA diretamente — tudo passa por
`ClienteIAPort` (`orquestracao/application/ports.py`), então trocar de
provedor é só escrever outro adapter, sem tocar em domain/application/nem
nos outros bounded contexts. Hoje existem dois:

- `ClaudeClienteIA` (`orquestracao/infrastructure/claude_cliente_ia.py`) —
  via Claude Messages API. **Único testado ponta a ponta com chave real
  nesta sessão** (24/09 pendente — ver limitações abaixo).
- `GeminiClienteIA` (`orquestracao/infrastructure/gemini_cliente_ia.py`) —
  via Gemini `generate_content` (a API síncrona/stateless do Google, não a
  Interactions API mais nova — essa é stateful via `previous_interaction_id`
  e teria contrato incompatível com `ClienteIAPort` como está hoje).
  Alternativa pra quem não tem acesso pago à API da Anthropic. Modelo
  padrão: `gemini-3.8-flash` (GA, confirmado com suporte a function
  calling — ver ressalva de teste abaixo).

Escolha via `SIEG_AGENTE_PROVEDOR_IA=claude` (padrão) ou `=gemini` no
`.env`, preenchendo só `ANTHROPIC_API_KEY` ou `GEMINI_API_KEY` conforme o
escolhido (ver `.env.example`).

**O que foi validado do adapter Gemini nesta sessão, e o que não foi**:
toda a lógica de conversão (schema de ferramenta, mapeamento de papel de
mensagem pra `Content`/`Part`, parsing de resposta com texto e com
`function_call`) foi testada localmente com dublês, sem rede — e as
assinaturas reais do pacote `google-genai==2.25.0` foram inspecionadas
diretamente (não assumidas da documentação). O que **não** foi testado: uma
chamada real à API do Gemini — o sandbox usado pra montar isso não tem
saída de rede liberada pra `generativelanguage.googleapis.com`. Rode o chat
localmente com uma `GEMINI_API_KEY` de verdade antes de considerar esse
provedor definitivo, do mesmo jeito que o Claude também depende disso.

Abra http://localhost:5000 pra um chat de teste simples (HTML/JS puro,
sem build), ou chame a API direto:

```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"mensagem": "quais certificados eu tenho ativos?"}'
```

A resposta inclui `sessao_id` (reenvie no próximo `POST /chat` pra manter
o contexto da conversa) e `arquivos` (links de download quando a
ferramenta gerou PDF/ZIP/Excel).

**Limitações conhecidas do MVP, deliberadas (YAGNI, não esquecimento)**:
sessão de conversa em memória do processo Flask (reinicia, perde o
histórico — trocar por Redis/banco só quando isso for um problema real);
sem autenticação de usuário no chat; sem testes automatizados formais
ainda — o loop do agente (`ResponderMensagem`) e o despachante de
ferramentas (`ExecutorFerramentasSieg`) foram validados com dublês/stubs
(confirmação bloqueando ação destrutiva, cache de referência de XML,
loop de tool use, tratamento de erro), mas o fluxo ponta a ponta com a
Claude de verdade ainda depende de uma `ANTHROPIC_API_KEY` válida — rode
o chat localmente com a sua chave antes de considerar isso definitivo.

## O que NÃO está confirmado ainda (marcado em comentário no código)

- Formato exato da resposta de `listar` (o Swagger só documenta
  `{Id, Status}`, mas a nota promete mais campos).
- Nomes reais das chaves de `ListaPrestador` (`Cnpj`/`InscMunicipal`
  vs. o `<Cnpj>k__BackingField` que apareceu no Swagger).
- Formato do corpo de erro em 400/500 nas rotas que não documentam
  `Mensagens` explicitamente.

Nenhum desses bloqueia o uso do fluxo principal — só vale testar contra
a API real antes de confiar no mapeamento em `SiegCertificadoGateway`.

## Próximos passos (fora do escopo do MVP atual)

- Fluxo NSU de Documentos Fiscais (adiado por decisão explícita desde o
  início do projeto).
- `RegistrarCertificado`/`EditarCertificado` como ferramentas do agente
  (hoje só existem como casos de uso testáveis por script — o payload
  inclui o arquivo do certificado em base64 + senha, não é um fluxo
  natural de chat de texto).
- Persistência de sessão de conversa (hoje é em memória do processo
  Flask — ver ressalva na seção do agente).
- Testes automatizados (hoje a validação é contra a API real via scripts
  manuais + testes com stubs do loop do agente — nenhum teste automatizado
  formal ainda, tipo pytest).
- Autenticação de usuário no chat.

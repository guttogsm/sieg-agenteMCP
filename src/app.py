"""Controller Flask fino — só tradução HTTP <-> caso de uso, nenhuma regra
de negócio aqui (ela mora inteira em orquestracao/application e nos
outros bounded contexts). Rode com:

    cd src
    python app.py

e acesse http://localhost:5000 (chat de teste simples, ver static/index.html)
ou chame POST /chat diretamente (ver README.md).

Sessão em memória, de propósito simplificado pro MVP: cada sessao_id vira
uma entrada num dict do processo Flask. Reinicia o processo, perde a
conversa. Suficiente pra validar o fluxo ponta a ponta contra a API real;
trocar por um armazenamento persistente (Redis, banco) quando isso virar
um problema de verdade (mais de um processo Flask, ou precisar sobreviver
a um restart) — não antes, YAGNI.
"""
from __future__ import annotations

import os
import threading
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()  # lê o .env na raiz do projeto antes de app_factory ler os.environ

from app_factory import montar_responder_mensagem  # noqa: E402 (depois do load_dotenv de propósito)

DIRETORIO_BASE = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_ARQUIVOS_GERADOS = os.path.join(DIRETORIO_BASE, "arquivos_gerados")
DIRETORIO_LOGS = os.path.join(DIRETORIO_BASE, "logs")

app = Flask(__name__, static_folder="static", static_url_path="")

_responder_mensagem = montar_responder_mensagem(DIRETORIO_ARQUIVOS_GERADOS, DIRETORIO_LOGS)

# sessao_id -> list[MensagemConversa] — ver ressalva de sessão em memória no docstring acima.
_sessoes: dict[str, list] = {}
_lock_sessoes = threading.Lock()


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/saude")
def saude():
    return jsonify({"status": "ok"})


@app.post("/chat")
def chat():
    corpo = request.get_json(silent=True) or {}
    mensagem = (corpo.get("mensagem") or "").strip()
    if not mensagem:
        return jsonify({"erro": "Campo 'mensagem' é obrigatório."}), 400

    sessao_id = corpo.get("sessao_id") or str(uuid.uuid4())

    with _lock_sessoes:
        historico = _sessoes.get(sessao_id, [])

    try:
        resposta = _responder_mensagem.executar(sessao_id, mensagem, historico)
    except Exception as exc:  # noqa: BLE001 — controller fino, só traduz pra HTTP 500
        return jsonify({"erro": f"Erro inesperado no agente: {exc}"}), 500

    with _lock_sessoes:
        _sessoes[sessao_id] = resposta.historico

    return jsonify(
        {
            "sessao_id": sessao_id,
            "resposta": resposta.texto,
            "arquivos": [
                {"nome": a.nome_arquivo, "url": f"/arquivos/{sessao_id}/{a.nome_arquivo}"}
                for a in resposta.arquivos_gerados
            ],
        }
    )


@app.get("/arquivos/<sessao_id>/<nome_arquivo>")
def baixar_arquivo(sessao_id: str, nome_arquivo: str):
    diretorio = os.path.join(DIRETORIO_ARQUIVOS_GERADOS, sessao_id)
    return send_from_directory(diretorio, nome_arquivo, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)

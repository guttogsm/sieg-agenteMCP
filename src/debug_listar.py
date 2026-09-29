"""Script temporário só para inspecionar o formato real da resposta de
/api/v1/listar. Apague depois de usar — não faz parte da arquitetura."""
import json
import os

from dotenv import load_dotenv

from shared.infrastructure.auth.sieg_jwt_provider import SiegJwtProvider
from shared.infrastructure.sieg_http_client import NivelAcesso, SiegHttpClient

load_dotenv(dotenv_path=r"..\.env")

base_url = os.environ["SIEG_BASE_URL"]
token_provider = SiegJwtProvider(base_url, os.environ["SIEG_CLIENT_ID"], os.environ["SIEG_SECRET_KEY"])
http = SiegHttpClient(
    base_url,
    token_provider,
    os.environ["SIEG_API_KEY_LEITURA"],
    os.environ["SIEG_API_KEY_ESCRITA"],
)

dados = http.get("/api/v1/listar", NivelAcesso.LEITURA, params={"active": True, "pagina": 0})
print(json.dumps(dados, indent=2, ensure_ascii=False))

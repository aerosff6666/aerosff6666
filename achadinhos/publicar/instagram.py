"""Passo 11: Instagram Reels via Graph API (conta Profissional).

A API busca o vídeo numa URL pública, então o arquivo precisa estar hospedado
(bucket S3/R2, Cloudflare, Google Cloud Storage...) em url_publica_base.
"""

import os
import time
import urllib.parse
from pathlib import Path

from achadinhos.publicar import ErroPublicacao, requisitar


def publicar(video: Path, legenda: str, url_publica_base: str, nome_publico: str) -> str:
    usuario = os.environ.get("IG_USER_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    base = os.environ.get("IG_GRAPH_URL", "https://graph.facebook.com/v23.0").rstrip("/")
    if not (usuario and token):
        raise ErroPublicacao("IG_USER_ID e IG_ACCESS_TOKEN precisam estar no .env")
    if not url_publica_base:
        raise ErroPublicacao("defina publicacao.url_publica_base no config.toml e suba o vídeo lá")

    url_video = f"{url_publica_base.rstrip('/')}/{nome_publico}"
    campos = urllib.parse.urlencode({
        "media_type": "REELS",
        "video_url": url_video,
        "caption": legenda[:2200],
        "share_to_feed": "true",
        "access_token": token,
    }).encode()
    container = requisitar("POST", f"{base}/{usuario}/media", dados=campos)["id"]

    for _ in range(60):
        estado = requisitar("GET", f"{base}/{container}?fields=status_code&access_token={token}")
        if estado.get("status_code") == "FINISHED":
            break
        if estado.get("status_code") == "ERROR":
            raise ErroPublicacao(f"Instagram não processou o vídeo ({url_video})")
        time.sleep(5)
    else:
        raise ErroPublicacao("Instagram demorou demais para processar o vídeo")

    publicado = requisitar("POST", f"{base}/{usuario}/media_publish", dados=urllib.parse.urlencode({
        "creation_id": container,
        "access_token": token,
    }).encode())
    return publicado["id"]

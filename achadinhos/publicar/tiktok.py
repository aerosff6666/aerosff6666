"""Passo 10: TikTok via Content Posting API.

Modo "rascunho" (escopo video.upload): o vídeo cai na caixa de entrada do app do
TikTok. Lá você confere, adiciona o link do produto (carrinho do TikTok Shop) e
posta. A API não anexa produto do TikTok Shop ao vídeo, por isso este é o padrão.

Modo "direto" (escopo video.publish): posta na hora. Enquanto o seu app não for
auditado pelo TikTok, os posts ficam privados (SELF_ONLY).
"""

import os
from pathlib import Path

from achadinhos.publicar import ErroPublicacao, requisitar

API = "https://open.tiktokapis.com/v2"


def publicar(video: Path, legenda: str, modo: str) -> str:
    token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not token:
        raise ErroPublicacao("TIKTOK_ACCESS_TOKEN não definido no .env")
    auth = {"Authorization": f"Bearer {token}"}
    tamanho = video.stat().st_size
    if tamanho > 64 * 1024 * 1024:
        raise ErroPublicacao("vídeo acima de 64 MB; envio em partes não implementado")
    origem = {"source": "FILE_UPLOAD", "video_size": tamanho, "chunk_size": tamanho, "total_chunk_count": 1}

    if modo == "rascunho":
        resposta = requisitar("POST", f"{API}/post/publish/inbox/video/init/",
                              json_corpo={"source_info": origem}, cabecalhos=auth)
    elif modo == "direto":
        info = {"title": legenda[:2200], "privacy_level": "PUBLIC_TO_EVERYONE", "is_aigc": True}
        resposta = requisitar("POST", f"{API}/post/publish/video/init/",
                              json_corpo={"post_info": info, "source_info": origem}, cabecalhos=auth)
    else:
        raise ErroPublicacao(f"tiktok_modo inválido: {modo}")

    if resposta.get("error", {}).get("code", "ok") != "ok":
        raise ErroPublicacao(f"TikTok: {resposta['error']}")
    dados = resposta["data"]
    requisitar("PUT", dados["upload_url"], dados=video.read_bytes(), cabecalhos={
        "Content-Type": "video/mp4",
        "Content-Length": str(tamanho),
        "Content-Range": f"bytes 0-{tamanho - 1}/{tamanho}",
    })
    return dados["publish_id"]

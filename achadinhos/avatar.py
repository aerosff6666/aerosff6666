"""Vídeo com o personagem falando (avatar com IA via HeyGen, opcional e pago).

Crie o avatar de cada personagem no HeyGen a partir da descrição em
personagens.toml (campo visual), copie o avatar_id e o voice_id para lá e
coloque HEYGEN_API_KEY no .env. Sem isso, o vídeo usa fotos do produto +
texto na tela + voz do personagem.
"""

import os
import time
import urllib.request
from pathlib import Path

from achadinhos.publicar import ErroPublicacao, requisitar

API = "https://api.heygen.com"


def disponivel(personagem: dict | None) -> bool:
    return bool(
        personagem
        and os.environ.get("HEYGEN_API_KEY")
        and personagem.get("heygen_avatar_id")
        and personagem.get("heygen_voice_id")
    )


def gerar_clipe(texto: str, personagem: dict, destino: Path, cfg: dict) -> Path:
    auth = {"X-Api-Key": os.environ["HEYGEN_API_KEY"]}
    corpo = {
        "video_inputs": [{
            "character": {"type": "avatar", "avatar_id": personagem["heygen_avatar_id"], "avatar_style": "normal"},
            "voice": {"type": "text", "input_text": texto, "voice_id": personagem["heygen_voice_id"]},
        }],
        "dimension": {"width": cfg["video"]["largura"], "height": cfg["video"]["altura"]},
    }
    video_id = requisitar("POST", f"{API}/v2/video/generate", json_corpo=corpo, cabecalhos=auth)["data"]["video_id"]
    for _ in range(120):
        estado = requisitar("GET", f"{API}/v1/video_status.get?video_id={video_id}", cabecalhos=auth)["data"]
        if estado["status"] == "completed":
            urllib.request.urlretrieve(estado["video_url"], destino)
            return destino
        if estado["status"] == "failed":
            raise ErroPublicacao(f"HeyGen não gerou o vídeo: {estado.get('error')}")
        time.sleep(10)
    raise ErroPublicacao("HeyGen demorou demais para gerar o vídeo")

"""Passo 12: envia o achadinho para o grupo/canal do Telegram (Bot API, gratuita)."""

import os
import uuid
from pathlib import Path

from achadinhos.publicar import ErroPublicacao, requisitar


def _multipart(campos: dict[str, str], arquivo: Path, campo_arquivo: str) -> tuple[bytes, str]:
    fronteira = uuid.uuid4().hex
    partes = []
    for nome, valor in campos.items():
        partes.append(
            f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n'.encode()
        )
    partes.append(
        f'--{fronteira}\r\nContent-Disposition: form-data; name="{campo_arquivo}"; '
        f'filename="{arquivo.name}"\r\nContent-Type: video/mp4\r\n\r\n'.encode()
    )
    partes.append(arquivo.read_bytes())
    partes.append(f"\r\n--{fronteira}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={fronteira}"


def publicar(video: Path, legenda: str, url_afiliado: str) -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        raise ErroPublicacao("TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID precisam estar no .env")
    texto = f"{legenda}\n\n🛒 {url_afiliado}"
    if len(texto) > 1024:
        texto = texto[: 1024 - len(url_afiliado) - 6] + f"…\n\n🛒 {url_afiliado}"
    corpo, tipo = _multipart({"chat_id": chat, "caption": texto}, video, "video")
    resposta = requisitar("POST", f"https://api.telegram.org/bot{token}/sendVideo",
                          dados=corpo, cabecalhos={"Content-Type": tipo})
    if not resposta.get("ok"):
        raise ErroPublicacao(f"Telegram: {resposta}")
    return str(resposta["result"]["message_id"])

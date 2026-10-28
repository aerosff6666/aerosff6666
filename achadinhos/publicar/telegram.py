"""Passo 12: envia o achadinho para o grupo/canal do Telegram (Bot API, gratuita)."""

import os
import uuid
from pathlib import Path

from achadinhos.publicar import ErroPublicacao, requisitar


def _credenciais() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        raise ErroPublicacao("TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID precisam estar no .env")
    return token, chat


def chamar(metodo: str, espera_http: int = 120, **campos) -> dict:
    token, _ = _credenciais()
    resposta = requisitar("POST", f"https://api.telegram.org/bot{token}/{metodo}",
                          json_corpo=campos, timeout=espera_http)
    if not resposta.get("ok"):
        raise ErroPublicacao(f"Telegram {metodo}: {resposta}")
    return resposta["result"]


def enviar_mensagem(texto: str, chat_id: str | None = None, **extra) -> dict:
    return chamar("sendMessage", chat_id=chat_id or _credenciais()[1], text=texto[:4096], **extra)


def enviar_foto(foto_url: str, legenda: str, chat_id: str | None = None) -> dict:
    return chamar("sendPhoto", chat_id=chat_id or _credenciais()[1], photo=foto_url, caption=legenda[:1024])


def enviar_enquete(pergunta: str, opcoes: list[str], chat_id: str | None = None) -> dict:
    return chamar("sendPoll", chat_id=chat_id or _credenciais()[1], question=pergunta[:300],
                  options=[{"text": o[:100]} for o in opcoes[:10]], is_anonymous=True)


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


def publicar(video: Path, legenda: str, links: list[tuple[str, str]]) -> str:
    """Vídeo + legenda + links (título, url). A legenda é cortada para caber no limite de 1024."""
    token, chat = _credenciais()
    rodape = "\n\n" + "\n".join(f"🛒 {titulo}: {url}" if len(links) > 1 else f"🛒 {url}" for titulo, url in links)
    texto = legenda[: max(0, 1024 - len(rodape) - 1)] + rodape
    corpo, tipo = _multipart({"chat_id": chat, "caption": texto}, video, "video")
    resposta = requisitar("POST", f"https://api.telegram.org/bot{token}/sendVideo",
                          dados=corpo, cabecalhos={"Content-Type": tipo})
    if not resposta.get("ok"):
        raise ErroPublicacao(f"Telegram: {resposta}")
    return str(resposta["result"]["message_id"])

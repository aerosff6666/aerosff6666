"""Passo 8: monta o vídeo vertical (9:16) com ffmpeg.

Cada cena do roteiro vira um trecho: foto do produto sobre um fundo desfocado
da própria foto, com o texto da cena na parte de baixo. A narração, se houver,
define a duração total.
"""

import hashlib
import shutil
import subprocess
import textwrap
import urllib.request
from pathlib import Path


def _ffmpeg(*args: str) -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg não encontrado. Instale: https://ffmpeg.org/download.html")
    resultado = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {resultado.stderr.strip()}")


def duracao_audio(caminho: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(caminho)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(saida.stdout.strip())


def baixar_imagem(origem: str, cache: Path) -> Path:
    """Aceita caminho local ou URL; URLs são baixadas uma vez para a pasta de cache."""
    if not origem.startswith(("http://", "https://")):
        return Path(origem)
    nome = hashlib.sha1(origem.encode()).hexdigest()[:16] + ".img"
    destino = cache / nome
    if not destino.exists():
        pedido = urllib.request.Request(origem, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(pedido, timeout=30) as r:
            destino.write_bytes(r.read())
    return destino


def _cena(imagem: Path | None, texto: str, duracao: float, saida: Path, cfg: dict) -> None:
    v = cfg["video"]
    w, h, fps = v["largura"], v["altura"], v["fps"]
    arquivo_texto = saida.with_suffix(".txt")
    arquivo_texto.write_text("\n".join(textwrap.wrap(texto, 18)), encoding="utf-8")
    texto_filtro = (
        f"drawtext=fontfile='{v['fonte']}':textfile='{arquivo_texto}':expansion=none:fontcolor=white:fontsize=72"
        f":line_spacing=12:box=1:boxcolor=black@0.55:boxborderw=28"
        f":x=(w-text_w)/2:y=h*0.72"
    )
    if imagem is None:
        entrada = ["-f", "lavfi", "-i", f"color=c=0xFF2D55:s={w}x{h}:r={fps}:d={duracao}"]
        filtro = f"[0:v]{texto_filtro},format=yuv420p[v]"
    else:
        entrada = ["-loop", "1", "-framerate", str(fps), "-t", f"{duracao}", "-i", str(imagem)]
        filtro = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=24:2[fundo];"
            f"[0:v]scale={w - 80}:{int(h * 0.62)}:force_original_aspect_ratio=decrease[frente];"
            f"[fundo][frente]overlay=(W-w)/2:H*0.08,{texto_filtro},format=yuv420p[v]"
        )
    _ffmpeg(
        *entrada,
        "-filter_complex", filtro,
        "-map", "[v]",
        "-t", f"{duracao}",
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        str(saida),
    )


def montar_video(pacote: dict, imagens: list[str], audio: Path | None, pasta: Path, cfg: dict, cache: Path) -> Path:
    cenas = pacote["roteiro"]["cenas"]
    arquivos_img = [baixar_imagem(i, cache) for i in imagens]
    total = len(cenas) * cfg["video"]["segundos_por_cena"]
    if audio:
        total = max(total, duracao_audio(audio) + 0.5)
    por_cena = round(total / len(cenas), 3)

    trechos = []
    for i, cena in enumerate(cenas):
        trecho = pasta / f"cena_{i:02d}.mp4"
        imagem = arquivos_img[i % len(arquivos_img)] if arquivos_img else None
        _cena(imagem, cena["texto_tela"], por_cena, trecho, cfg)
        trechos.append(trecho)

    lista = pasta / "cenas.txt"
    lista.write_text("".join(f"file '{t.name}'\n" for t in trechos), encoding="utf-8")
    video = pasta / "video.mp4"
    audio_args = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    _ffmpeg(
        "-f", "concat", "-safe", "0", "-i", str(lista),
        *audio_args,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-t", f"{total}",
        "-movflags", "+faststart",
        str(video),
    )
    for t in trechos:
        t.unlink()
        t.with_suffix(".txt").unlink()
    lista.unlink()
    return video

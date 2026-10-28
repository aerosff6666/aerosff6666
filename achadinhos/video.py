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


def _drawtext(cfg: dict, arquivo: Path, tamanho: int, y: str, caixa: str) -> str:
    return (
        f"drawtext=fontfile='{cfg['video']['fonte']}':textfile='{arquivo}':expansion=none"
        f":fontcolor=white:fontsize={tamanho}:line_spacing=12:box=1:boxcolor={caixa}"
        f":boxborderw={tamanho // 3}:x=(w-text_w)/2:y={y}"
    )


def _selo(personagem: dict | None, pasta: Path, cfg: dict) -> str:
    """Faixa no topo com o nome do personagem e o aviso de que é virtual."""
    if not personagem:
        return ""
    arquivo = pasta / f"selo_{personagem['id']}.txt"
    arquivo.write_text(f"{personagem['nome']} - personagem virtual (IA)", encoding="utf-8")
    return "," + _drawtext(cfg, arquivo, 40, "h*0.025", f"{personagem['cor']}@0.85")


def _cena(imagem: Path | None, texto: str, duracao: float, saida: Path, cfg: dict,
          personagem: dict | None = None) -> None:
    v = cfg["video"]
    w, h, fps = v["largura"], v["altura"], v["fps"]
    arquivo_texto = saida.with_suffix(".txt")
    arquivo_texto.write_text("\n".join(textwrap.wrap(texto, 18)), encoding="utf-8")
    if imagem is None:
        caixa = "black@0.35"  # o fundo já tem a cor do personagem
    else:
        caixa = f"{personagem['cor']}@0.80" if personagem else "black@0.55"
    textos = _drawtext(cfg, arquivo_texto, 72, "h*0.72", caixa) + _selo(personagem, saida.parent, cfg)
    if imagem is None:
        cor = personagem["cor"] if personagem else "0xFF2D55"
        entrada = ["-f", "lavfi", "-i", f"color=c={cor}:s={w}x{h}:r={fps}:d={duracao}"]
        filtro = f"[0:v]{textos},format=yuv420p[v]"
    else:
        entrada = ["-loop", "1", "-framerate", str(fps), "-t", f"{duracao}", "-i", str(imagem)]
        filtro = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=24:2[fundo];"
            f"[0:v]scale={w - 80}:{int(h * 0.58)}:force_original_aspect_ratio=decrease[frente];"
            f"[fundo][frente]overlay=(W-w)/2:H*0.10,{textos},format=yuv420p[v]"
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


def montar_video(pacote: dict, imagens: list[str], audio: Path | None, pasta: Path, cfg: dict, cache: Path,
                 personagens_por_id: dict[str, dict] | None = None) -> Path:
    personagens_por_id = personagens_por_id or {}
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
        _cena(imagem, cena["texto_tela"], por_cena, trecho, cfg, personagens_por_id.get(cena.get("personagem")))
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
    for arquivo in [*trechos, *(t.with_suffix(".txt") for t in trechos), lista, *pasta.glob("selo_*.txt")]:
        arquivo.unlink()
    return video


def video_com_avatar(clipe_avatar: Path, imagens: list[str], pasta: Path, cfg: dict, cache: Path,
                     personagem: dict) -> Path:
    """Clipe do avatar em tela cheia, com a foto do produto em destaque e o selo de IA."""
    v = cfg["video"]
    w, h = v["largura"], v["altura"]
    selo = _selo(personagem, pasta, cfg)
    entradas = ["-i", str(clipe_avatar)]
    filtro = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[base]"
    atual = "base"
    if imagens:
        entradas += ["-loop", "1", "-i", str(baixar_imagem(imagens[0], cache))]
        filtro += (f";[1:v]scale={int(w * 0.55)}:-2[produto];"
                   f"[base][produto]overlay=W-w-40:H*0.12:shortest=1[comproduto]")
        atual = "comproduto"
    filtro += f";[{atual}]null{selo},format=yuv420p[v]"
    video = pasta / "video.mp4"
    _ffmpeg(*entradas, "-filter_complex", filtro, "-map", "[v]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac",
            "-movflags", "+faststart", str(video))
    for arquivo in pasta.glob("selo_*.txt"):
        arquivo.unlink()
    return video

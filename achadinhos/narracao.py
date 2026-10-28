"""Passo 7: narração do vídeo, com a voz de cada personagem."""

import asyncio
import subprocess
from pathlib import Path

from achadinhos import personagens


def gerar_narracao(cenas: list[dict], destino: Path, cfg: dict) -> Path | None:
    """Devolve o caminho do áudio, ou None para vídeo sem voz."""
    modo = cfg["narracao"]["modo"]
    if modo == "nenhuma":
        return None
    if modo == "arquivo":
        # Você grava a própria voz e salva no lugar indicado antes de gerar o vídeo.
        if destino.exists():
            return destino
        print(f"  ! Grave a narração e salve em {destino}; o vídeo sai sem voz por enquanto.")
        return None
    if modo == "edge-tts":
        try:
            import edge_tts
        except ImportError:
            raise SystemExit("Modo edge-tts exige: pip install edge-tts")
        # Agrupa cenas seguidas do mesmo personagem para cada trecho ter uma voz só.
        trechos: list[tuple[str, str]] = []
        for cena in cenas:
            p = personagens.por_id(cfg, cena.get("personagem"))
            voz = p["voz"] if p else cfg["narracao"]["voz"]
            if trechos and trechos[-1][0] == voz:
                trechos[-1] = (voz, trechos[-1][1] + " " + cena["narracao"])
            else:
                trechos.append((voz, cena["narracao"]))
        arquivos = []
        for i, (voz, texto) in enumerate(trechos):
            arquivo = destino.with_name(f"narracao_{i:02d}.mp3")
            asyncio.run(edge_tts.Communicate(texto, voz).save(str(arquivo)))
            arquivos.append(arquivo)
        if len(arquivos) == 1:
            arquivos[0].rename(destino)
        else:
            lista = destino.with_name("narracao.txt")
            lista.write_text("".join(f"file '{a.name}'\n" for a in arquivos), encoding="utf-8")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                            "-i", str(lista), "-c", "copy", str(destino)], check=True)
            for a in [*arquivos, lista]:
                a.unlink()
        return destino
    raise SystemExit(f"Modo de narração desconhecido: {modo}")

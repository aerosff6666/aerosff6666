"""Passo 7: narração do vídeo."""

import asyncio
from pathlib import Path


def gerar_narracao(texto: str, destino: Path, cfg: dict) -> Path | None:
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
        asyncio.run(edge_tts.Communicate(texto, cfg["narracao"]["voz"]).save(str(destino)))
        return destino
    raise SystemExit(f"Modo de narração desconhecido: {modo}")

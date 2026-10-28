"""Carrega config.toml e o arquivo .env."""

import os
import tomllib
from pathlib import Path


def carregar_env(caminho: Path) -> None:
    """Lê um .env simples (CHAVE=valor) sem sobrescrever variáveis já definidas."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valor = valor.strip().strip('"').strip("'")
        if valor:
            os.environ.setdefault(chave.strip(), valor)


def carregar_config(caminho: str | Path = "config.toml") -> dict:
    caminho = Path(caminho)
    carregar_env(caminho.parent / ".env")
    with caminho.open("rb") as f:
        cfg = tomllib.load(f)
    cfg["_raiz"] = str(caminho.parent.resolve())
    arquivo_personagens = caminho.parent / "personagens.toml"
    if arquivo_personagens.exists():
        with arquivo_personagens.open("rb") as f:
            extra = tomllib.load(f)
        cfg["personagens"] = extra.get("personagens", [])
        cfg["duelo"] = extra.get("duelo", {})
    cfg.setdefault("personagens", [])
    cfg.setdefault("duelo", {})
    return cfg


def pasta(cfg: dict, nome: str) -> Path:
    p = Path(cfg["_raiz"]) / nome
    p.mkdir(parents=True, exist_ok=True)
    return p

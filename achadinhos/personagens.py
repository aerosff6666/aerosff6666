"""Escolhe qual personagem apresenta cada produto."""

import unicodedata


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sem_acento.lower().strip()


def por_id(cfg: dict, personagem_id: str | None) -> dict | None:
    return next((p for p in cfg["personagens"] if p["id"] == personagem_id), None)


def escolher(produto: dict, cfg: dict) -> dict | None:
    """Pela categoria do produto; categorias sem dono são divididas entre os personagens."""
    personagens = cfg["personagens"]
    if not personagens:
        return None
    categoria = normalizar(produto.get("categoria", ""))
    for p in personagens:
        if categoria in {normalizar(c) for c in p["categorias"]}:
            return p
    return personagens[produto.get("id", 0) % len(personagens)]

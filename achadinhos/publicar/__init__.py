"""Passos 10, 11 e 12: publicação no TikTok, Instagram e grupo do Telegram."""

import json
import urllib.error
import urllib.request


class ErroPublicacao(Exception):
    pass


def requisitar(metodo: str, url: str, *, dados: bytes | None = None, json_corpo: dict | None = None,
               cabecalhos: dict | None = None, timeout: int = 120) -> dict:
    cabecalhos = dict(cabecalhos or {})
    if json_corpo is not None:
        dados = json.dumps(json_corpo).encode()
        cabecalhos.setdefault("Content-Type", "application/json; charset=UTF-8")
    pedido = urllib.request.Request(url, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            corpo = r.read()
    except urllib.error.HTTPError as e:
        raise ErroPublicacao(f"{metodo} {url.split('?')[0]} -> HTTP {e.code}: {e.read()[:500]!r}") from e
    return json.loads(corpo) if corpo.strip() else {}

"""Passos 4, 5 e 6: raio-x do produto, roteiro do vídeo e legenda."""

import re

import anthropic

from achadinhos.ia import IA, RecusaIA

ESQUEMA_PACOTE = {
    "type": "object",
    "properties": {
        "raio_x": {
            "type": "object",
            "properties": {
                "publico": {"type": "string"},
                "dor": {"type": "string"},
                "beneficios": {"type": "array", "items": {"type": "string"}},
                "objecoes": {"type": "array", "items": {"type": "string"}},
                "angulo": {"type": "string"},
            },
            "required": ["publico", "dor", "beneficios", "objecoes", "angulo"],
            "additionalProperties": False,
        },
        "roteiro": {
            "type": "object",
            "properties": {
                "gancho": {"type": "string"},
                "cenas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "texto_tela": {"type": "string"},
                            "narracao": {"type": "string"},
                        },
                        "required": ["texto_tela", "narracao"],
                        "additionalProperties": False,
                    },
                },
                "cta": {"type": "string"},
            },
            "required": ["gancho", "cenas", "cta"],
            "additionalProperties": False,
        },
        "legenda": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["raio_x", "roteiro", "legenda", "hashtags"],
    "additionalProperties": False,
}

SISTEMA = """Você é roteirista de vídeos curtos de achadinhos para TikTok e Instagram Reels no Brasil.
Nicho: {nome}. Público: {publico}. Tom: {tom}. Idioma: {idioma}.

Regras:
- Gancho que prende nos 2 primeiros segundos, ligado a uma dor real do público.
- 3 a 5 cenas. texto_tela com no máximo 7 palavras; narracao com uma ou duas frases curtas.
- Fale só do que os dados do produto sustentam. Não invente números, prazos, garantias,
  resultados de saúde ou comparações com marcas. Nada de "melhor do mundo" ou "100% garantido".
- CTA leva ao carrinho/link do vídeo, sem pressão falsa ("só hoje", "últimas unidades") a menos
  que os dados digam isso.
- legenda: até 300 caracteres, sem hashtags (elas vão em hashtags), sem o aviso de publicidade.
- hashtags: 3 a 5, sem o símbolo #, misturando nicho e produto."""


def _formatar_preco(preco: float) -> str:
    return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pacote_modelo(produto: dict, cfg: dict) -> dict:
    """Pacote de conteúdo sem IA, montado a partir de modelos de texto."""
    titulo = produto["titulo"]
    curto = " ".join(titulo.split()[:4])
    preco = _formatar_preco(produto["preco"])
    return {
        "raio_x": {
            "publico": cfg["nicho"]["publico"],
            "dor": f"perder tempo ou dinheiro sem um {curto.lower()}",
            "beneficios": ["praticidade no dia a dia", f"custa {preco}"],
            "objecoes": ["será que funciona mesmo?", "vale o preço?"],
            "angulo": "achadinho prático e barato",
        },
        "roteiro": {
            "gancho": "Olha esse achadinho!",
            "cenas": [
                {"texto_tela": "Olha esse achadinho!", "narracao": f"Olha esse achadinho que eu achei: {titulo}."},
                {"texto_tela": curto, "narracao": "Ele resolve aquele problema chato do dia a dia."},
                {"texto_tela": f"Só {preco}", "narracao": f"E custa só {preco}."},
                {"texto_tela": "Link no carrinho", "narracao": "O link tá aqui no carrinho do vídeo."},
            ],
            "cta": "Link no carrinho",
        },
        "legenda": f"{titulo} por {preco}. Achadinho que facilita a rotina!",
        "hashtags": ["achadinhos", "tiktokshop", re.sub(r"\W", "", produto.get("categoria") or "casa")],
    }


def gerar_pacote(produto: dict, cfg: dict, ia: IA) -> tuple[dict, str]:
    """Devolve (pacote, origem), onde origem é 'ia' ou 'modelo'."""
    if not ia.ativa:
        return pacote_modelo(produto, cfg), "modelo"
    sistema = SISTEMA.format(**cfg["nicho"])
    pedido = (
        "Faça o raio-x deste produto (público, dor, benefícios, objeções, melhor ângulo de venda) "
        "e depois o roteiro, a legenda e as hashtags.\n\n"
        f"Produto: {produto['titulo']}\n"
        f"Preço: {_formatar_preco(produto['preco'])}\n"
        f"Categoria: {produto.get('categoria') or 'não informada'}\n"
        f"Vendas na loja: {produto['vendas']}\n"
        f"Nota média: {produto['nota']}"
    )
    try:
        return ia.gerar_json(sistema, pedido, ESQUEMA_PACOTE), "ia"
    except (RecusaIA, anthropic.APIError, ValueError) as e:
        print(f"  ! IA indisponível para '{produto['titulo']}' ({e}); usando modelo de texto.")
        return pacote_modelo(produto, cfg), "modelo"


def montar_legenda(pacote: dict, cfg: dict) -> str:
    hashtags = " ".join("#" + h.lstrip("#").replace(" ", "") for h in pacote["hashtags"])
    return f"{pacote['legenda']}\n\n{cfg['divulgacao']['aviso']}\n{hashtags}".strip()

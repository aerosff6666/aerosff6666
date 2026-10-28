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
                "formato": {"type": "string"},
            },
            "required": ["publico", "dor", "beneficios", "objecoes", "angulo", "formato"],
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
                            "personagem": {"type": "string"},
                        },
                        "required": ["texto_tela", "narracao", "personagem"],
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

REGRAS = """Regras que você nunca quebra:
- Os personagens são virtuais e sabem disso. Eles APRESENTAM o produto pelo que ele é
  (ficha, preço, avaliações e vendas da loja). Nunca dizem que usaram, testaram ou que
  "mudou a vida"; nada de antes/depois nem depoimento.
- Fale só do que os dados sustentam. Não invente números, prazos, garantias, efeitos de
  saúde ou estética, nem compare com marcas. Nada de "melhor do mundo" ou "100% garantido".
- Sem urgência falsa ("só hoje", "últimas unidades") a menos que os dados digam isso.
- texto_tela com no máximo 7 palavras; narracao com uma ou duas frases curtas.
- legenda: até 300 caracteres, sem hashtags e sem aviso de publicidade (são adicionados depois).
- hashtags: 3 a 5, sem o símbolo #, misturando nicho e produto."""

SISTEMA_PERSONAGEM = """Você escreve vídeos curtos de achadinhos para TikTok e Reels no Brasil (idioma {idioma}).
O vídeo é apresentado por {nome}, personagem virtual. Público: {publico}.

Personalidade de {nome}:{personalidade}
Abertura típica: "{bordao_abertura}". Fechamento típico: "{bordao_fechamento}".
Formatos que funcionam com {nome}: {formatos}.

Escreva como {nome} fala: o gancho prende nos 2 primeiros segundos e precisa parar a rolagem
(surpresa, pergunta, contraste de preço, situação do dia a dia). O vídeo mostra um produto só.
3 a 5 cenas, todas com
personagem = "{id}". Escolha o formato e registre em raio_x.formato.

""" + REGRAS

SISTEMA_DUELO = """Você escreve vídeos curtos de achadinhos para TikTok e Reels no Brasil (idioma {idioma}).
Formato DUELO entre dois personagens virtuais, cada um defendendo um produto:

{fichas}

Estrutura: cena de gancho (personagem do primeiro produto), 2 cenas de cada personagem
defendendo o seu produto, com provocação bem-humorada entre eles, e a cena final chamando o
público a votar nos comentários. Use o id do personagem no campo personagem de cada cena.
raio_x descreve os dois produtos juntos; raio_x.formato = "duelo".
Gancho sugerido: "{gancho}". Chamada final: "{chamada}".

""" + REGRAS


def formatar_preco(preco: float) -> str:
    return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


CONECTIVOS = {"de", "da", "do", "das", "dos", "para", "com", "e", "em", "a", "o", "p/", "c/"}


def titulo_curto(titulo: str, palavras: int = 4) -> str:
    """Primeiras palavras do título, sem terminar em conectivo ("Mini processador elétrico")."""
    partes = titulo.split()[:palavras]
    while len(partes) > 1 and partes[-1].lower() in CONECTIVOS:
        partes.pop()
    return " ".join(partes)


def _dados_produto(produto: dict) -> str:
    return (
        f"Produto: {produto['titulo']}\n"
        f"Preço: {formatar_preco(produto['preco'])}\n"
        f"Categoria: {produto.get('categoria') or 'não informada'}\n"
        f"Vendas na loja: {produto.get('vendas', 0)}\n"
        f"Nota média: {produto.get('nota', 0)}"
    )


def _hashtags(produto: dict, personagem: dict | None) -> list[str]:
    tags = ["achadinhos", "tiktokshop", re.sub(r"\W", "", produto.get("categoria") or "casa")]
    if personagem:
        tags.append(re.sub(r"\W", "", personagem["nome"]).lower())
    return tags


def pacote_modelo(produto: dict, cfg: dict, personagem: dict | None = None) -> dict:
    """Pacote de conteúdo sem IA, montado a partir de modelos de texto."""
    titulo = produto["titulo"]
    curto = titulo_curto(titulo)
    preco = formatar_preco(produto["preco"])
    pid = personagem["id"] if personagem else ""
    abertura = personagem["bordao_abertura"] if personagem else "Olha esse achadinho!"
    fechamento = personagem["bordao_fechamento"] if personagem else "O link tá aqui no carrinho do vídeo."
    return {
        "raio_x": {
            "publico": cfg["nicho"]["publico"],
            "dor": f"perder tempo ou dinheiro sem um {curto.lower()}",
            "beneficios": ["praticidade no dia a dia", f"custa {preco}"],
            "objecoes": ["será que funciona mesmo?", "vale o preço?"],
            "angulo": "achadinho prático e barato",
            "formato": "achado do dia",
        },
        "roteiro": {
            "gancho": abertura,
            "cenas": [
                {"texto_tela": abertura, "narracao": f"{abertura} {titulo}.", "personagem": pid},
                {"texto_tela": curto, "narracao": "Ele resolve aquele problema chato do dia a dia.", "personagem": pid},
                {"texto_tela": f"Só {preco}", "narracao": f"E custa {preco}.", "personagem": pid},
                {"texto_tela": "Link no carrinho", "narracao": fechamento, "personagem": pid},
            ],
            "cta": "Link no carrinho",
        },
        "legenda": f"{titulo} por {preco}. Achadinho que facilita a rotina!",
        "hashtags": _hashtags(produto, personagem),
    }


def pacote_duelo_modelo(produtos: list[dict], personagens: list[dict], cfg: dict) -> dict:
    duelo = cfg.get("duelo", {})
    cenas = [{"texto_tela": duelo.get("gancho", "Qual vale mais?"), "narracao": duelo.get("gancho", ""),
              "personagem": personagens[0]["id"]}]
    for produto, p in zip(produtos, personagens):
        preco = formatar_preco(produto["preco"])
        cenas.append({"texto_tela": titulo_curto(produto["titulo"]),
                      "narracao": f"{p['bordao_abertura']} {produto['titulo']}.", "personagem": p["id"]})
        cenas.append({"texto_tela": f"Só {preco}", "narracao": f"Por {preco}. {p['bordao_fechamento']}",
                      "personagem": p["id"]})
    cenas.append({"texto_tela": "Vota nos comentários!", "narracao": duelo.get("chamada", ""),
                  "personagem": personagens[-1]["id"]})
    return {
        "raio_x": {"publico": cfg["nicho"]["publico"], "dor": "", "beneficios": [], "objecoes": [],
                   "angulo": "duelo entre personagens", "formato": "duelo"},
        "roteiro": {"gancho": cenas[0]["texto_tela"], "cenas": cenas, "cta": duelo.get("chamada", "")},
        "legenda": " x ".join(p["titulo"] for p in produtos) + ". Qual você escolhe?",
        "hashtags": ["achadinhos", "tiktokshop", "duelo"],
    }


def gerar_pacote(produto: dict, cfg: dict, ia: IA, personagem: dict | None = None) -> tuple[dict, str]:
    """Devolve (pacote, origem), onde origem é 'ia' ou 'modelo'."""
    if not ia.ativa:
        return pacote_modelo(produto, cfg, personagem), "modelo"
    if personagem:
        sistema = SISTEMA_PERSONAGEM.format(
            idioma=cfg["nicho"]["idioma"], publico=cfg["nicho"]["publico"],
            **{k: personagem[k] for k in ("id", "nome", "personalidade", "bordao_abertura", "bordao_fechamento")},
            formatos="; ".join(personagem["formatos"]),
        )
    else:
        sistema = SISTEMA_PERSONAGEM.format(
            idioma=cfg["nicho"]["idioma"], publico=cfg["nicho"]["publico"],
            id="", nome="o narrador", personalidade=" " + cfg["nicho"]["tom"],
            bordao_abertura="Olha esse achadinho!", bordao_fechamento="Link no carrinho.",
            formatos="achado do dia",
        )
    pedido = (
        "Faça o raio-x deste produto (público, dor, benefícios, objeções, melhor ângulo e formato) "
        "e depois o roteiro, a legenda e as hashtags.\n\n" + _dados_produto(produto)
    )
    try:
        return ia.gerar_json(sistema, pedido, ESQUEMA_PACOTE), "ia"
    except (RecusaIA, anthropic.APIError, ValueError) as e:
        print(f"  ! IA indisponível para '{produto['titulo']}' ({e}); usando modelo de texto.")
        return pacote_modelo(produto, cfg, personagem), "modelo"


def gerar_pacote_duelo(produtos: list[dict], personagens: list[dict], cfg: dict, ia: IA) -> tuple[dict, str]:
    if not ia.ativa:
        return pacote_duelo_modelo(produtos, personagens, cfg), "modelo"
    fichas = "\n\n".join(
        f"Personagem {p['nome']} (id {p['id']}):{p['personalidade']}Bordões: \"{p['bordao_abertura']}\" / "
        f"\"{p['bordao_fechamento']}\"\nProduto que defende:\n{_dados_produto(prod)}"
        for prod, p in zip(produtos, personagens)
    )
    duelo = cfg.get("duelo", {})
    sistema = SISTEMA_DUELO.format(idioma=cfg["nicho"]["idioma"], fichas=fichas,
                                   gancho=duelo.get("gancho", ""), chamada=duelo.get("chamada", ""))
    try:
        return ia.gerar_json(sistema, "Escreva o duelo.", ESQUEMA_PACOTE), "ia"
    except (RecusaIA, anthropic.APIError, ValueError) as e:
        print(f"  ! IA indisponível para o duelo ({e}); usando modelo de texto.")
        return pacote_duelo_modelo(produtos, personagens, cfg), "modelo"


def montar_legenda(pacote: dict, cfg: dict, personagem: dict | None = None) -> str:
    hashtags = " ".join("#" + h.lstrip("#").replace(" ", "") for h in pacote["hashtags"])
    selo = "\n🤖 Personagem virtual criado com IA." if personagem or pacote["raio_x"].get("formato") == "duelo" else ""
    return f"{pacote['legenda']}\n\n{cfg['divulgacao']['aviso']}{selo}\n{hashtags}".strip()

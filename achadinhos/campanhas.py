"""Campanhas agendadas no grupo: oferta do dia, enquete e textos de convite."""

import sqlite3

import anthropic

from achadinhos import personagens
from achadinhos.conteudo import formatar_preco
from achadinhos.db import produto_dict
from achadinhos.ia import IA, RecusaIA
from achadinhos.publicar import telegram


def _registrar(con: sqlite3.Connection, tipo: str, produto_id: int | None, detalhe: str) -> None:
    con.execute("INSERT INTO campanhas (tipo, produto_id, detalhe) VALUES (?, ?, ?)", (tipo, produto_id, detalhe))
    con.commit()


def _texto_oferta(produto: dict, personagem: dict | None, cfg: dict, ia: IA) -> str:
    padrao = (f"{personagem['bordao_abertura'] if personagem else '🔥 Achadinho do dia!'}\n\n"
              f"{produto['titulo']}\n💰 {formatar_preco(produto['preco'])}")
    if ia.ativa and personagem:
        sistema = (f"Você é {personagem['nome']}, personagem virtual de achadinhos. Personalidade:"
                   f"{personagem['personalidade']}\nEscreva uma mensagem de grupo de até 3 linhas apresentando o "
                   "produto. Só use os dados fornecidos: sem inventar benefícios, garantias ou urgência. "
                   "Não coloque link nem hashtags.")
        dados = f"{produto['titulo']} — {formatar_preco(produto['preco'])} — categoria {produto['categoria']}"
        try:
            padrao = ia.gerar_texto(sistema, [{"role": "user", "content": dados}], max_tokens=1000)
        except (RecusaIA, anthropic.APIError) as e:
            print(f"  ! IA indisponível ({e}); usando texto pronto.")
    return f"{padrao}\n\n🛒 {produto['url_afiliado']}\n#publi link de afiliado"


def oferta(con: sqlite3.Connection, cfg: dict, simular: bool = False) -> str:
    """Manda ao grupo o melhor produto que não apareceu nas campanhas dos últimos 7 dias."""
    linha = con.execute(
        "SELECT * FROM produtos WHERE status IN ('aprovado', 'usado') AND id NOT IN ("
        " SELECT produto_id FROM campanhas WHERE produto_id IS NOT NULL AND criado_em >= datetime('now', '-7 days'))"
        " ORDER BY score DESC LIMIT 1"
    ).fetchone()
    if not linha:
        return "Sem produto novo para ofertar (todos já saíram nos últimos 7 dias)."
    produto = produto_dict(linha)
    texto = _texto_oferta(produto, personagens.escolher(produto, cfg), cfg, IA(cfg))
    if not simular:
        foto = next((i for i in produto["imagens"] if i.startswith("http")), None)
        if foto:
            telegram.enviar_foto(foto, texto)
        else:
            telegram.enviar_mensagem(texto)
        _registrar(con, "oferta", produto["id"], texto)
    return texto


def enquete(con: sqlite3.Connection, cfg: dict, simular: bool = False) -> str:
    """Pergunta ao grupo o que ele quer ver; engaja e mostra quais categorias interessam."""
    opcoes = []
    for p in cfg["personagens"]:
        for categoria in p["categorias"][:2]:
            opcoes.append(f"{categoria.capitalize()} ({p['nome'].split()[0]})")
    opcoes = opcoes or ["Casa", "Beleza", "Tecnologia", "Pets"]
    pergunta = "Qual achadinho vocês querem ver amanhã? 👀"
    if not simular:
        telegram.enviar_enquete(pergunta, opcoes)
        _registrar(con, "enquete", None, " | ".join(opcoes))
    return pergunta + "\n" + "\n".join(f"- {o}" for o in opcoes)


def convite(cfg: dict) -> str:
    """Textos prontos para levar gente ao grupo (bio, comentário fixado, stories)."""
    grupo = cfg["grupo"].get("link") or "<link do grupo>"
    nomes = " e ".join(p["nome"] for p in cfg["personagens"]) or "a gente"
    return "\n\n".join([
        f"BIO:\n🛍️ Achadinhos todo dia com {nomes} (personagens IA)\n👇 Grupo VIP de ofertas\n{grupo}",
        f"COMENTÁRIO FIXADO:\nQuer receber achadinhos antes de todo mundo? Entra no grupo: {grupo}",
        f"STORIES (com figurinha de link):\nO grupo de achadinhos tá on! Ofertas, enquetes e links direto no celular. {grupo}",
    ])

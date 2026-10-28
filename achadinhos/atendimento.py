"""Respostas automáticas: acha o produto que a pessoa quer e manda o link."""

import re
import sqlite3

import anthropic

from achadinhos.conteudo import formatar_preco
from achadinhos.ia import IA, RecusaIA
from achadinhos.personagens import normalizar

SISTEMA = """Você responde mensagens de clientes de um perfil de achadinhos (afiliado do TikTok Shop),
falando como {nome}, personagem virtual criado com IA. Personalidade:{personalidade}

Regras:
- Respostas curtas (até 4 linhas), simpáticas, em português do Brasil.
- Só indique produtos da lista abaixo e só use os links exatamente como estão. Se o que a pessoa
  procura não está na lista, diga que ainda não tem e convide para o grupo{grupo}.
- Sempre que mandar link, avise que é link de afiliado (#publi).
- Não prometa resultado, prazo de entrega, garantia ou troca: compra, entrega e trocas são com a
  loja no TikTok Shop. Para problema com pedido, oriente a falar com a loja pelo app.
- Se perguntarem se você é real, diga que é um personagem virtual criado com IA.
- Não peça dados pessoais (CPF, endereço, telefone, cartão).

Produtos disponíveis:
{catalogo}"""


# Palavras comuns em perguntas que não ajudam a achar o produto.
IGNORAR = {"tem", "que", "uma", "um", "para", "pra", "com", "voce", "voces", "quero", "link", "onde",
           "quanto", "custa", "manda", "esse", "essa", "isso", "algum", "alguma", "vende", "achar", "qual"}


def buscar_produtos(con: sqlite3.Connection, texto: str, limite: int = 3) -> list[dict]:
    palavras = {p for p in re.findall(r"\w+", normalizar(texto)) if len(p) >= 3 and p not in IGNORAR}
    if not palavras:
        return []
    achados = []
    for r in con.execute("SELECT * FROM produtos WHERE status IN ('aprovado', 'usado')"):
        alvo = normalizar(f"{r['titulo']} {r['categoria']}")
        acertos = sum(1 for p in palavras if p in alvo)
        if acertos:
            achados.append((acertos, r["score"] or 0, dict(r)))
    achados.sort(key=lambda a: (a[0], a[1]), reverse=True)
    return [a[2] for a in achados[:limite]]


def linha_produto(p: dict) -> str:
    return f"• {p['titulo']} — {formatar_preco(p['preco'])}: {p['url_afiliado']}"


def responder(con: sqlite3.Connection, cfg: dict, ia: IA, texto: str, personagem: dict | None) -> str:
    achados = buscar_produtos(con, texto)
    grupo = cfg.get("grupo", {}).get("link", "")
    if ia.ativa:
        destaque = [dict(r) for r in con.execute(
            "SELECT * FROM produtos WHERE status IN ('aprovado', 'usado') ORDER BY score DESC LIMIT 15")]
        catalogo = {p["id"]: p for p in achados + destaque}.values()
        sistema = SISTEMA.format(
            nome=personagem["nome"] if personagem else "o perfil",
            personalidade=personagem["personalidade"] if personagem else " simpático e direto.",
            grupo=f" ({grupo})" if grupo else "",
            catalogo="\n".join(linha_produto(p) for p in catalogo) or "(nenhum produto cadastrado)",
        )
        try:
            return ia.gerar_texto(sistema, [{"role": "user", "content": texto}])[:1000]
        except (RecusaIA, anthropic.APIError) as e:
            print(f"  ! IA indisponível no atendimento ({e}); usando resposta pronta.")
    if achados:
        return ("Achei isso pra você:\n" + "\n".join(linha_produto(p) for p in achados)
                + "\n\n#publi links de afiliado.")
    convite = f" Entra no grupo que lá sai achadinho todo dia: {grupo}" if grupo else ""
    return f"Ainda não tenho esse por aqui 😕 Me fala o nome do produto que eu procuro!{convite}"


def mensagem_link(cfg: dict, produto: dict, nome: str) -> str:
    texto = cfg["respostas"]["mensagem_link"].format(
        nome=nome or "tudo bem", produto=produto["titulo"], link=produto["url_afiliado"])
    grupo = cfg.get("grupo", {}).get("link")
    if grupo:
        texto += f"\n\nQuer mais achadinhos? Entra no grupo: {grupo}"
    return texto


def pode_responder(con: sqlite3.Connection, cfg: dict, plataforma: str, usuario: str) -> bool:
    """Limite diário por pessoa, para não parecer spam."""
    n = con.execute(
        "SELECT COUNT(*) FROM interacoes WHERE plataforma = ? AND usuario = ?"
        " AND criado_em >= datetime('now', '-1 day')",
        (plataforma, usuario),
    ).fetchone()[0]
    return n < cfg["respostas"]["max_por_pessoa_dia"]


def registrar(con: sqlite3.Connection, plataforma: str, id_externo: str, usuario: str,
              entrada: str, resposta: str) -> bool:
    """Grava a interação; devolve False se ela já tinha sido respondida (notificação repetida)."""
    cur = con.execute(
        "INSERT OR IGNORE INTO interacoes (plataforma, id_externo, usuario, entrada, resposta)"
        " VALUES (?, ?, ?, ?, ?)",
        (plataforma, id_externo, usuario, entrada, resposta),
    )
    con.commit()
    return cur.rowcount == 1

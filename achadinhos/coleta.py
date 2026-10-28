"""Passo 2: coleta de produtos a partir de uma planilha CSV.

O TikTok Shop não oferece uma API pública de catálogo para afiliados, então a
entrada é uma planilha que você monta no Centro de Afiliados (ou exporta de uma
ferramenta de pesquisa de produtos). Colunas aceitas estão em COLUNAS.
"""

import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

# nome no banco -> nomes aceitos no cabeçalho do CSV
COLUNAS = {
    "titulo": ["titulo", "título", "nome", "produto", "title"],
    "preco": ["preco", "preço", "price"],
    "comissao_pct": ["comissao_pct", "comissão", "comissao", "commission"],
    "vendas": ["vendas", "vendidos", "sold", "sales"],
    "nota": ["nota", "avaliacao", "avaliação", "rating"],
    "url_afiliado": ["url_afiliado", "link", "url", "link_afiliado"],
    "imagens": ["imagens", "imagem", "images", "image"],
    "categoria": ["categoria", "category"],
}
OBRIGATORIAS = ["titulo", "preco", "comissao_pct", "url_afiliado"]


def _numero(valor: str) -> float:
    """Aceita '39,90', 'R$ 1.299,90', '15%' e '39.90'."""
    v = (valor or "").replace("R$", "").replace("%", "").strip()
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    return float(v) if v else 0.0


def _mapear_cabecalho(cabecalho: list[str]) -> dict[str, str]:
    normalizado = {c.strip().lower(): c for c in cabecalho}
    mapa = {}
    for campo, nomes in COLUNAS.items():
        for nome in nomes:
            if nome in normalizado:
                mapa[campo] = normalizado[nome]
                break
    faltando = [c for c in OBRIGATORIAS if c not in mapa]
    if faltando:
        raise ValueError(f"CSV sem as colunas obrigatórias: {', '.join(faltando)}")
    return mapa


def importar_csv(con: sqlite3.Connection, caminho: str | Path) -> tuple[int, int]:
    """Importa produtos; links já existentes são atualizados. Retorna (novos, atualizados)."""
    novos = atualizados = 0
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        mapa = _mapear_cabecalho(leitor.fieldnames or [])
        for linha in leitor:
            get = lambda campo: (linha.get(mapa[campo]) or "").strip() if campo in mapa else ""
            if not get("titulo") or not get("url_afiliado"):
                continue
            imagens = [i.strip() for i in get("imagens").split("|") if i.strip()]
            dados = (
                get("titulo"),
                _numero(get("preco")),
                _numero(get("comissao_pct")),
                int(_numero(get("vendas"))),
                _numero(get("nota")),
                json.dumps(imagens),
                get("categoria"),
                get("url_afiliado"),
            )
            existe = con.execute(
                "SELECT 1 FROM produtos WHERE url_afiliado = ?", (get("url_afiliado"),)
            ).fetchone()
            if existe:
                con.execute(
                    "UPDATE produtos SET titulo=?, preco=?, comissao_pct=?, vendas=?, nota=?,"
                    " imagens=?, categoria=? WHERE url_afiliado=?",
                    dados,
                )
                atualizados += 1
            else:
                con.execute(
                    "INSERT INTO produtos (titulo, preco, comissao_pct, vendas, nota, imagens,"
                    " categoria, url_afiliado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    dados,
                )
                novos += 1
    con.commit()
    return novos, atualizados


COLUNAS_VENDAS = {
    "url_afiliado": ["url_afiliado", "link", "url", "link_afiliado"],
    "titulo": ["titulo", "título", "produto", "nome", "product"],
    "comissao": ["comissao", "comissão", "comissao_estimada", "commission", "valor_comissao"],
    "data": ["data", "date", "data_pedido"],
    "pedido": ["pedido", "id_pedido", "order_id", "numero_pedido"],
}


def importar_vendas(con: sqlite3.Connection, caminho: str | Path) -> int:
    """Importa vendas do Centro de Afiliados (planilha) para o ranking aprender o que converte.

    Cada linha precisa do link de afiliado ou do título exato do produto, e da comissão.
    Com a coluna de número do pedido, reimportar a mesma planilha não duplica vendas.
    """
    novas = 0
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        normalizado = {c.strip().lower(): c for c in leitor.fieldnames or []}
        mapa = {campo: normalizado[n] for campo, nomes in COLUNAS_VENDAS.items()
                for n in nomes if n in normalizado}
        if "comissao" not in mapa or not ({"url_afiliado", "titulo"} & mapa.keys()):
            raise ValueError("planilha de vendas precisa de comissao e de url_afiliado ou titulo")
        for linha in leitor:
            get = lambda campo: (linha.get(mapa[campo]) or "").strip() if campo in mapa else ""
            url = get("url_afiliado")
            if not url and get("titulo"):
                achado = con.execute("SELECT url_afiliado FROM produtos WHERE titulo = ?", (get("titulo"),)).fetchone()
                url = achado[0] if achado else ""
            if not url:
                continue
            cur = con.execute(
                "INSERT OR IGNORE INTO vendas (url_afiliado, comissao, data, pedido) VALUES (?, ?, ?, ?)",
                (url, _numero(get("comissao")), get("data") or "sem data", get("pedido")),
            )
            novas += cur.rowcount
    con.commit()
    return novas


URL = re.compile(r"https?://\S+")


def ler_linha_de_link(linha: str) -> dict | None:
    """Aceita "nome | preço | quanto ganha | categoria | link", só o link, ou o texto
    que o botão Compartilhar copia ("Confira ... https://vt.tiktok.com/...")."""
    achado = URL.search(linha)
    if not achado:
        return None
    url = achado.group(0).rstrip(".,;)")
    antes = linha[: achado.start()].strip().rstrip("|").strip()
    campos = [c.strip() for c in antes.split("|")] if "|" in antes else [antes]
    campos += [""] * (4 - len(campos))
    nome, preco, ganha, categoria = campos[:4]
    preco_n = _numero(preco) if preco else 0.0
    ganha_n = _numero(ganha) if ganha else 0.0
    return {
        "titulo": nome,
        "preco": preco_n,
        # O Mercado de produtos mostra quanto você ganha em reais; aqui vira percentual.
        "comissao_pct": round(100 * ganha_n / preco_n, 1) if preco_n and ganha_n else 0.0,
        "categoria": categoria.lower(),
        "url_afiliado": url,
    }


def importar_links(con: sqlite3.Connection, caminho: str | Path) -> tuple[int, int, int]:
    """Importa a lista de links colados. Devolve (novos, atualizados, sem_nome).

    Produtos sem nome ficam como 'incompleto' e não entram nos vídeos até você
    completar a linha (rodar de novo atualiza pelo link).
    """
    novos = atualizados = sem_nome = 0
    texto = sys.stdin.read() if str(caminho) == "-" else Path(caminho).read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.lstrip().startswith("#"):
            continue
        p = ler_linha_de_link(linha)
        if not p:
            continue
        sem_nome += not p["titulo"]
        existe = con.execute("SELECT * FROM produtos WHERE url_afiliado = ?", (p["url_afiliado"],)).fetchone()
        if existe:
            # Só sobrescreve o que veio preenchido.
            novos_dados = {k: v for k, v in p.items() if v} | {"url_afiliado": p["url_afiliado"]}
            sets = ", ".join(f"{k} = ?" for k in novos_dados if k != "url_afiliado")
            if sets:
                con.execute(f"UPDATE produtos SET {sets} WHERE url_afiliado = ?",
                            [v for k, v in novos_dados.items() if k != "url_afiliado"] + [p["url_afiliado"]])
            atualizados += 1
        else:
            con.execute(
                "INSERT INTO produtos (titulo, preco, comissao_pct, categoria, url_afiliado) VALUES (?, ?, ?, ?, ?)",
                (p["titulo"], p["preco"], p["comissao_pct"], p["categoria"], p["url_afiliado"]),
            )
            novos += 1
    con.commit()
    return novos, atualizados, sem_nome

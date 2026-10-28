"""Passo 2: coleta de produtos a partir de uma planilha CSV.

O TikTok Shop não oferece uma API pública de catálogo para afiliados, então a
entrada é uma planilha que você monta no Centro de Afiliados (ou exporta de uma
ferramenta de pesquisa de produtos). Colunas aceitas estão em COLUNAS.
"""

import csv
import json
import sqlite3
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

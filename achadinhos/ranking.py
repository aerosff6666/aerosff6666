"""Passo 3: filtra e ranqueia produtos pelo potencial de ganho."""

import math
import sqlite3


def motivo_reprovacao(p: dict, regras: dict) -> str | None:
    if not regras["preco_min"] <= p["preco"] <= regras["preco_max"]:
        return "preço fora da faixa"
    if p["comissao_pct"] < regras["comissao_min_pct"]:
        return "comissão baixa"
    if p["nota"] < regras["nota_min"]:
        return "nota baixa"
    if p["vendas"] < regras["vendas_min"]:
        return "poucas vendas"
    return None


def calcular_scores(produtos: list[dict], regras: dict) -> dict[int, float]:
    """Score de 0 a 100, relativo aos produtos aprovados no filtro."""
    aprovados = [p for p in produtos if motivo_reprovacao(p, regras) is None]
    if not aprovados:
        return {}
    ganho = {p["id"]: p["preco"] * p["comissao_pct"] / 100 for p in aprovados}
    vendas = {p["id"]: math.log10(p["vendas"] + 1) for p in aprovados}
    max_ganho = max(ganho.values()) or 1
    max_vendas = max(vendas.values()) or 1
    scores = {}
    for p in aprovados:
        nota = (p["nota"] - regras["nota_min"]) / max(5 - regras["nota_min"], 0.01)
        s = (
            regras["peso_ganho_por_venda"] * ganho[p["id"]] / max_ganho
            + regras["peso_vendas"] * vendas[p["id"]] / max_vendas
            + regras["peso_nota"] * nota
        )
        scores[p["id"]] = round(100 * s, 1)
    return scores


def ranquear(con: sqlite3.Connection, regras: dict) -> list[dict]:
    """Atualiza score e status de todos os produtos e devolve os aprovados em ordem."""
    produtos = [dict(r) for r in con.execute("SELECT * FROM produtos")]
    scores = calcular_scores(produtos, regras)
    for p in produtos:
        if p["status"] in ("novo", "reprovado", "aprovado"):
            status = "aprovado" if p["id"] in scores else "reprovado"
        else:
            status = p["status"]
        con.execute(
            "UPDATE produtos SET score = ?, status = ? WHERE id = ?",
            (scores.get(p["id"]), status, p["id"]),
        )
    con.commit()
    return [
        dict(r)
        for r in con.execute(
            "SELECT * FROM produtos WHERE score IS NOT NULL ORDER BY score DESC"
        )
    ]

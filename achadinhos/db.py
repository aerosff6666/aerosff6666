"""Banco SQLite: produtos, conteúdos gerados e publicações."""

import json
import sqlite3
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY,
    titulo TEXT NOT NULL,
    preco REAL NOT NULL,
    comissao_pct REAL NOT NULL,
    vendas INTEGER NOT NULL DEFAULT 0,
    nota REAL NOT NULL DEFAULT 0,
    url_afiliado TEXT NOT NULL UNIQUE,
    imagens TEXT NOT NULL DEFAULT '[]',
    categoria TEXT NOT NULL DEFAULT '',
    score REAL,
    status TEXT NOT NULL DEFAULT 'novo',
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conteudos (
    id INTEGER PRIMARY KEY,
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    pacote TEXT NOT NULL,
    legenda TEXT NOT NULL,
    video TEXT,
    status TEXT NOT NULL DEFAULT 'gerado',
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS publicacoes (
    id INTEGER PRIMARY KEY,
    conteudo_id INTEGER NOT NULL REFERENCES conteudos(id),
    plataforma TEXT NOT NULL,
    id_externo TEXT,
    status TEXT NOT NULL,
    detalhe TEXT,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY,
    url_afiliado TEXT NOT NULL,
    comissao REAL NOT NULL,
    data TEXT NOT NULL,
    pedido TEXT NOT NULL DEFAULT '',
    UNIQUE (url_afiliado, data, comissao, pedido)
);
CREATE TABLE IF NOT EXISTS interacoes (
    id INTEGER PRIMARY KEY,
    plataforma TEXT NOT NULL,
    id_externo TEXT NOT NULL UNIQUE,
    usuario TEXT,
    entrada TEXT,
    resposta TEXT,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS campanhas (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    produto_id INTEGER REFERENCES produtos(id),
    detalhe TEXT,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# Colunas adicionadas depois da primeira versão (bancos antigos recebem via ALTER TABLE).
MIGRACOES = [
    ("conteudos", "personagem", "TEXT"),
]


def conectar(cfg: dict) -> sqlite3.Connection:
    con = sqlite3.connect(Path(cfg["_raiz"]) / "achadinhos.db")
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    for tabela, coluna, tipo in MIGRACOES:
        colunas = {r["name"] for r in con.execute(f"PRAGMA table_info({tabela})")}
        if coluna not in colunas:
            con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    return con


def produto_dict(linha: sqlite3.Row) -> dict:
    d = dict(linha)
    d["imagens"] = json.loads(d["imagens"])
    return d


def conteudo_dict(linha: sqlite3.Row) -> dict:
    d = dict(linha)
    d["pacote"] = json.loads(d["pacote"])
    return d

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
"""


def conectar(cfg: dict) -> sqlite3.Connection:
    con = sqlite3.connect(Path(cfg["_raiz"]) / "achadinhos.db")
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def produto_dict(linha: sqlite3.Row) -> dict:
    d = dict(linha)
    d["imagens"] = json.loads(d["imagens"])
    return d


def conteudo_dict(linha: sqlite3.Row) -> dict:
    d = dict(linha)
    d["pacote"] = json.loads(d["pacote"])
    return d

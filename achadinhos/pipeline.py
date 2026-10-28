"""Junta os 12 passos: ranquear -> gerar conteúdo -> aprovar -> publicar -> relatório."""

import json
import shutil
import sqlite3
from pathlib import Path

from achadinhos import conteudo, narracao, ranking, video
from achadinhos.config import pasta
from achadinhos.db import conteudo_dict, produto_dict
from achadinhos.ia import IA
from achadinhos.publicar import ErroPublicacao, instagram, telegram, tiktok


def gerar(con: sqlite3.Connection, cfg: dict, quantidade: int) -> list[int]:
    """Passos 3 a 8 para os melhores produtos ainda sem vídeo. Devolve os ids dos conteúdos."""
    ranking.ranquear(con, cfg["ranking"])
    produtos = [
        produto_dict(r)
        for r in con.execute(
            "SELECT * FROM produtos WHERE status = 'aprovado' ORDER BY score DESC LIMIT ?",
            (quantidade,),
        )
    ]
    ia = IA(cfg)
    saida, cache = pasta(cfg, "saida"), pasta(cfg, "cache")
    criados = []
    for p in produtos:
        print(f"→ {p['titulo']} (score {p['score']})")
        pacote, origem = conteudo.gerar_pacote(p, cfg, ia)
        pacote["origem"] = origem
        legenda = conteudo.montar_legenda(pacote, cfg)
        cur = con.execute(
            "INSERT INTO conteudos (produto_id, pacote, legenda) VALUES (?, ?, ?)",
            (p["id"], json.dumps(pacote, ensure_ascii=False), legenda),
        )
        cid = cur.lastrowid
        dir_conteudo = saida / str(cid)
        dir_conteudo.mkdir(exist_ok=True)
        roteiro = pacote["roteiro"]
        texto_narracao = " ".join(c["narracao"] for c in roteiro["cenas"])
        audio = narracao.gerar_narracao(texto_narracao, dir_conteudo / "narracao.mp3", cfg)
        arquivo = video.montar_video(pacote, p["imagens"], audio, dir_conteudo, cfg, cache)
        (dir_conteudo / "legenda.txt").write_text(legenda, encoding="utf-8")
        (dir_conteudo / "roteiro.json").write_text(json.dumps(pacote, ensure_ascii=False, indent=2), encoding="utf-8")
        status = "gerado" if cfg["publicacao"]["aprovacao_manual"] else "aprovado"
        con.execute("UPDATE conteudos SET video = ?, status = ? WHERE id = ?", (str(arquivo), status, cid))
        con.execute("UPDATE produtos SET status = 'usado' WHERE id = ?", (p["id"],))
        con.commit()
        print(f"  ✓ conteúdo #{cid} ({origem}): {arquivo}")
        criados.append(cid)
    return criados


def mudar_status(con: sqlite3.Connection, ids: list[int], status: str) -> None:
    """Passo 9: aprovação humana."""
    for cid in ids:
        con.execute("UPDATE conteudos SET status = ? WHERE id = ? AND status = 'gerado'", (status, cid))
    con.commit()


def _ja_publicado(con: sqlite3.Connection, cid: int, plataforma: str) -> bool:
    return con.execute(
        "SELECT 1 FROM publicacoes WHERE conteudo_id = ? AND plataforma = ? AND status = 'ok'",
        (cid, plataforma),
    ).fetchone() is not None


def publicar(con: sqlite3.Connection, cfg: dict, plataformas: list[str], simular: bool = False) -> None:
    """Passos 10 a 12 para todos os conteúdos aprovados."""
    linhas = con.execute(
        "SELECT c.*, p.url_afiliado, p.titulo FROM conteudos c JOIN produtos p ON p.id = c.produto_id"
        " WHERE c.status = 'aprovado' ORDER BY c.id"
    ).fetchall()
    if not linhas:
        print("Nenhum conteúdo aprovado. Use: achadinhos aprovar <id>")
        return
    pub = cfg["publicacao"]
    for linha in linhas:
        c = conteudo_dict(linha)
        arquivo = Path(c["video"])
        todas_ok = True
        for plataforma in plataformas:
            if _ja_publicado(con, c["id"], plataforma):
                continue
            print(f"→ #{c['id']} {c['titulo']} → {plataforma}")
            if simular:
                print("  (simulação: nada foi enviado)")
                todas_ok = False
                continue
            try:
                if plataforma == "tiktok":
                    id_externo = tiktok.publicar(arquivo, c["legenda"], pub["tiktok_modo"])
                elif plataforma == "instagram":
                    nome = f"{c['id']}.mp4"
                    id_externo = instagram.publicar(arquivo, c["legenda"], pub["url_publica_base"], nome)
                elif plataforma == "telegram":
                    id_externo = telegram.publicar(arquivo, c["legenda"], c["url_afiliado"])
                else:
                    raise ErroPublicacao(f"plataforma desconhecida: {plataforma}")
                status, detalhe = "ok", None
                print(f"  ✓ {id_externo}")
            except (ErroPublicacao, OSError) as e:
                id_externo, status, detalhe = None, "erro", str(e)
                todas_ok = False
                print(f"  ✗ {e}")
            con.execute(
                "INSERT INTO publicacoes (conteudo_id, plataforma, id_externo, status, detalhe)"
                " VALUES (?, ?, ?, ?, ?)",
                (c["id"], plataforma, id_externo, status, detalhe),
            )
            con.commit()
        if todas_ok:
            con.execute("UPDATE conteudos SET status = 'publicado' WHERE id = ?", (c["id"],))
            con.commit()


def exportar_para_instagram(con: sqlite3.Connection, cfg: dict, destino: Path) -> int:
    """Copia os vídeos aprovados como <id>.mp4 para uma pasta que você sincroniza com o bucket público."""
    destino.mkdir(parents=True, exist_ok=True)
    n = 0
    for r in con.execute("SELECT id, video FROM conteudos WHERE status = 'aprovado'"):
        shutil.copy(r["video"], destino / f"{r['id']}.mp4")
        n += 1
    return n


def relatorio(con: sqlite3.Connection) -> str:
    linhas = ["== Produtos =="]
    for r in con.execute("SELECT status, COUNT(*) n FROM produtos GROUP BY status"):
        linhas.append(f"  {r['status']:<10} {r['n']}")
    linhas.append("== Conteúdos ==")
    for r in con.execute("SELECT status, COUNT(*) n FROM conteudos GROUP BY status"):
        linhas.append(f"  {r['status']:<10} {r['n']}")
    linhas.append("== Publicações ==")
    for r in con.execute(
        "SELECT plataforma, status, COUNT(*) n FROM publicacoes GROUP BY plataforma, status"
    ):
        linhas.append(f"  {r['plataforma']:<10} {r['status']:<6} {r['n']}")
    linhas.append(
        "Vendas e comissões: confira no Centro de Afiliados do TikTok Shop "
        "(a API de afiliados não é aberta ao público)."
    )
    return "\n".join(linhas)

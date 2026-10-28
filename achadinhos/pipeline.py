"""Junta os 12 passos: ranquear -> gerar conteúdo -> aprovar -> publicar -> relatório."""

import json
import random
import shutil
import sqlite3
from pathlib import Path

from achadinhos import avatar, conteudo, narracao, personagens, ranking, video
from achadinhos.config import pasta
from achadinhos.db import conteudo_dict, produto_dict
from achadinhos.ia import IA
from achadinhos.publicar import ErroPublicacao, instagram, telegram, tiktok


def _escolher_produtos(con: sqlite3.Connection, cfg: dict, quantidade: int) -> list[dict]:
    """Os melhores por score, com ~20% de vagas para categorias que ainda não venderam."""
    ranking.ranquear(con, cfg["ranking"])
    aprovados = [produto_dict(r) for r in con.execute(
        "SELECT * FROM produtos WHERE status = 'aprovado' ORDER BY score DESC")]
    desempenho = ranking.desempenho_categorias(con)
    if not desempenho:
        return aprovados[:quantidade]
    n_explorar = max(1, round(quantidade * 0.2)) if quantidade >= 2 else 0
    escolhidos = aprovados[: quantidade - n_explorar]
    sem_vendas = [p for p in aprovados[len(escolhidos):]
                  if personagens.normalizar(p["categoria"]) not in desempenho]
    restantes = [p for p in aprovados[len(escolhidos):] if p not in sem_vendas]
    escolhidos += random.sample(sem_vendas, min(n_explorar, len(sem_vendas)))
    return escolhidos + restantes[: quantidade - len(escolhidos)]


def _salvar_conteudo(con, cfg, produto_id, pacote, origem, personagem_id, imagens, dir_base) -> int:
    legenda = conteudo.montar_legenda(pacote, cfg, personagens.por_id(cfg, personagem_id))
    pacote["origem"] = origem
    cur = con.execute(
        "INSERT INTO conteudos (produto_id, pacote, legenda, personagem) VALUES (?, ?, ?, ?)",
        (produto_id, json.dumps(pacote, ensure_ascii=False), legenda, personagem_id),
    )
    cid = cur.lastrowid
    pasta_c = dir_base / str(cid)
    pasta_c.mkdir(exist_ok=True)
    por_id = {p["id"]: p for p in cfg["personagens"]}
    cenas = pacote["roteiro"]["cenas"]
    personagem = por_id.get(personagem_id)
    cache = pasta(cfg, "cache")
    if avatar.disponivel(personagem) and cfg.get("avatar", {}).get("ativo", True):
        clipe = avatar.gerar_clipe(" ".join(c["narracao"] for c in cenas), personagem, pasta_c / "avatar.mp4", cfg)
        arquivo = video.video_com_avatar(clipe, imagens, pasta_c, cfg, cache, personagem)
    else:
        audio = narracao.gerar_narracao(cenas, pasta_c / "narracao.mp3", cfg)
        arquivo = video.montar_video(pacote, imagens, audio, pasta_c, cfg, cache, por_id)
    (pasta_c / "legenda.txt").write_text(legenda, encoding="utf-8")
    (pasta_c / "roteiro.json").write_text(json.dumps(pacote, ensure_ascii=False, indent=2), encoding="utf-8")
    status = "gerado" if cfg["publicacao"]["aprovacao_manual"] else "aprovado"
    con.execute("UPDATE conteudos SET video = ?, status = ? WHERE id = ?", (str(arquivo), status, cid))
    con.commit()
    print(f"  ✓ conteúdo #{cid} ({origem}, {personagem['nome'] if personagem else 'duelo/sem personagem'}): {arquivo}")
    return cid


def gerar(con: sqlite3.Connection, cfg: dict, quantidade: int) -> list[int]:
    """Passos 3 a 8 para os melhores produtos ainda sem vídeo. Devolve os ids dos conteúdos."""
    ia = IA(cfg)
    saida = pasta(cfg, "saida")
    criados = []
    for p in _escolher_produtos(con, cfg, quantidade):
        personagem = personagens.escolher(p, cfg)
        print(f"→ {p['titulo']} (score {p['score']}) com {personagem['nome'] if personagem else 'narrador'}")
        pacote, origem = conteudo.gerar_pacote(p, cfg, ia, personagem)
        cid = _salvar_conteudo(con, cfg, p["id"], pacote, origem,
                               personagem["id"] if personagem else None, p["imagens"], saida)
        con.execute("UPDATE produtos SET status = 'usado' WHERE id = ?", (p["id"],))
        con.commit()
        criados.append(cid)
    return criados


def gerar_duelo(con: sqlite3.Connection, cfg: dict) -> int | None:
    """Um vídeo com os dois primeiros personagens, cada um defendendo o melhor produto da sua área."""
    if len(cfg["personagens"]) < 2:
        print("O duelo precisa de dois personagens em personagens.toml.")
        return None
    ranking.ranquear(con, cfg["ranking"])
    aprovados = [produto_dict(r) for r in con.execute(
        "SELECT * FROM produtos WHERE status = 'aprovado' ORDER BY score DESC")]
    dupla = cfg["personagens"][:2]
    produtos = []
    for pers in dupla:
        candidato = next((p for p in aprovados if personagens.escolher(p, cfg) is pers and p not in produtos), None)
        if candidato is None:
            candidato = next((p for p in aprovados if p not in produtos), None)
        if candidato is None:
            print("Faltam produtos aprovados para o duelo.")
            return None
        produtos.append(candidato)
    print(f"→ Duelo: {produtos[0]['titulo']} x {produtos[1]['titulo']}")
    pacote, origem = conteudo.gerar_pacote_duelo(produtos, dupla, cfg, IA(cfg))
    pacote["duelo"] = {pers["id"]: prod["id"] for pers, prod in zip(dupla, produtos)}
    imagens = [i for prod in produtos for i in prod["imagens"][:2]]
    cid = _salvar_conteudo(con, cfg, produtos[0]["id"], pacote, origem, None, imagens, pasta(cfg, "saida"))
    for prod in produtos:
        con.execute("UPDATE produtos SET status = 'usado' WHERE id = ?", (prod["id"],))
    con.commit()
    return cid


def mudar_status(con: sqlite3.Connection, ids: list[int], status: str) -> None:
    """Passo 9: aprovação humana."""
    for cid in ids:
        con.execute("UPDATE conteudos SET status = ? WHERE id = ? AND status = 'gerado'", (status, cid))
    con.commit()


def links_do_conteudo(con: sqlite3.Connection, c: dict) -> list[tuple[str, str]]:
    ids = list(c["pacote"].get("duelo", {}).values()) or [c["produto_id"]]
    linhas = {r["id"]: r for r in con.execute(
        f"SELECT id, titulo, url_afiliado FROM produtos WHERE id IN ({','.join('?' * len(ids))})", ids)}
    return [(linhas[i]["titulo"], linhas[i]["url_afiliado"]) for i in ids if i in linhas]


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
                    cta = cfg["duelo"].get("chamada") if "duelo" in c["pacote"] else cfg["respostas"]["cta_instagram"]
                    legenda = f"{cta}\n\n{c['legenda']}" if cta else c["legenda"]
                    nome = f"{c['id']}.mp4"
                    id_externo = instagram.publicar(arquivo, legenda, pub["url_publica_base"], nome)
                elif plataforma == "telegram":
                    id_externo = telegram.publicar(arquivo, c["legenda"], links_do_conteudo(con, c))
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

"""Linha de comando: python -m achadinhos <comando>."""

import argparse
from pathlib import Path

from achadinhos import campanhas, coleta, instagram_bot, pipeline, ranking, telegram_bot
from achadinhos.config import carregar_config
from achadinhos.db import conectar, conteudo_dict


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="achadinhos", description="Agente de achadinhos para TikTok Shop")
    ap.add_argument("--config", default="config.toml")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("importar", help="passo 2: importa produtos de um CSV")
    p.add_argument("csv")

    p = sub.add_parser("importar-links", help="passo 2: importa links colados do botão Compartilhar")
    p.add_argument("arquivo", help="arquivo de texto, ou - para colar no terminal")

    p = sub.add_parser("ranquear", help="passo 3: filtra e ordena os produtos")
    p.add_argument("--top", type=int, default=10)

    p = sub.add_parser("gerar", help="passos 3 a 8: raio-x, roteiro, legenda, narração e vídeo")
    p.add_argument("--quantidade", type=int, default=3)

    sub.add_parser("duelo", help="vídeo com os dois personagens disputando o voto do público")

    p = sub.add_parser("importar-vendas", help="importa as vendas do Centro de Afiliados (o ranking aprende)")
    p.add_argument("csv")

    p = sub.add_parser("campanha", help="campanhas no grupo do Telegram")
    p.add_argument("tipo", choices=["oferta", "enquete", "convite"])
    p.add_argument("--simular", action="store_true")

    sub.add_parser("telegram-bot", help="bot do Telegram que responde e manda links (fica rodando)")

    p = sub.add_parser("instagram-bot", help="webhook: comentou EU QUERO, recebe o link no direct (fica rodando)")
    p.add_argument("--porta", type=int, default=8080)

    p = sub.add_parser("listar", help="mostra os conteúdos gerados")
    p.add_argument("--status", choices=["gerado", "aprovado", "rejeitado", "publicado"])

    p = sub.add_parser("aprovar", help="passo 9: aprova conteúdos para publicar")
    p.add_argument("ids", type=int, nargs="+")
    p = sub.add_parser("rejeitar", help="passo 9: descarta conteúdos")
    p.add_argument("ids", type=int, nargs="+")

    p = sub.add_parser("exportar", help="copia os vídeos aprovados para subir na URL pública (Instagram)")
    p.add_argument("pasta")

    p = sub.add_parser("publicar", help="passos 10 a 12: TikTok, Instagram e Telegram")
    p.add_argument("--plataformas", help="ex.: tiktok,telegram (padrão: as do config.toml)")
    p.add_argument("--simular", action="store_true", help="mostra o que seria enviado, sem enviar")

    sub.add_parser("relatorio", help="resumo de produtos, conteúdos e publicações")

    p = sub.add_parser("rodar", help="ciclo completo para agendar no cron")
    p.add_argument("--csv", help="importa este CSV antes")
    p.add_argument("--quantidade", type=int, default=3)

    args = ap.parse_args(argv)
    cfg = carregar_config(args.config)
    con = conectar(cfg)

    if args.comando == "importar":
        novos, atualizados = coleta.importar_csv(con, args.csv)
        print(f"{novos} produtos novos, {atualizados} atualizados.")
    elif args.comando == "importar-links":
        novos, atualizados, sem_nome = coleta.importar_links(con, args.arquivo)
        print(f"{novos} produtos novos, {atualizados} atualizados.")
        if sem_nome:
            print(f"{sem_nome} links sem nome: complete as linhas no formato "
                  "'nome | preço | quanto ganha | categoria | link' e importe de novo.")
    elif args.comando == "ranquear":
        regras = cfg["ranking"]
        for p in ranking.ranquear(con, regras)[: args.top]:
            print(f"{p['score']:6.1f}  #{p['id']:<4} R$ {p['preco']:>8.2f}  {p['comissao_pct']:>4.1f}%  {p['titulo']}")
        for r in con.execute("SELECT * FROM produtos WHERE status IN ('reprovado', 'incompleto')"):
            print(f"  {r['status']} #{r['id']} {r['titulo']}: {ranking.motivo_reprovacao(dict(r), regras)}")
    elif args.comando == "gerar":
        criados = pipeline.gerar(con, cfg, args.quantidade)
        if criados and cfg["publicacao"]["aprovacao_manual"]:
            print(f"\nAssista os vídeos em saida/<id>/video.mp4 e aprove com: achadinhos aprovar {' '.join(map(str, criados))}")
    elif args.comando == "duelo":
        cid = pipeline.gerar_duelo(con, cfg)
        if cid and cfg["publicacao"]["aprovacao_manual"]:
            print(f"\nAssista saida/{cid}/video.mp4 e aprove com: achadinhos aprovar {cid}")
    elif args.comando == "importar-vendas":
        print(f"{coleta.importar_vendas(con, args.csv)} vendas novas importadas.")
        for categoria, peso in sorted(ranking.desempenho_categorias(con).items(), key=lambda x: -x[1]):
            print(f"  {categoria or '(sem categoria)':<15} {'█' * round(peso * 20)}")
    elif args.comando == "campanha":
        if args.tipo == "convite":
            print(campanhas.convite(cfg))
        else:
            texto = getattr(campanhas, args.tipo)(con, cfg, simular=args.simular)
            print(("(simulação)\n" if args.simular else "Enviado:\n") + texto)
    elif args.comando == "telegram-bot":
        telegram_bot.rodar(cfg)
    elif args.comando == "instagram-bot":
        instagram_bot.rodar(cfg, args.porta)
    elif args.comando == "listar":
        sql = "SELECT c.*, p.titulo FROM conteudos c JOIN produtos p ON p.id = c.produto_id"
        params = ()
        if args.status:
            sql += " WHERE c.status = ?"
            params = (args.status,)
        for linha in con.execute(sql + " ORDER BY c.id", params):
            c = conteudo_dict(linha)
            quem = c.get("personagem") or ("duelo" if "duelo" in c["pacote"] else "-")
            print(f"#{c['id']:<4} [{c['status']}] ({quem}) {linha['titulo']}\n      gancho: {c['pacote']['roteiro']['gancho']}\n      {c['video']}")
    elif args.comando in ("aprovar", "rejeitar"):
        pipeline.mudar_status(con, args.ids, "aprovado" if args.comando == "aprovar" else "rejeitado")
        print("ok")
    elif args.comando == "exportar":
        print(f"{pipeline.exportar_para_instagram(con, cfg, Path(args.pasta))} vídeos copiados.")
    elif args.comando == "publicar":
        plataformas = args.plataformas.split(",") if args.plataformas else cfg["publicacao"]["plataformas"]
        pipeline.publicar(con, cfg, plataformas, simular=args.simular)
    elif args.comando == "relatorio":
        print(pipeline.relatorio(con))
    elif args.comando == "rodar":
        if args.csv:
            coleta.importar_csv(con, args.csv)
        pipeline.gerar(con, cfg, args.quantidade)
        if not cfg["publicacao"]["aprovacao_manual"]:
            pipeline.publicar(con, cfg, cfg["publicacao"]["plataformas"])
        print(pipeline.relatorio(con))

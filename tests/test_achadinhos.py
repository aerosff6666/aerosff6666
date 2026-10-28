import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from achadinhos import coleta, conteudo, pipeline, ranking
from achadinhos.config import carregar_config
from achadinhos.db import conectar
from achadinhos.ia import IA, RecusaIA

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    shutil.copy(RAIZ / "config.toml", tmp_path / "config.toml")
    shutil.copy(RAIZ / "personagens.toml", tmp_path / "personagens.toml")
    return carregar_config(tmp_path / "config.toml")


def test_importar_e_ranquear(cfg):
    con = conectar(cfg)
    assert coleta.importar_csv(con, RAIZ / "dados/produtos_exemplo.csv") == (9, 0)
    assert coleta.importar_csv(con, RAIZ / "dados/produtos_exemplo.csv") == (0, 9)
    ordem = ranking.ranquear(con, cfg["ranking"])
    assert ordem[0]["titulo"].startswith(("Mini processador", "Fone de ouvido"))
    reprovados = {r["titulo"] for r in con.execute("SELECT titulo FROM produtos WHERE status='reprovado'")}
    assert reprovados == {"Panela elétrica multifuncional antiaderente", "Capa de celular genérica"}


def test_numero_formato_brasileiro():
    assert coleta._numero("R$ 1.299,90") == 1299.90
    assert coleta._numero("15%") == 15
    assert coleta._numero("39.90") == 39.90


def test_csv_sem_coluna_obrigatoria(cfg, tmp_path):
    arquivo = tmp_path / "ruim.csv"
    arquivo.write_text("titulo,preco\nX,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="comissao_pct"):
        coleta.importar_csv(conectar(cfg), arquivo)


def test_legenda_tem_aviso_de_publi(cfg):
    produto = {"titulo": "Garrafa térmica 1L", "preco": 49.9, "categoria": "casa"}
    pacote, origem = conteudo.gerar_pacote(produto, cfg, IA(cfg))
    assert origem == "modelo"
    legenda = conteudo.montar_legenda(pacote, cfg)
    assert "#publi" in legenda and "R$ 49,90" in legenda


class ClienteFalso:
    def __init__(self, resposta):
        self.pedidos = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.resposta = resposta

    def _create(self, **kwargs):
        self.pedidos.append(kwargs)
        return self.resposta


def _ia_com(cfg, resposta):
    ia = IA(cfg)
    ia.ativa = True
    ia.cliente = ClienteFalso(resposta)
    return ia


def test_ia_pede_json_com_esquema_e_fallback(cfg):
    pacote = conteudo.pacote_modelo({"titulo": "X", "preco": 10, "categoria": ""}, cfg)
    resposta = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=json.dumps(pacote))],
    )
    ia = _ia_com(cfg, resposta)
    resultado, origem = conteudo.gerar_pacote({"titulo": "X", "preco": 10, "vendas": 1, "nota": 5}, cfg, ia)
    assert origem == "ia" and resultado == pacote
    pedido = ia.cliente.pedidos[0]
    assert pedido["model"] == "claude-opus-5-5"
    assert pedido["output_config"]["format"]["schema"] is conteudo.ESQUEMA_PACOTE
    assert pedido["fallbacks"] == "default"


def test_ia_recusa_vira_modelo(cfg):
    resposta = SimpleNamespace(stop_reason="refusal", stop_details=SimpleNamespace(explanation="não"), content=[])
    ia = _ia_com(cfg, resposta)
    with pytest.raises(RecusaIA):
        ia.gerar_json("s", "p", {})
    _, origem = conteudo.gerar_pacote({"titulo": "X", "preco": 10, "vendas": 1, "nota": 5}, cfg, ia)
    assert origem == "modelo"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg não instalado")
def test_fluxo_completo_gera_video_e_simula_publicacao(cfg, capsys):
    con = conectar(cfg)
    coleta.importar_csv(con, RAIZ / "dados/produtos_exemplo.csv")
    cfg["video"]["segundos_por_cena"] = 0.5
    ids = pipeline.gerar(con, cfg, 1)
    assert len(ids) == 1
    video = Path(con.execute("SELECT video FROM conteudos WHERE id=?", (ids[0],)).fetchone()[0])
    assert video.exists() and video.stat().st_size > 0
    pipeline.mudar_status(con, ids, "aprovado")
    pipeline.publicar(con, cfg, ["telegram"], simular=True)
    assert "simulação" in capsys.readouterr().out
    assert con.execute("SELECT status FROM conteudos WHERE id=?", (ids[0],)).fetchone()[0] == "aprovado"


# --- personagens, duelo, vendas, atendimento e bots -------------------------------------

from achadinhos import atendimento, campanhas, instagram_bot, personagens, telegram_bot  # noqa: E402


def _base(cfg):
    con = conectar(cfg)
    coleta.importar_csv(con, RAIZ / "dados/produtos_exemplo.csv")
    ranking.ranquear(con, cfg["ranking"])
    return con


def test_personagem_por_categoria(cfg):
    assert personagens.escolher({"categoria": "Eletrônicos", "id": 1}, cfg)["id"] == "rafa"
    assert personagens.escolher({"categoria": "Beleza", "id": 1}, cfg)["id"] == "bia"
    # Categoria sem dono é dividida entre os dois.
    donos = {personagens.escolher({"categoria": "brinquedos", "id": i}, cfg)["id"] for i in range(2)}
    assert donos == {"bia", "rafa"}


def test_legenda_de_personagem_tem_selo_de_ia(cfg):
    bia = personagens.por_id(cfg, "bia")
    pacote, _ = conteudo.gerar_pacote({"titulo": "Body splash 200ml", "preco": 29.9, "categoria": "beleza"},
                                      cfg, IA(cfg), bia)
    assert pacote["roteiro"]["gancho"] == bia["bordao_abertura"]
    assert "personagem virtual" in conteudo.montar_legenda(pacote, cfg, bia).lower()


def test_titulo_curto_nao_termina_em_conectivo():
    assert conteudo.titulo_curto("Mini processador elétrico de alimentos USB") == "Mini processador elétrico"


def test_vendas_aumentam_peso_da_categoria(cfg, tmp_path):
    con = _base(cfg)
    antes = {r["id"]: r["score"] for r in con.execute("SELECT id, score FROM produtos WHERE score IS NOT NULL")}
    vendas = tmp_path / "vendas.csv"
    vendas.write_text("pedido,link,comissao\nA1,https://exemplo.com/afiliado/fone,8.39\n", encoding="utf-8")
    assert coleta.importar_vendas(con, vendas) == 1
    assert coleta.importar_vendas(con, vendas) == 0  # mesmo pedido não duplica
    ranking.ranquear(con, cfg["ranking"])
    depois = {r["id"]: r["score"] for r in con.execute("SELECT id, score FROM produtos WHERE score IS NOT NULL")}
    fone = con.execute("SELECT id FROM produtos WHERE categoria = 'eletronicos'").fetchone()[0]
    casa = con.execute("SELECT id FROM produtos WHERE categoria = 'casa'").fetchone()[0]
    assert depois[fone] > antes[fone] and depois[casa] < antes[casa]


def test_atendimento_acha_produto_e_avisa_publi(cfg):
    con = _base(cfg)
    resposta = atendimento.responder(con, cfg, IA(cfg), "tem fone bluetooth?", None)
    assert "https://exemplo.com/afiliado/fone" in resposta and "#publi" in resposta
    assert "não tenho" in atendimento.responder(con, cfg, IA(cfg), "bicicleta aro 29", None).lower()


def test_limite_de_respostas_por_pessoa(cfg):
    con = _base(cfg)
    for i in range(cfg["respostas"]["max_por_pessoa_dia"]):
        assert atendimento.pode_responder(con, cfg, "telegram", "u1")
        assert atendimento.registrar(con, "telegram", f"m{i}", "u1", "oi", "olá")
    assert not atendimento.pode_responder(con, cfg, "telegram", "u1")
    assert not atendimento.registrar(con, "telegram", "m0", "u1", "oi", "olá")  # repetida


def test_bot_telegram_fica_quieto_no_grupo_sem_mencao(cfg):
    con = _base(cfg)
    bot = {"id": 99, "username": "achadinhos_bot"}
    grupo = {"id": -100, "type": "supergroup"}
    msg = {"message_id": 1, "chat": grupo, "from": {"id": 5}, "text": "alguém viu o jogo?"}
    assert telegram_bot.tratar(msg, con, cfg, IA(cfg), bot) is None
    msg["text"] = "@achadinhos_bot tem fone?"
    assert "fone" in telegram_bot.tratar(msg, con, cfg, IA(cfg), bot)
    assert "Destaques" in telegram_bot.tratar({**msg, "text": "/ofertas"}, con, cfg, IA(cfg), bot)
    novo = {"message_id": 2, "chat": grupo, "new_chat_members": [{"first_name": "Ana", "is_bot": False}]}
    assert "Ana" in telegram_bot.tratar(novo, con, cfg, IA(cfg), bot)


def test_instagram_comentario_eu_quero_e_duelo(cfg, monkeypatch):
    monkeypatch.setenv("IG_USER_ID", "meu_perfil")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "t")
    con = _base(cfg)
    fone = con.execute("SELECT id FROM produtos WHERE categoria='eletronicos'").fetchone()[0]
    escova = con.execute("SELECT id FROM produtos WHERE titulo LIKE 'Escova%'").fetchone()[0]
    for media, pacote in (("m1", {}), ("m2", {"duelo": {"bia": escova, "rafa": fone}})):
        cid = con.execute("INSERT INTO conteudos (produto_id, pacote, legenda) VALUES (?, ?, '')",
                          (escova if media == "m2" else fone, json.dumps(pacote))).lastrowid
        con.execute("INSERT INTO publicacoes (conteudo_id, plataforma, id_externo, status)"
                    " VALUES (?, 'instagram', ?, 'ok')", (cid, media))
    con.commit()
    assert instagram_bot.produto_pedido(con, cfg, "m1", "EU QUERO!!")["id"] == fone
    assert instagram_bot.produto_pedido(con, cfg, "m1", "que lindo") is None
    assert instagram_bot.produto_pedido(con, cfg, "m2", "rafa ganhou")["id"] == fone

    enviados = []
    monkeypatch.setattr(instagram_bot, "_enviar_direct", lambda dest, texto: enviados.append((dest, texto)))
    monkeypatch.setattr(instagram_bot, "_responder_comentario", lambda cid, texto: enviados.append((cid, texto)))
    comentario = {"id": "c1", "text": "quero", "from": {"id": "fã", "username": "ana"}, "media": {"id": "m1"}}
    instagram_bot.tratar_comentario(con, cfg, comentario)
    instagram_bot.tratar_comentario(con, cfg, comentario)  # notificação repetida
    instagram_bot.tratar_comentario(con, cfg, {**comentario, "id": "c2", "from": {"id": "meu_perfil"}})
    assert len(enviados) == 2  # direct + resposta pública, uma vez só
    assert enviados[0][0] == {"comment_id": "c1"} and "afiliado/fone" in enviados[0][1]


def test_assinatura_do_webhook():
    import hashlib
    import hmac
    corpo = b'{"entry": []}'
    assinatura = "sha256=" + hmac.new(b"segredo", corpo, hashlib.sha256).hexdigest()
    assert instagram_bot.assinatura_valida(corpo, assinatura, "segredo")
    assert not instagram_bot.assinatura_valida(corpo, assinatura, "outro")
    assert not instagram_bot.assinatura_valida(corpo, "", "segredo")


def test_campanhas_simuladas(cfg):
    con = _base(cfg)
    assert "#publi" in campanhas.oferta(con, cfg, simular=True)
    assert "(Bia)" in campanhas.enquete(con, cfg, simular=True)
    assert "personagens IA" in campanhas.convite(cfg)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg não instalado")
def test_duelo_gera_video_com_os_dois(cfg):
    con = conectar(cfg)
    coleta.importar_csv(con, RAIZ / "dados/produtos_exemplo.csv")
    cfg["video"]["segundos_por_cena"] = 0.3
    cid = pipeline.gerar_duelo(con, cfg)
    pacote = json.loads(con.execute("SELECT pacote FROM conteudos WHERE id=?", (cid,)).fetchone()[0])
    assert set(pacote["duelo"]) == {"bia", "rafa"}
    assert {c["personagem"] for c in pacote["roteiro"]["cenas"]} == {"bia", "rafa"}
    assert len(pipeline.links_do_conteudo(con, {"pacote": pacote, "produto_id": 0})) == 2

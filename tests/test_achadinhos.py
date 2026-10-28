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
    return carregar_config(tmp_path / "config.toml")


def test_importar_e_ranquear(cfg):
    con = conectar(cfg)
    assert coleta.importar_csv(con, RAIZ / "dados/produtos_exemplo.csv") == (6, 0)
    assert coleta.importar_csv(con, RAIZ / "dados/produtos_exemplo.csv") == (0, 6)
    ordem = ranking.ranquear(con, cfg["ranking"])
    assert [p["titulo"] for p in ordem][0].startswith("Mini processador")
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

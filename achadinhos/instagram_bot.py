"""Robô do Instagram: comentou "EU QUERO", recebe o link no direct.

Roda um servidor de webhook que a Meta chama a cada comentário ou mensagem.
Ele precisa estar num endereço HTTPS público (VPS com domínio, ou um túnel
como cloudflared/ngrok para testar) cadastrado no painel do app da Meta, com
assinaturas dos campos "comments" e "messages".

Usa só a API oficial: resposta privada a comentário (uma por comentário) e
resposta a quem mandou mensagem nas últimas 24 h.
"""

import hashlib
import hmac
import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from achadinhos import atendimento, personagens
from achadinhos.db import conectar, conteudo_dict, produto_dict
from achadinhos.ia import IA
from achadinhos.publicar import ErroPublicacao, requisitar


def _api() -> tuple[str, str, str]:
    base = os.environ.get("IG_GRAPH_URL", "https://graph.facebook.com/v23.0").rstrip("/")
    return base, os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]


def _enviar_direct(destinatario: dict, texto: str) -> None:
    base, usuario, token = _api()
    requisitar("POST", f"{base}/{usuario}/messages?access_token={token}",
               json_corpo={"recipient": destinatario, "message": {"text": texto[:1000]}})


def _responder_comentario(comentario_id: str, texto: str) -> None:
    base, _, token = _api()
    requisitar("POST", f"{base}/{comentario_id}/replies",
               dados=urllib.parse.urlencode({"message": texto, "access_token": token}).encode())


def _conteudo_da_midia(con, media_id: str) -> dict | None:
    linha = con.execute(
        "SELECT c.* FROM publicacoes pb JOIN conteudos c ON c.id = pb.conteudo_id"
        " WHERE pb.plataforma = 'instagram' AND pb.id_externo = ? AND pb.status = 'ok'",
        (media_id,),
    ).fetchone()
    return conteudo_dict(linha) if linha else None


def produto_pedido(con, cfg: dict, media_id: str, texto: str) -> dict | None:
    """Qual produto o comentário pede, ou None se o comentário não pede link."""
    texto_n = personagens.normalizar(texto)
    conteudo = _conteudo_da_midia(con, media_id)
    if conteudo and "duelo" in conteudo["pacote"]:
        for personagem_id, produto_id in conteudo["pacote"]["duelo"].items():
            p = personagens.por_id(cfg, personagem_id)
            if p and personagens.normalizar(p["nome"].split()[0]) in texto_n:
                return produto_dict(con.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone())
    if not any(personagens.normalizar(palavra) in texto_n for palavra in cfg["respostas"]["palavras_link"]):
        return None
    if conteudo:
        return produto_dict(con.execute("SELECT * FROM produtos WHERE id = ?", (conteudo["produto_id"],)).fetchone())
    return None


def tratar_comentario(con, cfg: dict, valor: dict) -> None:
    autor = valor.get("from", {})
    if autor.get("id") == os.environ.get("IG_USER_ID"):
        return  # comentário do próprio perfil
    produto = produto_pedido(con, cfg, valor.get("media", {}).get("id", ""), valor.get("text", ""))
    if not produto or not atendimento.pode_responder(con, cfg, "instagram", autor.get("id", "")):
        return
    mensagem = atendimento.mensagem_link(cfg, produto, autor.get("username", ""))
    if not atendimento.registrar(con, "instagram", f"comentario:{valor['id']}", autor.get("id", ""),
                                 valor.get("text", ""), mensagem):
        return  # notificação repetida
    _enviar_direct({"comment_id": valor["id"]}, mensagem)
    if cfg["respostas"].get("resposta_publica"):
        _responder_comentario(valor["id"], cfg["respostas"]["resposta_publica"])


def tratar_mensagem(con, cfg: dict, ia: IA, evento: dict) -> None:
    mensagem = evento.get("message", {})
    remetente = evento.get("sender", {}).get("id", "")
    if mensagem.get("is_echo") or not mensagem.get("text") or remetente == os.environ.get("IG_USER_ID"):
        return
    if not atendimento.pode_responder(con, cfg, "instagram", remetente):
        return
    personagem = cfg["personagens"][0] if cfg["personagens"] else None
    resposta = atendimento.responder(con, cfg, ia, mensagem["text"], personagem)
    if atendimento.registrar(con, "instagram", f"mensagem:{mensagem.get('mid')}", remetente,
                             mensagem["text"], resposta):
        _enviar_direct({"id": remetente}, resposta)


def processar(cfg: dict, corpo: dict) -> None:
    con = conectar(cfg)
    ia = IA(cfg)
    for entrada in corpo.get("entry", []):
        for mudanca in entrada.get("changes", []):
            if mudanca.get("field") == "comments":
                try:
                    tratar_comentario(con, cfg, mudanca["value"])
                except (ErroPublicacao, KeyError) as e:
                    print(f"  ! comentário: {e}")
        for evento in entrada.get("messaging", []):
            try:
                tratar_mensagem(con, cfg, ia, evento)
            except (ErroPublicacao, KeyError) as e:
                print(f"  ! mensagem: {e}")
    con.close()


def assinatura_valida(corpo: bytes, assinatura: str, segredo: str) -> bool:
    esperado = "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, assinatura or "")


def rodar(cfg: dict, porta: int) -> None:
    token_verificacao = os.environ.get("IG_VERIFY_TOKEN")
    segredo = os.environ.get("IG_APP_SECRET")
    faltando = [n for n in ("IG_USER_ID", "IG_ACCESS_TOKEN", "IG_VERIFY_TOKEN", "IG_APP_SECRET") if not os.environ.get(n)]
    if faltando:
        raise SystemExit(f"Preencha no .env: {', '.join(faltando)}")

    class Webhook(BaseHTTPRequestHandler):
        def do_GET(self):
            # Verificação feita pela Meta ao cadastrar o webhook.
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("hub.mode") == ["subscribe"] and q.get("hub.verify_token") == [token_verificacao]:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(q["hub.challenge"][0].encode())
            else:
                self.send_response(403)
                self.end_headers()

        def do_POST(self):
            corpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if not assinatura_valida(corpo, self.headers.get("X-Hub-Signature-256", ""), segredo):
                self.send_response(403)
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            # Responde 200 na hora e processa em segundo plano (a Meta reenvia se demorar).
            threading.Thread(target=processar, args=(cfg, json.loads(corpo)), daemon=True).start()

        def log_message(self, *args):
            pass

    print(f"Webhook do Instagram ouvindo na porta {porta}. Ctrl+C para parar.")
    ThreadingHTTPServer(("0.0.0.0", porta), Webhook).serve_forever()

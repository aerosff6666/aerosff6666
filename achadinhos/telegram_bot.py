"""Bot do Telegram: tira dúvidas, manda links e dá boas-vindas no grupo.

No privado responde tudo. No grupo só responde quando é mencionado, quando
respondem a uma mensagem dele ou com /ofertas, para não poluir a conversa.
"""

import time

from achadinhos import atendimento
from achadinhos.db import conectar
from achadinhos.ia import IA
from achadinhos.publicar import ErroPublicacao, telegram


def _boas_vindas(cfg: dict) -> str:
    nomes = " e ".join(p["nome"] for p in cfg["personagens"])
    apresentacao = f"Aqui quem fala são {nomes}, personagens virtuais criados com IA." if nomes else ""
    return (f"Oi! {apresentacao}\n"
            "Me manda o nome de um produto que eu procuro o link, ou digita /ofertas pra ver os destaques.")


def _ofertas(con) -> str:
    linhas = [atendimento.linha_produto(dict(r)) for r in con.execute(
        "SELECT * FROM produtos WHERE status IN ('aprovado', 'usado') ORDER BY score DESC LIMIT 5")]
    if not linhas:
        return "Ainda não tenho ofertas cadastradas."
    return "🔥 Destaques de hoje:\n" + "\n".join(linhas) + "\n\n#publi links de afiliado."


def tratar(mensagem: dict, con, cfg: dict, ia: IA, bot: dict) -> str | None:
    """Decide a resposta para uma mensagem (ou None para ficar quieto)."""
    texto = (mensagem.get("text") or "").strip()
    chat = mensagem["chat"]
    privado = chat["type"] == "private"
    if mensagem.get("new_chat_members") and cfg["grupo"].get("boas_vindas"):
        nomes = ", ".join(m["first_name"] for m in mensagem["new_chat_members"] if not m.get("is_bot"))
        return f"Bem-vindo(a), {nomes}! 🎉 Aqui sai achadinho todo dia. Digita /ofertas pra ver os destaques." if nomes else None
    if not texto:
        return None
    comando = texto.split()[0].split("@")[0].lower()
    if comando == "/start":
        return _boas_vindas(cfg)
    if comando == "/ofertas":
        return _ofertas(con)
    mencionado = f"@{bot['username']}".lower() in texto.lower()
    resposta_ao_bot = (mensagem.get("reply_to_message") or {}).get("from", {}).get("id") == bot["id"]
    if not (privado or mencionado or resposta_ao_bot):
        return None
    usuario = str(mensagem.get("from", {}).get("id"))
    if not atendimento.pode_responder(con, cfg, "telegram", usuario):
        return None
    pergunta = texto.replace(f"@{bot['username']}", "").strip()
    personagem = cfg["personagens"][0] if cfg["personagens"] else None
    return atendimento.responder(con, cfg, ia, pergunta, personagem)


def rodar(cfg: dict) -> None:
    con = conectar(cfg)
    ia = IA(cfg)
    bot = telegram.chamar("getMe")
    print(f"Bot @{bot['username']} no ar. Ctrl+C para parar.")
    offset = 0
    while True:
        try:
            # Long polling: o Telegram segura a conexão até 50 s esperando mensagens novas.
            atualizacoes = telegram.chamar("getUpdates", espera_http=70, offset=offset,
                                           timeout=50, allowed_updates=["message"])
        except (ErroPublicacao, OSError) as e:
            print(f"  ! {e}; tentando de novo em 10 s")
            time.sleep(10)
            continue
        for atualizacao in atualizacoes:
            offset = atualizacao["update_id"] + 1
            mensagem = atualizacao.get("message")
            if not mensagem:
                continue
            resposta = tratar(mensagem, con, cfg, ia, bot)
            if not resposta:
                continue
            chave = f"{mensagem['chat']['id']}:{mensagem['message_id']}"
            usuario = str(mensagem.get("from", {}).get("id"))
            if atendimento.registrar(con, "telegram", chave, usuario, mensagem.get("text", ""), resposta):
                try:
                    telegram.enviar_mensagem(resposta, str(mensagem["chat"]["id"]),
                                             reply_to_message_id=mensagem["message_id"])
                except ErroPublicacao as e:
                    print(f"  ! {e}")

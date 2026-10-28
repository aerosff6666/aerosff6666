"""Cliente de IA (Claude). Sem credencial, o agente usa modelos de texto prontos."""

import json
import os

import anthropic


class RecusaIA(Exception):
    pass


class IA:
    def __init__(self, cfg: dict):
        self.modelo = cfg["ia"]["modelo"]
        self.esforco = cfg["ia"]["esforco"]
        self.ativa = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
        self.cliente = anthropic.Anthropic() if self.ativa else None

    def gerar_json(self, sistema: str, pedido: str, esquema: dict) -> dict:
        """Pede ao Claude uma resposta que segue exatamente o JSON Schema dado."""
        resposta = self.cliente.beta.messages.create(
            model=self.modelo,
            max_tokens=16000,
            system=sistema,
            messages=[{"role": "user", "content": pedido}],
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.esforco,
                "format": {"type": "json_schema", "schema": esquema},
            },
            # Se o modelo recusar o pedido, a API tenta de novo num modelo alternativo.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resposta.stop_reason == "refusal":
            raise RecusaIA(getattr(resposta.stop_details, "explanation", None) or "pedido recusado")
        if resposta.stop_reason == "max_tokens":
            raise RecusaIA("resposta cortada por limite de tokens")
        texto = next(b.text for b in resposta.content if b.type == "text")
        return json.loads(texto)

    def gerar_texto(self, sistema: str, mensagens: list[dict], max_tokens: int = 2000) -> str:
        """Resposta curta de atendimento (direct do Instagram, bot do Telegram)."""
        resposta = self.cliente.beta.messages.create(
            model=self.modelo,
            max_tokens=max_tokens,
            system=sistema,
            messages=mensagens,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resposta.stop_reason == "refusal":
            raise RecusaIA(getattr(resposta.stop_details, "explanation", None) or "pedido recusado")
        return "".join(b.text for b in resposta.content if b.type == "text").strip()

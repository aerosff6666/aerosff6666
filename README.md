# Agente de Achadinhos — TikTok Shop (afiliado)

Pipeline em 12 passos. Ele escolhe produtos do TikTok Shop com boa comissão e
faz o raio-x de cada um com IA. Depois escreve o roteiro e a legenda e monta o
vídeo vertical. Por fim, publica no TikTok, no Instagram Reels e num grupo de
achadinhos no Telegram.

Tudo é código aberto e roda de graça. A IA (Claude) é opcional e paga por uso.
Sem chave, o agente usa modelos de texto prontos.

---

## Vale a pena? (avaliação franca)

**A ideia é boa, mas o "100% automático" é a parte que mais derruba esse tipo de projeto.**

O que joga a favor:
- O TikTok Shop está no Brasil desde 2025 e paga comissão de afiliado sem você ter estoque.
- Vídeo curto de achadinho é um formato que vende e dá para produzir em escala.
- Um grupo próprio (Telegram/WhatsApp) é uma audiência que o algoritmo não tira de você.

O que joga contra, e como este projeto lida com cada ponto:

| Risco | Na prática | Como o projeto trata |
|---|---|---|
| **Conteúdo não original** | TikTok e Instagram tiram do alcance (For You / Explorar) vídeos repetidos, de banco de imagens ou "slideshow" genérico. Contas 100% automáticas costumam morrer em alcance. | Os vídeos gerados servem de **ponto de partida**. O que mais converte é você filmando o produto na mão ou gravando a própria voz (`narracao.modo = "arquivo"`). |
| **Link do produto no vídeo** | A API do TikTok **não anexa produto do TikTok Shop** (carrinho amarelo) ao post. | O modo padrão envia o vídeo como **rascunho** para o app. Você adiciona o produto e posta, o que leva uns 30 segundos por vídeo. |
| **Postagem automática no TikTok** | Até o app ser auditado pelo TikTok, posts via API ficam **privados**. | Modo `rascunho` funciona sem auditoria. O modo `direto` fica disponível depois. |
| **Requisitos de afiliado** | O TikTok exige idade mínima e número mínimo de seguidores para liberar o carrinho de afiliado. Os números mudam, então confira no app (Central do Criador → TikTok Shop). | Comece postando conteúdo sem link para crescer a conta. |
| **Publicidade e IA** | O CONAR e as plataformas exigem sinalizar publicidade (#publi) e conteúdo gerado/alterado por IA. | O aviso entra automaticamente em toda legenda. Ative o rótulo "conteúdo gerado por IA" ao postar. |
| **Promessas falsas** | Prometer o que o produto não entrega gera denúncia, devolução e banimento. | O prompt da IA proíbe inventar números, garantias, resultados de saúde e urgência falsa. |
| **Imagens de terceiros** | Usar fotos/vídeos de outros criadores sem autorização é violação de direito autoral. | Use fotos do vendedor (dentro das regras da loja) ou, melhor, as suas. |

**Recomendação:** automatize o trabalho chato (pesquisa, roteiro, edição, legenda,
agendamento, grupo) e deixe com você a aprovação e o toque final. É isso que
`aprovacao_manual = true` faz. Com 3 a 5 vídeos por dia e revisão humana, a
conta cresce sem cair nos filtros de spam.

---

## Os 12 passos

| # | Passo | Onde | Automático? |
|---|---|---|---|
| 1 | Definir nicho, público, tom e regras de corte | `config.toml` | configura uma vez |
| 2 | Coletar produtos (planilha CSV) | `achadinhos/coleta.py` | você atualiza a planilha |
| 3 | Filtrar e ranquear (preço, comissão, nota, vendas) | `achadinhos/ranking.py` | ✅ |
| 4 | Raio-X do produto: público, dor, benefícios, objeções, ângulo | `achadinhos/conteudo.py` | ✅ (IA) |
| 5 | Roteiro: gancho de 2 s, 3 a 5 cenas, CTA | `achadinhos/conteudo.py` | ✅ (IA) |
| 6 | Legenda + hashtags + aviso de publi | `achadinhos/conteudo.py` | ✅ |
| 7 | Narração (nenhuma, voz sintética ou a sua voz) | `achadinhos/narracao.py` | ✅ / você grava |
| 8 | Montagem do vídeo 9:16 (1080×1920) com texto na tela | `achadinhos/video.py` | ✅ (ffmpeg) |
| 9 | Fila de aprovação | `achadinhos aprovar` | 👤 você |
| 10 | TikTok: rascunho no app (você adiciona o produto e posta) | `achadinhos/publicar/tiktok.py` | ✅ + 👤 |
| 11 | Instagram Reels | `achadinhos/publicar/instagram.py` | ✅ |
| 12 | Grupo de achadinhos no Telegram + relatório | `achadinhos/publicar/telegram.py` | ✅ |

---

## Instalação

Requisitos: Python 3.11+ e [ffmpeg](https://ffmpeg.org/download.html).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # adicione ,voz para a voz sintética: ".[dev,voz]"
cp .env.example .env               # preencha só o que for usar
```

## Uso

```bash
python -m achadinhos importar dados/produtos_exemplo.csv   # passo 2
python -m achadinhos ranquear                               # passo 3
python -m achadinhos gerar --quantidade 3                   # passos 4 a 8
python -m achadinhos listar                                 # veja saida/<id>/video.mp4
python -m achadinhos aprovar 1 2                            # passo 9
python -m achadinhos publicar --simular                     # confere antes de enviar
python -m achadinhos publicar                               # passos 10 a 12
python -m achadinhos relatorio
```

Cada conteúdo fica em `saida/<id>/` com `video.mp4`, `legenda.txt` e `roteiro.json`
(raio-x completo).

### A planilha de produtos (passo 2)

O TikTok Shop não tem API pública de catálogo para afiliados. Por isso, monte a
planilha a partir do **Centro de Afiliados**, no app ou em
`affiliate.tiktok.com`: copie o link de afiliado de cada produto que achar bom.
Colunas aceitas (veja `dados/produtos_exemplo.csv`):

| coluna | obrigatória | exemplo |
|---|---|---|
| `titulo` | sim | Mini processador elétrico USB |
| `preco` | sim | `39,90` ou `39.90` |
| `comissao_pct` | sim | `15` |
| `url_afiliado` | sim | seu link de afiliado |
| `vendas`, `nota`, `categoria` | não | `4200`, `4.7`, `cozinha` |
| `imagens` | não | URLs ou caminhos separados por `\|` |

Sem imagens, o vídeo sai com fundo colorido e o texto na tela.

### Agendar (rodar sozinho)

```cron
# todo dia às 7h: gera 3 vídeos novos e deixa na fila de aprovação
0 7 * * * cd /caminho/do/projeto && .venv/bin/python -m achadinhos rodar --quantidade 3
```

Com `aprovacao_manual = false`, o `rodar` também publica sem esperar você. Não
recomendamos isso até a conta estar madura.

---

## Credenciais (todas gratuitas, menos a IA)

**IA (opcional).** Crie uma chave em [console.anthropic.com](https://console.anthropic.com) e coloque em `ANTHROPIC_API_KEY`.
O modelo e o esforço ficam em `config.toml` → `[ia]`. Se o modelo recusar um
pedido, a API repete a chamada num modelo alternativo (`fallbacks: "default"`).
Se ainda assim falhar, o agente usa o modelo de texto pronto.

**TikTok.** Crie um app em [developers.tiktok.com](https://developers.tiktok.com), adicione o produto
*Content Posting API* e peça o escopo `video.upload` (rascunho) ou
`video.publish` (direto). Gere o token de acesso do usuário via Login Kit e
coloque em `TIKTOK_ACCESS_TOKEN`. O token expira, então renove pelo refresh token.

**Instagram.** A conta precisa ser **Profissional** (Criador ou Empresa) e estar ligada a uma
Página do Facebook. Crie um app em [developers.facebook.com](https://developers.facebook.com) com a
*Instagram Graph API* e as permissões `instagram_basic` e `instagram_content_publish`.
Preencha `IG_USER_ID` e `IG_ACCESS_TOKEN`. A API baixa o vídeo de uma **URL pública**:
- rode `python -m achadinhos exportar pasta_publica/`;
- sincronize essa pasta com um bucket público (Cloudflare R2, S3, GCS…);
- coloque o endereço em `publicacao.url_publica_base`.

**Telegram (o grupo de achadinhos).**
1. Crie o bot com o [@BotFather](https://t.me/BotFather) e copie o token para `TELEGRAM_BOT_TOKEN`.
2. Adicione o bot ao grupo ou canal como administrador.
3. Pegue o `chat_id` (ex.: `-100123...`): envie uma mensagem no grupo e abra
   `https://api.telegram.org/bot<TOKEN>/getUpdates`. Coloque o valor em `TELEGRAM_CHAT_ID`.

Cada post leva o vídeo, a legenda e o link de afiliado.

**WhatsApp.** Não está incluído. A API oficial (Cloud API) é paga por conversa
e não foi feita para grupos. Bibliotecas não oficiais violam os termos e levam a
banimento do número. Para WhatsApp, use um **Canal** e poste manualmente o que já
saiu no Telegram.

---

## Testes

```bash
python -m pytest -q
```

## Próximos passos sugeridos

- Ler as métricas dos vídeos (TikTok Display API / Instagram Insights) e devolver
  ao ranking quais nichos e ganchos convertem.
- Gerar 2 ou 3 ganchos por produto e testar qual performa melhor (teste A/B).
- Painel web simples para aprovar vídeos pelo celular.

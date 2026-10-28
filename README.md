# Agente de Achadinhos — TikTok Shop (afiliado)

Pipeline em 12 passos. Ele escolhe produtos do TikTok Shop com boa comissão e
faz o raio-x de cada um com IA. Dois personagens virtuais, **Bia Brilho** e
**Rafa Raio-X**, apresentam os vídeos. O sistema publica no TikTok, no
Instagram Reels e num grupo de achadinhos no Telegram, responde quem comenta
"EU QUERO", roda campanhas no grupo e aprende com as vendas quais categorias
dão mais comissão.

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
| 1 | Nicho, regras de corte e os dois personagens | `config.toml`, `personagens.toml` | configura uma vez |
| 2 | Coletar produtos (planilha CSV) | `achadinhos/coleta.py` | você atualiza a planilha |
| 3 | Filtrar e ranquear, com peso extra para categorias que já venderam | `achadinhos/ranking.py` | ✅ |
| 4 | Raio-X do produto: público, dor, benefícios, objeções, ângulo e formato | `achadinhos/conteudo.py` | ✅ (IA) |
| 5 | Roteiro na voz do personagem (ou duelo Bia x Rafa) | `achadinhos/conteudo.py` | ✅ (IA) |
| 6 | Legenda + hashtags + #publi + selo de personagem IA | `achadinhos/conteudo.py` | ✅ |
| 7 | Narração com a voz de cada personagem | `achadinhos/narracao.py` | ✅ |
| 8 | Vídeo 9:16 com as cores do personagem, ou avatar falante (HeyGen) | `achadinhos/video.py`, `achadinhos/avatar.py` | ✅ |
| 9 | Fila de aprovação (pode desligar) | `achadinhos aprovar` | 👤 ou ✅ |
| 10 | TikTok: rascunho no app (você adiciona o produto e posta) | `achadinhos/publicar/tiktok.py` | ✅ + 👤 30 s |
| 11 | Instagram Reels + robô "comenta EU QUERO" → link no direct | `achadinhos/publicar/instagram.py`, `achadinhos/instagram_bot.py` | ✅ |
| 12 | Grupo do Telegram: vídeos, bot que responde, ofertas e enquetes; vendas voltam para o ranking | `achadinhos/telegram_bot.py`, `achadinhos/campanhas.py` | ✅ |

---|---|---|---|
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

## Os personagens

Estão em `personagens.toml`, com nome, bio, personalidade, bordões, formatos de
vídeo, cor, voz e a descrição visual para criar o avatar.

| | Bia Brilho ✨ | Rafa Raio-X 🔎 |
|---|---|---|
| Jeito | Energia alta, dramática, "a amiga que acha tudo antes" | Calmo, irônico, "faz o raio-x" da ficha técnica |
| Bordões | "Para tudo que a Bia achou!" / "Tá no carrinho, depois me conta!" | "Bora pro raio-x!" / "Raio-x feito. O resto é com você" |
| Categorias | beleza, moda, acessórios, casa, cozinha, decoração | eletrônicos, gadgets, ferramentas, pets, automotivo, esporte |
| Cor / voz | rosa `#FF2D87` / Francisca | azul `#00B7FF` / Antonio |

O produto vai para o personagem dono da categoria. Categorias sem dono são
divididas entre os dois. Para mudar nomes, jeito ou categorias, edite o arquivo.

**Regras de transparência (já embutidas):**
- todo vídeo leva a faixa "personagem virtual (IA)";
- a legenda leva "🤖 Personagem virtual criado com IA";
- a IA está proibida de fazer o personagem dizer que usou ou testou o produto.

Ao postar no TikTok, ative também o rótulo "conteúdo gerado por IA".

**Duelo (engajamento de verdade).** `python -m achadinhos duelo` gera um vídeo
em que cada personagem defende um produto. A chamada final pede para comentar
**BIA** ou **RAFA**. No Instagram, o robô manda no direct o link do produto
escolhido.

**Avatar falante (opcional, pago).**
1. Crie cada personagem no [HeyGen](https://www.heygen.com) a partir do campo `visual`.
2. Copie o `heygen_avatar_id` e o `heygen_voice_id` para o `personagens.toml`.
3. Coloque `HEYGEN_API_KEY` no `.env`.

Os vídeos passam a ter o personagem falando, com a foto do produto em destaque.
Sem isso, o vídeo usa as fotos do produto, o texto na tela e a voz do personagem
(`narracao.modo = "edge-tts"`).

## A planilha de produtos (passo 2)

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

## Atendimento, grupo e campanhas

```bash
python -m achadinhos telegram-bot              # bot: responde dúvidas e manda links (fica rodando)
python -m achadinhos instagram-bot --porta 8080  # comenta "EU QUERO" → link no direct (fica rodando)
python -m achadinhos campanha oferta           # oferta do dia no grupo (não repete por 7 dias)
python -m achadinhos campanha enquete          # "qual achadinho vocês querem amanhã?"
python -m achadinhos campanha convite          # textos de bio, comentário fixado e stories
python -m achadinhos importar-vendas vendas.csv  # vendas do Centro de Afiliados → ranking aprende
```

- **Bot do Telegram.**
  - No privado, responde tudo.
  - No grupo, só fala quando é mencionado, quando respondem a ele ou com
    `/ofertas`, para não poluir a conversa. Também dá boas-vindas a quem entra.
- **Robô do Instagram.**
  - Responde só quem comentou ou mandou mensagem, como manda a regra da Meta.
  - Manda uma mensagem por comentário, com limite diário por pessoa
    (`respostas.max_por_pessoa_dia`).
- **Aprendizado.**
  - Categorias que deram comissão ganham até +20% no ranking.
  - As que ainda não venderam perdem 20%.
  - Cerca de 20% dos vídeos continuam testando categorias novas.
- **Planilha de vendas.**
  - Colunas: `pedido`, `link` (ou `titulo`), `comissao`, `data`.
  - Com o número do pedido, reimportar a mesma planilha não duplica vendas.

## Deixar tudo no automático (servidor)

Use uma VPS Linux (ex.: R$ 25–50/mês) com Python e ffmpeg. Para o robô do
Instagram, ela precisa de um domínio com HTTPS: use Caddy ou Nginx na frente da
porta 8080 e cadastre `https://seu-dominio/` como webhook no app da Meta, com
os campos `comments` e `messages`.

Rotina diária sugerida (`crontab -e`):

```cron
# 7h: gera 3 vídeos (vão para aprovação, ou direto se aprovacao_manual = false)
0 7 * * *  cd /opt/achadinhos && .venv/bin/python -m achadinhos rodar --quantidade 3
# terças e sextas, 8h: um duelo Bia x Rafa
0 8 * * 2,5 cd /opt/achadinhos && .venv/bin/python -m achadinhos duelo
# 12h e 19h: oferta no grupo
0 12,19 * * * cd /opt/achadinhos && .venv/bin/python -m achadinhos campanha oferta
# 21h: enquete no grupo
0 21 * * *  cd /opt/achadinhos && .venv/bin/python -m achadinhos campanha enquete
# a cada 2h: publica o que estiver aprovado
0 */2 * * * cd /opt/achadinhos && .venv/bin/python -m achadinhos publicar
```

Os dois bots ficam rodando como serviço. Exemplo de
`/etc/systemd/system/achadinhos-telegram.service`; faça um igual para o
`instagram-bot`:

```ini
[Service]
WorkingDirectory=/opt/achadinhos
ExecStart=/opt/achadinhos/.venv/bin/python -m achadinhos telegram-bot
Restart=always

[Install]
WantedBy=multi-user.target
```

Recomendamos manter `aprovacao_manual = true` nas primeiras 2 semanas. Depois
que o tom dos vídeos estiver bom, troque para `false` e tudo passa a sair
sozinho. Só o carrinho do TikTok continua com você.

---

## Credenciais (todas gratuitas, menos a IA)

**IA (opcional, recomendada para os personagens).** Crie uma chave em [console.anthropic.com](https://console.anthropic.com) e coloque em `ANTHROPIC_API_KEY`.
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
Para o robô de comentários e direct, peça também `instagram_manage_comments` e
`instagram_manage_messages`, e preencha `IG_VERIFY_TOKEN` e `IG_APP_SECRET`.
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

## Custos

| Item | Custo |
|---|---|
| Código, ffmpeg, voz edge-tts, Telegram, APIs do TikTok e do Instagram | grátis |
| VPS para rodar 24 h | ~R$ 25–50/mês |
| IA (Claude) para roteiros e respostas | centavos por vídeo/conversa |
| Avatar falante (HeyGen) | plano pago deles (opcional) |

## Próximos passos sugeridos

- Ler as métricas dos vídeos (Instagram Insights) e devolver ao ranking quais
  ganchos convertem.
- Gerar 2 ou 3 ganchos por produto e testar qual performa melhor (teste A/B).
- Painel web simples para aprovar vídeos pelo celular.

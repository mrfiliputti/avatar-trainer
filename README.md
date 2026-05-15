# Gerador de Treinamento em Vídeo com Azure Avatar

> ⚠️ **Aviso:** este repositório é um **código de exemplo / prova de conceito**, fornecido apenas
> para fins didáticos e de demonstração da API de Batch Avatar Synthesis do Azure AI Speech.
> **Não é um produto pronto para produção** — não há garantias de estabilidade, segurança,
> tratamento robusto de erros, testes automatizados ou suporte. Use por sua conta e risco e
> revise/adapte antes de qualquer uso real.

Aplicação em Python que:

1. Carrega **slides já existentes** (imagens PNG/JPG) de um diretório.
2. Lê um arquivo de **Speaker Notes** (`SLIDE N` / `Speaker Notes` / texto).
3. Para cada slide, chama o **Azure AI Speech – Batch Avatar Synthesis** (REST) e baixa o **MP4 do avatar**.
4. **Compõe o vídeo final** (`moviepy` + `ffmpeg`) sobrepondo o avatar no canto do slide e concatena tudo em um único `.mp4`.

```
slides/*.png + notes.txt ──► avatar/*.mp4 ──► treinamento.mp4
```

## Pré-requisitos

- Python 3.10+
- [`ffmpeg`](https://ffmpeg.org/) no PATH (necessário para o `moviepy`)
- Recurso **Azure AI Speech** com Avatar habilitado (regiões suportadas: `westus2`, `westeurope`, `southeastasia`, etc.)

## Instalação

```powershell
cd c:\work\avatar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edite o .env com seu endpoint
```

## Formato do arquivo de notas

```
SLIDE 1
Speaker Notes
Texto narrado para o slide 1.
Pode ter várias linhas e parágrafos separados por linha em branco.

SLIDE 2
Speaker Notes
Texto narrado para o slide 2.
```

Regras:
- Cabeçalho `SLIDE N` (case-insensitive) inicia um bloco. `N` é o índice do slide (1-based).
- A linha `Speaker Notes` logo abaixo é descartada (apenas marcador).
- O restante até o próximo `SLIDE N` é a narração enviada ao Azure Speech.
- Slides sem bloco correspondente são **pulados** no avatar (com aviso).

Veja [notes.txt](notes.txt).

## Slides

Coloque as imagens em qualquer pasta (ex.: `slides/`):

```
slides/
├── slide1.png
├── slide2.png
├── slide3.png
└── …
```

São aceitas extensões: `.png .jpg .jpeg .bmp .webp`. A ordenação é **natural** (`slide2` vem antes de `slide10`).

## Uso

```powershell
# Pipeline completo (slides + notas → vídeo)
python -m src.main --slides-dir slides --notes notes.txt --out output

# Só valida pareamento (sem chamar Azure)
python -m src.main --slides-dir slides --notes notes.txt --skip-avatar

# Avatar mas sem montar vídeo final
python -m src.main --slides-dir slides --notes notes.txt --skip-video

# Posição do avatar e nome do vídeo
python -m src.main --slides-dir slides --notes notes.txt --avatar-position bottom-left --name fundamentos_ia
```

Saída em `output/`:

```
output/
├── avatar/avatar_01.mp4 …
└── treinamento.mp4   ← vídeo final
```

## Variáveis de ambiente (`.env`)

| Variável | Descrição | Exemplo |
|---|---|---|
| `SPEECH_ENDPOINT`         | Endpoint do recurso Speech (use domínio customizado p/ passwordless) | `https://my-res.cognitiveservices.azure.com` |
| `PASSWORDLESS`            | `true` usa `DefaultAzureCredential` (Azure CLI / MI). `false` usa `SPEECH_KEY`. | `true` |
| `SPEECH_KEY`              | Chave de assinatura (apenas se `PASSWORDLESS=false`) | `xxxxxxxx` |
| `AZURE_TTS_VOICE`         | Voz neural                                          | `en-US-Ava:DragonHDLatestNeural` |
| `AZURE_AVATAR_CHARACTER`  | Personagem do avatar                                | `Lisa`     |
| `AZURE_AVATAR_STYLE`      | Estilo                                              | `casual-sitting` |
| `AZURE_AVATAR_BACKGROUND` | Cor RGBA hex ou `transparent`                       | `#FFFFFFFF` |
| `AZURE_AVATAR_BACKGROUND_IMAGE` | URL https de imagem de fundo (opcional)       | `https://…/bg.jpg` |
| `AZURE_AVATAR_VIDEO_FORMAT`     | `mp4` ou `webm` (webm para transparente)      | `mp4` |
| `AZURE_AVATAR_VIDEO_CODEC`      | `h264`, `hevc` ou `vp9` (vp9 para transparente)| `h264` |
| `AZURE_AVATAR_CUSTOMIZED`        | Avatar customizado                            | `false` |
| `AZURE_AVATAR_USE_BUILT_IN_VOICE`| Voice sync para avatar customizado            | `false` |

> **Passwordless**: faça `az login` antes de rodar. Sua conta precisa do papel **Cognitive Services User** (ou **Cognitive Services Speech User**) no recurso de Speech, e o endpoint deve usar **domínio customizado**.

> Personagens e estilos suportados: consulte a [documentação oficial](https://learn.microsoft.com/azure/ai-services/speech-service/text-to-speech-avatar/avatar-gestures-with-ssml).

## Estrutura

```
src/
├── slides_loader.py      # carrega imagens dos slides
├── notes_parser.py       # parser das notas (blocos SLIDE N)
├── avatar_synthesizer.py # cliente REST do Batch Avatar Synthesis
├── video_composer.py     # composição com moviepy
└── main.py               # CLI
```

## Notas

- A API de Avatar é **assíncrona**: o cliente faz `PUT` para criar o job, faz polling do status e baixa o MP4 quando `Succeeded`.
- Os MP4s do avatar ficam em cache em `output/avatar/`. Se já existirem, são reutilizados (útil para reprocessar só o vídeo final).
- Para fundo transparente, use `AZURE_AVATAR_BACKGROUND=transparent`, `AZURE_AVATAR_VIDEO_FORMAT=webm` e `AZURE_AVATAR_VIDEO_CODEC=vp9`.
- A autenticação **passwordless** é a recomendada: faça `az login` localmente; em produção, atribua uma Managed Identity ao recurso e dê o papel "Cognitive Services User" no recurso de Speech.

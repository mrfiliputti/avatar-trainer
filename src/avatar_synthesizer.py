"""Cliente para Azure Speech – Batch Avatar Synthesis (REST).

Adaptado da amostra oficial:
  https://learn.microsoft.com/azure/ai-services/speech-service/batch-synthesis-avatar

Autenticação:
  * Passwordless (recomendado) via azure-identity / DefaultAzureCredential.
    Requer endpoint com domínio customizado
    (`https://<custom>.cognitiveservices.azure.com`) e que a identidade tenha
    o papel "Cognitive Services User" ou "Cognitive Services Speech User".
  * Chave de assinatura (fallback) via `SPEECH_KEY`.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

API_VERSION = "2024-08-01"


class AvatarSynthesizer:
    def __init__(
        self,
        endpoint: str,
        *,
        subscription_key: Optional[str] = None,
        passwordless: bool = True,
        tenant_id: Optional[str] = None,
        voice: str = "en-US-Ava:DragonHDLatestNeural",
        character: str = "Lisa",
        style: str = "casual-sitting",
        background_color: str = "#FFFFFFFF",
        background_image: Optional[str] = None,
        video_format: str = "mp4",
        video_codec: str = "h264",
        subtitle_type: str = "soft_embedded",
        customized: bool = False,
        photo_avatar_base_model: str = "",
        use_built_in_voice: bool = False,
        custom_voices: Optional[dict] = None,
    ) -> None:
        if not endpoint:
            raise ValueError("SPEECH_ENDPOINT é obrigatório.")
        if not passwordless and not subscription_key:
            raise ValueError("SPEECH_KEY é obrigatória quando passwordless=False.")

        self.endpoint = endpoint.rstrip("/")
        self.subscription_key = subscription_key
        self.passwordless = passwordless
        self.tenant_id = tenant_id
        self.voice = voice
        self.character = character
        self.style = style
        self.background_color = background_color
        self.background_image = background_image
        self.video_format = video_format
        self.video_codec = video_codec
        self.subtitle_type = subtitle_type
        self.customized = customized
        self.photo_avatar_base_model = photo_avatar_base_model
        self.use_built_in_voice = use_built_in_voice
        self.custom_voices = custom_voices or {}

        self._credential = None  # lazy DefaultAzureCredential
        self._base_url = f"{self.endpoint}/avatar/batchsyntheses"

    # --------------------------------------------------------------- auth ---
    def _authenticate(self) -> dict:
        if self.passwordless:
            from azure.identity import DefaultAzureCredential  # lazy import

            if self._credential is None:
                kwargs = {}
                if self.tenant_id:
                    # Restringe a aquisição de token ao tenant correto
                    # (resolve "Tenant provided in token does not match resource tenant")
                    kwargs["interactive_browser_tenant_id"] = self.tenant_id
                    kwargs["shared_cache_tenant_id"] = self.tenant_id
                    kwargs["visual_studio_code_tenant_id"] = self.tenant_id
                    kwargs["workload_identity_tenant_id"] = self.tenant_id
                    kwargs["additionally_allowed_tenants"] = [self.tenant_id]
                self._credential = DefaultAzureCredential(**kwargs)
            token = self._credential.get_token("https://cognitiveservices.azure.com/.default")
            return {"Authorization": f"Bearer {token.token}"}
        return {"Ocp-Apim-Subscription-Key": self.subscription_key or ""}

    # ------------------------------------------------------- core REST API --
    @staticmethod
    def create_job_id() -> str:
        return str(uuid.uuid4())

    def submit(self, text: str, job_id: Optional[str] = None) -> str:
        job_id = job_id or self.create_job_id()
        url = f"{self._base_url}/{job_id}?api-version={API_VERSION}"
        headers = {"Content-Type": "application/json", **self._authenticate()}

        avatar_config = {
            "talkingAvatarCharacter": self.character,
            "talkingAvatarStyle": self.style,
            "photoAvatarBaseModel": self.photo_avatar_base_model,
            "customized": self.customized,
            "videoFormat": self.video_format,
            "videoCodec": self.video_codec,
            "subtitleType": self.subtitle_type,
            "useBuiltInVoice": self.use_built_in_voice,
        }
        if self.background_image:
            avatar_config["backgroundImage"] = self.background_image
        else:
            avatar_config["backgroundColor"] = self.background_color

        payload = {
            "synthesisConfig": {"voice": self.voice},
            "customVoices": self.custom_voices,
            "inputKind": "PlainText",
            "inputs": [{"content": text}],
            "avatarConfig": avatar_config,
        }

        response = requests.put(url, data=json.dumps(payload), headers=headers, timeout=60)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Falha ao submeter avatar [{response.status_code}]: {response.text}"
            )
        logger.info("Batch avatar synthesis job submitted: %s", job_id)
        return job_id

    def get_status(self, job_id: str) -> dict:
        url = f"{self._base_url}/{job_id}?api-version={API_VERSION}"
        response = requests.get(url, headers=self._authenticate(), timeout=60)
        if response.status_code >= 400:
            raise RuntimeError(f"Falha ao consultar job: {response.text}")
        return response.json()

    def wait_for(self, job_id: str, poll_sec: int = 5, timeout_sec: int = 1800) -> dict:
        start = time.time()
        while True:
            data = self.get_status(job_id)
            status = data.get("status")
            if status == "Succeeded":
                return data
            if status == "Failed":
                raise RuntimeError(f"Job {job_id} falhou: {data}")
            if time.time() - start > timeout_sec:
                raise TimeoutError(f"Timeout aguardando job {job_id}")
            logger.info("Job %s status: %s", job_id, status)
            time.sleep(poll_sec)

    def download_result(self, job_data: dict, dest: Path) -> Path:
        result_url = job_data.get("outputs", {}).get("result")
        if not result_url:
            raise RuntimeError(f"Sem URL de resultado em {job_data}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(result_url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return dest

    def list_jobs(self, skip: int = 0, max_page_size: int = 100) -> dict:
        url = (
            f"{self._base_url}?api-version={API_VERSION}"
            f"&skip={skip}&maxpagesize={max_page_size}"
        )
        response = requests.get(url, headers=self._authenticate(), timeout=60)
        response.raise_for_status()
        return response.json()

    # ----------------------------------------------------------- helpers ---
    def synthesize_to_file(self, text: str, dest: Path, log=logger.info) -> Path:
        log(f"  → submetendo job de avatar ({len(text)} chars)…")
        job_id = self.submit(text)
        log(f"  → job_id={job_id}, aguardando conclusão…")
        data = self.wait_for(job_id)
        log("  → baixando vídeo…")
        return self.download_result(data, dest)


def synthesize_for_slides(
    narrations: List[str],
    out_dir: Path,
    synth: AvatarSynthesizer,
    log=print,
) -> List[Path]:
    """Sintetiza um vídeo de avatar para cada narração.

    O cache é validado por sidecar `.txt` com a narração exata: se o texto
    mudar, o vídeo é regerado.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    ext = synth.video_format
    for i, text in enumerate(narrations, start=1):
        log(f"[Avatar] Slide {i}/{len(narrations)}")
        dest = out_dir / f"avatar_{i:02d}.{ext}"
        sidecar = dest.with_suffix(".txt")

        cached_text = sidecar.read_text(encoding="utf-8") if sidecar.exists() else None
        if dest.exists() and dest.stat().st_size > 0 and cached_text == text:
            log(f"  → cache hit: {dest.name}")
        else:
            if dest.exists():
                log("  → cache invalidado (narração mudou), regerando…")
                dest.unlink()
            synth.synthesize_to_file(text, dest, log=log)
            sidecar.write_text(text, encoding="utf-8")
        files.append(dest)
    return files


def from_env() -> AvatarSynthesizer:
    """Constrói o sintetizador a partir de variáveis de ambiente.

    Variáveis principais:
        SPEECH_ENDPOINT   (obrigatória) ex.: https://my-resource.cognitiveservices.azure.com
        SPEECH_KEY        (opcional, se PASSWORDLESS=false)
        PASSWORDLESS      (opcional, default 'true')
        AZURE_TTS_VOICE
        AZURE_AVATAR_CHARACTER
        AZURE_AVATAR_STYLE
        AZURE_AVATAR_BACKGROUND        (cor RGBA hex ou 'transparent')
        AZURE_AVATAR_BACKGROUND_IMAGE  (URL https; tem prioridade sobre a cor)
        AZURE_AVATAR_VIDEO_FORMAT      (mp4 | webm)
        AZURE_AVATAR_VIDEO_CODEC       (h264 | hevc | vp9)
        AZURE_AVATAR_CUSTOMIZED        (true|false)
        AZURE_AVATAR_USE_BUILT_IN_VOICE (true|false)
    """

    def _bool(v: Optional[str], default: bool) -> bool:
        if v is None:
            return default
        return v.strip().lower() in ("1", "true", "yes", "on")

    return AvatarSynthesizer(
        endpoint=os.environ.get("SPEECH_ENDPOINT", ""),
        subscription_key=os.environ.get("SPEECH_KEY"),
        passwordless=_bool(os.environ.get("PASSWORDLESS"), True),
        tenant_id=os.environ.get("AZURE_TENANT_ID") or None,
        voice=os.environ.get("AZURE_TTS_VOICE", "en-US-Ava:DragonHDLatestNeural"),
        character=os.environ.get("AZURE_AVATAR_CHARACTER", "Lisa"),
        style=os.environ.get("AZURE_AVATAR_STYLE", "casual-sitting"),
        background_color=os.environ.get("AZURE_AVATAR_BACKGROUND", "#FFFFFFFF"),
        background_image=os.environ.get("AZURE_AVATAR_BACKGROUND_IMAGE") or None,
        video_format=os.environ.get("AZURE_AVATAR_VIDEO_FORMAT", "mp4"),
        video_codec=os.environ.get("AZURE_AVATAR_VIDEO_CODEC", "h264"),
        customized=_bool(os.environ.get("AZURE_AVATAR_CUSTOMIZED"), False),
        use_built_in_voice=_bool(os.environ.get("AZURE_AVATAR_USE_BUILT_IN_VOICE"), False),
    )

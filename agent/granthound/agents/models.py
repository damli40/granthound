"""Bedrock model factories. max_tokens is always explicit (an unset value
reserves the model's maximum against the account's tokens-per-minute quota
and is the usual cause of a ThrottlingException on a workload this small);
temperature is 0; the boto client retries adaptively."""

from botocore.config import Config
from strands.models.bedrock import BedrockModel

from granthound.config import Settings

HAIKU_MAX_TOKENS = 1500
ANALYST_MAX_TOKENS = 2500


def _client_config() -> Config:
    return Config(retries={"mode": "adaptive", "total_max_attempts": 5}, read_timeout=120)


def haiku(settings: Settings, *, max_tokens: int = HAIKU_MAX_TOKENS) -> BedrockModel:
    return BedrockModel(
        model_id=settings.haiku_model_id,
        region_name=settings.region,
        max_tokens=max_tokens,
        temperature=0,
        boto_client_config=_client_config(),
    )


def analyst_model(settings: Settings, *, max_tokens: int = ANALYST_MAX_TOKENS) -> BedrockModel:
    return BedrockModel(
        model_id=settings.analyst_model_id,
        region_name=settings.region,
        max_tokens=max_tokens,
        temperature=0,
        boto_client_config=_client_config(),
    )


def model_id_of(executor) -> str:
    """The model id an executor will bill to -- read from the Strands model
    config for real Agents, from a `model_id` attribute for test doubles."""
    model = getattr(executor, "model", None)
    config = getattr(model, "config", None)
    if isinstance(config, dict) and config.get("model_id"):
        return str(config["model_id"])
    return str(getattr(executor, "model_id", "unknown"))

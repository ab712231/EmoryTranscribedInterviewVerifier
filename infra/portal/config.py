from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_ENVS = ("dev", "prod")

REQUIRED_FIELDS = (
    "envName",
    "region",
    "stackPrefix",
    "allowedOrigins",
    "sesFromAddress",
    "manageSesIdentity",
    "studyTeamAddress",
    "kmsKeyAlias",
)


@dataclass(frozen=True)
class PortalConfig:
    env_name: str
    region: str
    stack_prefix: str
    allowed_origins: list[str]
    ses_from_address: str
    manage_ses_identity: bool
    study_team_address: str
    kms_key_alias: str


def default_config_dir():
    return Path(__file__).resolve().parent.parent / "config"


def load_config(env_name, config_dir: Path | None = None) -> PortalConfig:
    if env_name not in SUPPORTED_ENVS:
        raise ValueError(
            f'Unknown env "{env_name}". Pass one of: {", ".join(SUPPORTED_ENVS)} '
            f"(e.g. cdk synth -c env=dev)."
        )

    directory = config_dir or default_config_dir()
    config_path = directory / f"{env_name}.json"
    if not config_path.exists():
        raise ValueError(f'Config file not found for env "{env_name}": {config_path}')

    raw = json.loads(config_path.read_text(encoding="utf-8"))

    missing = []
    for key in REQUIRED_FIELDS:
        value = raw.get(key)
        if value is None or value == [] or (isinstance(value, str) and not value.strip()):
            missing.append(key)
    if missing:
        raise ValueError(
            f'Config for env "{env_name}" is missing {", ".join(missing)}. '
            f"Type them into infra/config/{env_name}.json."
        )

    if raw.get("envName") != env_name:
        raise ValueError(
            f'Config envName "{raw.get("envName")}" does not match requested '
            f'env "{env_name}".'
        )

    return PortalConfig(
        env_name=raw["envName"],
        region=raw["region"],
        stack_prefix=raw["stackPrefix"],
        allowed_origins=list(raw["allowedOrigins"]),
        ses_from_address=raw["sesFromAddress"],
        manage_ses_identity=bool(raw["manageSesIdentity"]),
        study_team_address=raw["studyTeamAddress"],
        kms_key_alias=raw["kmsKeyAlias"],
    )

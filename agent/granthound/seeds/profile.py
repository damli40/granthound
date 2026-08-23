"""The org profile + seed list (maya.yml) as typed data.

yaml.safe_load turns `start: 2026-09-01` into a datetime.date; DynamoDB
cannot store that, and the rest of the pipeline compares ISO strings, so
dates are converted to ISO strings at the edge (before validation).
"""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator, model_validator

DEFAULT_SEED_PATH = Path(__file__).with_name("maya.yml")

_POINTER_FIELDS = ("verdict", "fit_score", "latest_eval_sk", "latest_snapshot_sha")


class CommitmentWindow(BaseModel):
    label: str
    start: str
    end: str

    @field_validator("start", "end", mode="before")
    @classmethod
    def _date_to_iso(cls, value):
        return value.isoformat() if isinstance(value, date) else value


class OrgProfile(BaseModel):
    name: str
    profile: str
    commitment_windows: list[CommitmentWindow] = []


class Seed(BaseModel):
    id: str
    url: str
    funder: str
    source_type: str
    is_fixture: bool = False


class SeedFile(BaseModel):
    org: OrgProfile
    seeds: list[Seed]

    @model_validator(mode="after")
    def _unique_ids(self):
        seen: set[str] = set()
        for seed in self.seeds:
            if seed.id in seen:
                raise ValueError(f"duplicate seed id: {seed.id}")
            seen.add(seed.id)
        return self


def load_seed_file(path: Path = DEFAULT_SEED_PATH) -> SeedFile:
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return SeedFile.model_validate(data)


def build_meta_item(seed: Seed, org_name: str, existing: dict | None, seeded_at: str) -> dict:
    """The META item for a seed. Re-seeding keeps the run-written pointer
    fields (verdict, fit_score, latest_*) so a seed-file edit never erases
    what the pipeline has learned about the program."""
    item = {
        "program_id": seed.id,
        "url": seed.url,
        "funder": seed.funder,
        "source_type": seed.source_type,
        "is_fixture": seed.is_fixture,
        "org": org_name,
        "seeded_at": seeded_at,
    }
    for field in _POINTER_FIELDS:
        if existing is not None and field in existing:
            item[field] = existing[field]
    return item

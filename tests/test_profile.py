from pathlib import Path

import pytest

from granthound.seeds.profile import DEFAULT_SEED_PATH, Seed, build_meta_item, load_seed_file

YAML = """
org:
  name: Riverbend Youth Collective
  profile: |
    501(c)(3) youth org in Columbus, OH.
  commitment_windows:
    - {label: fall program launch, start: 2026-09-01, end: 2026-09-20}
seeds:
  - id: a
    url: https://example.org/a
    funder: A Foundation
    source_type: community_foundation
    is_fixture: false
  - id: b
    url: https://example.org/b
    funder: B Corp
    source_type: corporate_giving
"""


def test_yaml_dates_become_iso_strings(tmp_path: Path):
    path = tmp_path / "seeds.yml"
    path.write_text(YAML)
    sf = load_seed_file(path)
    [window] = sf.org.commitment_windows
    assert window.start == "2026-09-01" and isinstance(window.start, str)
    assert [s.id for s in sf.seeds] == ["a", "b"]
    assert sf.seeds[1].is_fixture is False


def test_duplicate_seed_ids_are_rejected(tmp_path: Path):
    path = tmp_path / "seeds.yml"
    path.write_text(YAML.replace("id: b", "id: a"))
    with pytest.raises(ValueError, match="duplicate seed id"):
        load_seed_file(path)


def test_the_shipped_seed_file_loads():
    sf = load_seed_file(DEFAULT_SEED_PATH)
    assert sf.org.name and len(sf.seeds) >= 3


def test_build_meta_item_preserves_pointer_fields_on_reseed():
    seed = Seed(id="a", url="https://example.org/a2", funder="A Foundation", source_type="community_foundation")
    existing = {"program_id": "a", "url": "https://example.org/a", "verdict": "APPLY", "fit_score": 3.9, "latest_eval_sk": "EVAL#x"}
    item = build_meta_item(seed, "Riverbend", existing, "2026-08-21T12:00:00+00:00")
    assert item["url"] == "https://example.org/a2"
    assert item["verdict"] == "APPLY" and item["fit_score"] == 3.9 and item["latest_eval_sk"] == "EVAL#x"
    assert item["program_id"] == "a" and item["org"] == "Riverbend" and item["seeded_at"] == "2026-08-21T12:00:00+00:00"


def test_build_meta_item_fresh():
    seed = Seed(id="a", url="https://example.org/a", funder="A", source_type="x", is_fixture=True)
    item = build_meta_item(seed, "Riverbend", None, "2026-08-21T12:00:00+00:00")
    assert item == {
        "program_id": "a", "url": "https://example.org/a", "funder": "A", "source_type": "x",
        "is_fixture": True, "org": "Riverbend", "seeded_at": "2026-08-21T12:00:00+00:00",
    }

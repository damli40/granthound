"""Fidelity checks on the test doubles in tests.fakes.

A fake that is more forgiving than the real store hides bugs instead of
catching them: the suite stays green while production breaks. These tests
pin the invariants MemoryStore must share with granthound.store.ddb.
"""

from tests.fakes import MemoryStore


def test_put_run_rows_never_surface_from_list_programs():
    # In DynamoDB a run is pk="RUN#<id>", sk="META" -- the SAME sk as a
    # program's META row, so a filter on sk alone returns both. A run row
    # has no url and no program_id, so a caller iterating list_programs()
    # would hand evaluate_program a program it cannot fetch. MemoryStore
    # has to express that separation too, or this bug class is untestable
    # anywhere but live AWS.
    store = MemoryStore()
    store.put_program_meta({"program_id": "p1", "url": "https://example.org/grants"})
    store.put_run({"run_id": "run-20260821T120000Z", "status": "ok", "program_ids": ["p1"]})

    listed = store.list_programs()
    assert [p["program_id"] for p in listed] == ["p1"]
    assert not any("run_id" in p for p in listed)
    assert store.runs["run-20260821T120000Z"]["status"] == "ok"

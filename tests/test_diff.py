from granthound.tools.diff import diff_snapshots

OLD = "# Grants\n\nDeadline: October 15, 2026.\n\nAwards up to $5,000.\n"
NEW_DATE = "# Grants\n\nDeadline: September 30, 2026.\n\nAwards up to $5,000.\n"
NEW_PROSE = "# Grants\n\nDeadline: October 15, 2026.\n\nAwards up to $5,000 for youth programs.\n"


def test_identical_snapshots_unchanged():
    r = diff_snapshots(OLD, OLD)
    assert r.changed is False and r.date_lines_changed is False


def test_moved_deadline_flags_date_lines():
    r = diff_snapshots(OLD, NEW_DATE)
    assert r.changed is True
    assert r.date_lines_changed is True
    assert "September 30, 2026" in r.diff_text


def test_prose_change_without_date_change():
    r = diff_snapshots(OLD, NEW_PROSE)
    assert r.changed is True
    assert r.date_lines_changed is False
    assert r.added_lines == 1 and r.removed_lines == 1

"""Static-site snapshot."""

import pytest

from f1_ml import snapshot


def test_snapshot_never_wipes_a_folder_that_is_not_a_snapshot(tmp_path):
    mine = tmp_path / "notes.txt"
    mine.write_text("keep me")
    with pytest.raises(SystemExit):
        snapshot.build(tmp_path)
    assert mine.read_text() == "keep me"

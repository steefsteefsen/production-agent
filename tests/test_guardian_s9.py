"""Guardian S9: Binärdateien erkennen und begrenzen – kein Traceback auf gestagten Binärdaten."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))

import guardian  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def test_png_under_docs_images_passes(tmp_path):
    (tmp_path / "docs" / "images").mkdir(parents=True)
    (tmp_path / "docs" / "images" / "x.png").write_bytes(PNG)
    assert guardian.check_binary_placement(["docs/images/x.png"], root=tmp_path) == []


def test_png_in_root_is_s9_falsification(tmp_path):
    (tmp_path / "x.png").write_bytes(PNG)
    errs = guardian.check_binary_placement(["x.png"], root=tmp_path)
    assert any("S9" in e for e in errs)


def test_nul_byte_file_without_suffix_is_binary_falsification(tmp_path):
    f = tmp_path / "blob"
    f.write_bytes(b"text\x00more")
    assert guardian.is_binary(f) is True
    # und wird ohne erlaubtes Verzeichnis als S9 gemeldet, ohne Traceback
    assert any("S9" in e for e in guardian.check_binary_placement(["blob"], root=tmp_path))

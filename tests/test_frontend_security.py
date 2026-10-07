from pathlib import Path


def test_dataset_values_are_escaped_before_html_rendering():
    source = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text(encoding="utf-8")
    assert "const esc=" in source
    for expression in ("esc(m.name)", "esc(m.id)", "esc(x.sender)", "esc(x.receiver)"):
        assert expression in source

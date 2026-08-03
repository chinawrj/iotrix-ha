from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_repository_does_not_contain_tunnel_or_account_secrets() -> None:
    text = "\n".join(
        path.read_text(errors="ignore")
        for root in (ROOT / "custom_components", ROOT / ".github")
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    assert "Private" + "Key =" not in text
    assert "Preshared" + "Key =" not in text
    assert "192.168." + "123.47" not in text

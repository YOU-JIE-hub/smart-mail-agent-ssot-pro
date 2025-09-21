import sys
import textwrap

from ai_rpa.main import main


def test_main_nlp_only_no_texts(monkeypatch, tmp_path):
    cfg = tmp_path / "nlp_only.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
    tasks: ["nlp"]
    nlp: {model: "offline-keyword"}
    """
        ).strip(),
        encoding="utf-8",
    )

    argv = [
        "prog",
        "--config",
        str(cfg),
        "--input-path",
        str(tmp_path),
        "--url",
        "http://stub.local",
        "--dry-run",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = main()
    assert rc == 0

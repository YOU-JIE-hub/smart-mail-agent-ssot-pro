import sys
import textwrap

from ai_rpa.main import main


def test_main_no_tasks_cfg_empty(monkeypatch, tmp_path):
    cfg = tmp_path / "empty_tasks.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
    input_path: "data/input"
    output_path: "data/output/x.json"
    tasks: []
    """
        ).strip(),
        encoding="utf-8",
    )

    argv = ["prog", "--config", str(cfg)]
    monkeypatch.setattr(sys, "argv", argv)
    rc = main()
    assert rc == 0

"""Command-line validation before any experiment or output mutation."""
import pytest
from hvac_benchmark import cli, sensitivity


@pytest.mark.parametrize("flag,value", [
    ("--time-limit", "nan"), ("--time-limit", "inf"), ("--time-limit", "-inf"),
    ("--time-limit", "0"), ("--horizon-hours", "nan"), ("--horizon-hours", "inf"),
    ("--horizon-hours", "-inf"), ("--horizon-hours", "1e308"),
    ("--horizon-hours", "0.3"),
])
def test_invalid_numeric_options_exit_cleanly_without_output(tmp_path, capsys, flag, value):
    output = tmp_path / "new-output"
    with pytest.raises(SystemExit) as exc:
        cli.main([f"{flag}={value}", "--output", str(output)])
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err
    assert not output.exists()


def test_output_file_is_preserved_and_reported_as_argument_error(tmp_path, capsys):
    output = tmp_path / "existing.txt"
    output.write_text("keep this content", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        cli.main(["--output", str(output)])
    assert exc.value.code == 2
    assert "empty directory" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "keep this content"


def test_study_also_preserves_an_output_file(tmp_path):
    output = tmp_path / "existing.txt"
    output.write_text("keep this content", encoding="utf-8")
    with pytest.raises(ValueError, match="empty directory"):
        sensitivity.run_study(output, stage="smoke")
    assert output.read_text(encoding="utf-8") == "keep this content"


def test_sensitivity_console_route_forwards_arguments(monkeypatch):
    received = []
    monkeypatch.setattr(sensitivity, "main", lambda argv: received.append(argv))
    cli.main(["sensitivity", "--stage", "smoke", "--output", "results/check"])
    assert received == [["--stage", "smoke", "--output", "results/check"]]

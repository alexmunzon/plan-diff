from typer.testing import CliRunner

from plan_diff import __version__
from plan_diff.cli import app


def test_version_prints_the_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__

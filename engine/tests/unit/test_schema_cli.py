import json
from pathlib import Path

from typer.testing import CliRunner

from plan_diff.cli import app
from plan_diff.models import TOP_LEVEL_MODELS


def test_schema_export_writes_one_file_per_model(tmp_path: Path) -> None:
    out = tmp_path / "schemas"
    result = CliRunner().invoke(app, ["schema", "export", "--out", str(out)])
    assert result.exit_code == 0, result.output
    files = sorted(p.name for p in out.iterdir())
    assert len(files) == len(TOP_LEVEL_MODELS) == 6
    for model in TOP_LEVEL_MODELS:
        data = json.loads((out / f"{model.__name__}.schema.json").read_text())
        assert data["title"] == model.__name__

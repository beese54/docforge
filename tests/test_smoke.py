from typer.testing import CliRunner

from docforge import __version__
from docforge.cli import app


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output

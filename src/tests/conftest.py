from pathlib import Path

import pytest

DADOS = Path(__file__).resolve().parents[2] / "dados"


@pytest.fixture(scope="session")
def dados() -> Path:
    if not DADOS.exists():
        pytest.skip("pasta dados/ ausente")
    return DADOS

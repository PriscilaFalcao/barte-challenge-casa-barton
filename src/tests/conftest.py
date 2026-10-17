from pathlib import Path

import pytest

DADOS = Path(__file__).resolve().parents[2] / "dados"


@pytest.fixture(scope="session")
def dados() -> Path:
    if not DADOS.exists():
        pytest.skip("pasta dados/ ausente")
    return DADOS


@pytest.fixture(scope="session", autouse=True)
def _isolar_estado_e_ia(tmp_path_factory):
    """Testes nunca chamam a API de verdade, nem leem o cache de agentes versionado, nem escrevem em data/ do
    repositório. Escopo de sessão: precisa valer ANTES dos fixtures de módulo (que já rodam o fechamento)."""
    base = tmp_path_factory.mktemp("isolamento")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TARVO_SEM_IA", "1")
        mp.setenv("TARVO_ESTADO", str(base / "estado"))
        mp.setenv("TARVO_CACHE_AGENTES", str(base / "cache"))
        yield


@pytest.fixture(autouse=True)
def _estado_por_teste(tmp_path, monkeypatch):
    monkeypatch.setenv("TARVO_ESTADO", str(tmp_path / "estado"))

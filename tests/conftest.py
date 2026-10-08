import pytest

from contractscore.config import load_config
from contractscore.generate import generate


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def small_data(tmp_path_factory, cfg):
    out = tmp_path_factory.mktemp("data")
    generate(out, cfg, seed=3, n_scale=0.25)
    return out

"""The factory suite must not retain successful test trees."""

import configparser
from pathlib import Path


def test_pytest_temp_retention_config(pytestconfig):
    config_path = Path(__file__).resolve().parents[2] / "pytest.ini"
    config = configparser.ConfigParser()
    config.read(config_path)

    assert pytestconfig.inipath == config_path
    assert config["pytest"]["tmp_path_retention_count"] == "1"
    assert config["pytest"]["tmp_path_retention_policy"] == "failed"
    assert pytestconfig.getini("tmp_path_retention_count") == "1"
    assert pytestconfig.getini("tmp_path_retention_policy") == "failed"

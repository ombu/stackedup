import os

import pytest

from stacks.config import config_get_stack_region, config_load
from stacks.stack import Stack

STACK_CONFIG = {
    "account": "aws_account_for_the_stack",
    "parameters": {
        "Parameter1": "my_key",
        "Parameter2": "t3.small",
    },
}


@pytest.fixture
def config():
    path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(path, "test_config.yaml")) as config_file:
        return config_load(config_file)


@pytest.fixture
def test_template_path():
    return os.path.join(os.path.realpath(os.path.dirname(__file__)), "templates")


def _make_stack(config, test_template_path, stack_name=None):
    stack_config = {**STACK_CONFIG, **({"stack_name": stack_name} if stack_name else {})}
    return Stack(
        project_name="tests",
        stack_type="cluster",
        name="core",
        stack_config=stack_config,
        region=config_get_stack_region(config, "cluster", "core"),
        template_dir=test_template_path,
    )


@pytest.fixture
def live_stack(config, test_template_path):
    return _make_stack(config, test_template_path, stack_name="the_stack_name")


@pytest.fixture
def new_stack(config, test_template_path):
    return _make_stack(config, test_template_path)

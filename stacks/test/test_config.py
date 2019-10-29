import unittest
import os

from stacks.core import (
    config_load,
    config_get_stack_parameters,
    config_get_account_id,
    config_get_project_name,
)


class TestConfig(unittest.TestCase):
    def setUp(self):
        path = os.path.dirname(os.path.abspath(__file__))
        self.config = config_load(os.path.join(path, "test_config.yaml"))

    def test_config_get_account_id(self):
        self.assertEqual(config_get_account_id(self.config, "testing"), "637300000123")

    def test_config_get_project_name(self):
        self.assertEqual(config_get_project_name(self.config), "stacks")

    def test_resolved_parameters(self):
        resolved_parameters = config_get_stack_parameters(
            self.config, "testing", "cluster"
        )
        self.assertIsInstance(resolved_parameters, list)
        self.assertTrue(resolved_parameters[0]["ParameterKey"])

    def test_direct_parameters(self):
        direct_parameters = config_get_stack_parameters(
            self.config, "testing", "application"
        )
        self.assertIsInstance(direct_parameters, list)
        self.assertTrue(direct_parameters[0]["ParameterKey"])


if __name__ == "__main__":
    unittest.main()

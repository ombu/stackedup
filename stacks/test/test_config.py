import unittest
import os

from stacks.config import (
    config_load,
    config_get_stack_parameters,
    config_get_account_id,
    config_get_project_name,
    config_get_stack_name,
)


class TestConfig(unittest.TestCase):
    def setUp(self):
        path = os.path.dirname(os.path.abspath(__file__))
        self.config = config_load(os.path.join(path, "test_config.yaml"))

    def test_config_get_account_id(self):
        self.assertEqual(config_get_account_id(self.config, "instance", "testing1"), "637300000123")

    def test_config_get_project_name(self):
        self.assertEqual(config_get_project_name(self.config), "stacks")

    def test_resolved_parameters(self):
        resolved_parameters = config_get_stack_parameters(
            self.config, "testing1", "cluster"
        )
        self.assertIsInstance(resolved_parameters, list)
        self.assertTrue(resolved_parameters[0]["ParameterKey"])

    def test_direct_parameters(self):
        direct_parameters = config_get_stack_parameters(
            self.config, "testing1", "application"
        )
        self.assertIsInstance(direct_parameters, list)
        self.assertTrue(direct_parameters[0]["ParameterKey"])

    def test_get_stack_name_instance(self):
        instance = "testing1"
        component = "application"
        stack_name = config_get_stack_name(self.config, instance, component)
        self.assertEqual(stack_name, "stacks-application-testing1")

    def test_get_stack_name_cluster(self):
        instance = "testing1"
        component = "cluster"
        stack_name = config_get_stack_name(self.config, instance, component)
        self.assertEqual(stack_name, "stacks-cluster-core")


if __name__ == "__main__":
    unittest.main()

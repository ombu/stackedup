import os
import runpy
import unittest
from unittest import mock

from stacks.config import (
    _pluralize_component_name,
    config_get_account_id,
    config_get_account_name,
    config_get_active_account_id,
    config_get_cloudformation_bucket,
    config_get_project_name,
    config_get_role,
    config_get_stack_config,
    config_get_stack_region,
    config_load,
)


class TestConfig(unittest.TestCase):
    def setUp(self):
        path = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(path, "test_config.yaml")) as config_file:
            self.config = config_load(config_file)

    def test_config_load_adds_instance_list(self):
        self.assertEqual(self.config["instance_list"], ["testing1"])

    def test_config_get_account_name_for_account(self):
        self.assertEqual(config_get_account_name(self.config, "account", "ignored"), "_root")

    def test_config_get_account_name_for_cluster(self):
        self.assertEqual(
            config_get_account_name(self.config, "cluster", "core"), "test_aws_account1"
        )

    def test_config_get_account_name_for_instance(self):
        self.assertEqual(
            config_get_account_name(self.config, "application", "testing1"),
            "test_aws_account1",
        )

    def test_config_get_account_id(self):
        self.assertEqual(
            config_get_account_id(self.config, "instance", "testing1"), "637300000123"
        )

    def test_config_get_account_id_for_account_uses_active_account(self):
        with mock.patch("stacks.config.config_get_active_account_id", return_value="999"):
            self.assertEqual(config_get_account_id(self.config, "account", "ignored"), "999")

    def test_config_get_active_account_id_calls_sts(self):
        sts = mock.Mock()
        sts.get_caller_identity.return_value = {"Account": "111"}
        with mock.patch("stacks.config.boto3.client", return_value=sts) as client:
            self.assertEqual(config_get_active_account_id(), "111")
            client.assert_called_once_with("sts")
            sts.get_caller_identity.assert_called_once_with()

    def test_config_get_project_name(self):
        self.assertEqual(config_get_project_name(self.config), "tests")

    def test_config_get_stack_config_for_account(self):
        account_cfg = config_get_stack_config(self.config, "account", "test_aws_account1")
        self.assertEqual(account_cfg["id"], "637300000123")
        self.assertEqual(account_cfg["cloudformation_bucket"], "my_s3_bucket_name")

    def test_config_get_stack_config_for_cluster(self):
        cluster_cfg = config_get_stack_config(self.config, "cluster", "core")
        self.assertEqual(cluster_cfg["region"], "us-west-2")
        self.assertEqual(cluster_cfg["account"], "test_aws_account1")

    def test_config_get_stack_config_for_service_imports_account_and_cluster(self):
        app_cfg = config_get_stack_config(self.config, "application", "testing1")
        self.assertEqual(app_cfg["stack_name"], "stacks-application-testing1")
        self.assertEqual(app_cfg["account"], "test_aws_account1")
        self.assertEqual(app_cfg["cluster"], "core2")

    def test_get_cluster_region(self):
        region = config_get_stack_region(self.config, "cluster", "core")
        self.assertEqual("us-west-2", region)

    def test_get_account_region_is_constant(self):
        region = config_get_stack_region(self.config, "account", "ignored")
        self.assertEqual("us-west-2", region)

    def test_get_instance_region(self):
        region = config_get_stack_region(self.config, "application", "testing1")
        self.assertEqual("us-east-1", region)

    def test_get_cloudformation_bucket(self):
        bucket_name = config_get_cloudformation_bucket(self.config, "test_aws_account1")
        self.assertEqual("my_s3_bucket_name", bucket_name)

    def test_config_get_role(self):
        self.assertEqual(
            config_get_role(self.config, "test_aws_account1"),
            "arn:aws:iam::123456789012:role/S3Access",
        )

    def test_pluralize_component_name(self):
        self.assertEqual(_pluralize_component_name("cluster"), "clusters")
        self.assertEqual(_pluralize_component_name("account"), "accounts")

    def test_main_guard_calls_unittest_main(self):
        test_file = os.path.abspath(__file__)
        with mock.patch("unittest.main") as main:
            runpy.run_path(test_file, run_name="__main__")
            main.assert_called_once()


if __name__ == "__main__":
    unittest.main()

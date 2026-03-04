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
)


class TestConfig:
    def test_config_load_adds_instance_list(self, config):
        assert config["instance_list"] == ["testing1"]

    def test_config_get_account_name_for_account(self, config):
        assert config_get_account_name(config, "account", "ignored") == "_root"

    def test_config_get_account_name_for_cluster(self, config):
        assert config_get_account_name(config, "cluster", "core") == "test_aws_account1"

    def test_config_get_account_name_for_instance(self, config):
        assert config_get_account_name(config, "application", "testing1") == "test_aws_account1"

    def test_config_get_account_id(self, config):
        assert config_get_account_id(config, "instance", "testing1") == "637300000123"

    def test_config_get_account_id_for_account_uses_active_account(self, config):
        with mock.patch("stacks.config.config_get_active_account_id", return_value="999"):
            assert config_get_account_id(config, "account", "ignored") == "999"

    def test_config_get_active_account_id_calls_sts(self):
        sts = mock.Mock()
        sts.get_caller_identity.return_value = {"Account": "111"}
        with mock.patch("stacks.config.boto3.client", return_value=sts) as client:
            assert config_get_active_account_id() == "111"
            client.assert_called_once_with("sts")
            sts.get_caller_identity.assert_called_once_with()

    def test_config_get_project_name(self, config):
        assert config_get_project_name(config) == "tests"

    def test_config_get_stack_config_for_account(self, config):
        account_cfg = config_get_stack_config(config, "account", "test_aws_account1")
        assert account_cfg["id"] == "637300000123"
        assert account_cfg["cloudformation_bucket"] == "my_s3_bucket_name"

    def test_config_get_stack_config_for_cluster(self, config):
        cluster_cfg = config_get_stack_config(config, "cluster", "core")
        assert cluster_cfg["region"] == "us-west-2"
        assert cluster_cfg["account"] == "test_aws_account1"

    def test_config_get_stack_config_for_service_imports_account_and_cluster(self, config):
        app_cfg = config_get_stack_config(config, "application", "testing1")
        assert app_cfg["stack_name"] == "stacks-application-testing1"
        assert app_cfg["account"] == "test_aws_account1"
        assert app_cfg["cluster"] == "core2"

    def test_get_cluster_region(self, config):
        assert config_get_stack_region(config, "cluster", "core") == "us-west-2"

    def test_get_account_region_is_constant(self, config):
        assert config_get_stack_region(config, "account", "ignored") == "us-west-2"

    def test_get_instance_region(self, config):
        assert config_get_stack_region(config, "application", "testing1") == "us-east-1"

    def test_get_cloudformation_bucket(self, config):
        assert config_get_cloudformation_bucket(config, "test_aws_account1") == "my_s3_bucket_name"

    def test_config_get_role(self, config):
        assert config_get_role(config, "test_aws_account1") == "arn:aws:iam::123456789012:role/S3Access"

    def test_pluralize_component_name(self):
        assert _pluralize_component_name("cluster") == "clusters"
        assert _pluralize_component_name("account") == "accounts"

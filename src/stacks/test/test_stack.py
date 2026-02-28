import datetime
import os
import runpy
import unittest
from unittest import mock

import botocore.exceptions
import yaml

from stacks.config import config_get_stack_region, config_load
from stacks.stack import Stack


class TestStack(unittest.TestCase):
    def setUp(self):
        path = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(path, "test_config.yaml")) as config_file:
            self.config = config_load(config_file)
        self.live_stack_yaml = """
account: aws_account_for_the_stack
parameters:
  Parameter1: my_key
  Parameter2: t3.small
stack_name: the_stack_name"""
        self.new_stack_yaml = """
account: aws_account_for_the_stack
parameters:
  Parameter1: my_key
  Parameter2: t3.small"""
        self.test_template_path = os.path.join(
            os.path.realpath(os.path.dirname(__file__)), "templates"
        )
        self.live_stack = Stack(
            project_name="tests",
            stack_type="cluster",
            name="core",
            stack_config=yaml.safe_load(self.live_stack_yaml, Loader=yaml.FullLoader),
            region=config_get_stack_region(self.config, "cluster", "core"),
            template_dir=self.test_template_path,
        )
        self.new_stack = Stack(
            project_name="tests",
            stack_type="cluster",
            name="core",
            stack_config=yaml.safe_load(self.new_stack_yaml, Loader=yaml.FullLoader),
            region=config_get_stack_region(self.config, "cluster", "core"),
            template_dir=self.test_template_path,
        )

    def test_stack_name_property(self):
        self.assertEqual("the_stack_name", self.live_stack.stack_name)
        fixed = datetime.datetime(2020, 1, 2, 3, 4, 5)
        with mock.patch("stacks.stack.datetime.datetime") as dt:
            dt.now.return_value = fixed
            dt.side_effect = lambda *a, **k: datetime.datetime(*a, **k)
            self.assertEqual("tests-cluster-core-202001020304", self.new_stack.stack_name)

    def test_account_name_property(self):
        account_stack = Stack(
            project_name="tests",
            stack_type="account",
            name="acct",
            region="us-west-2",
            stack_config={"parameters": {}},
            template_dir=self.test_template_path,
        )
        self.assertEqual("acct", account_stack.account_name)
        self.assertEqual("aws_account_for_the_stack", self.live_stack.account_name)

    def test_get_template_path(self):
        template_file = os.path.join(self.test_template_path, "cluster.yaml")
        self.assertEqual(template_file, self.new_stack.get_template_path())

    def test_get_template_body(self):
        template_file = os.path.join(self.test_template_path, "cluster.yaml")
        with open(template_file, "r") as f:
            template_body = f.read()
        self.assertEqual(template_body, self.new_stack.get_template_body)

    def test_get_parameters(self):
        self.assertEqual(
            {"Parameter1": "my_key", "Parameter2": "t3.small"},
            self.live_stack.get_parameters(formatting="json"),
        )
        self.assertEqual(
            [
                {"ParameterKey": "Parameter1", "ParameterValue": "my_key"},
                {"ParameterKey": "Parameter2", "ParameterValue": "t3.small"},
            ],
            self.live_stack.get_parameters(formatting="cloudformation"),
        )
        self.assertIsNone(self.live_stack.get_parameters(formatting="unknown"))

    def test_create_calls_client(self):
        client = mock.Mock()
        with mock.patch("builtins.print") as p:
            self.live_stack.create(client, Tags=[{"Key": "k", "Value": "v"}])
        p.assert_called_once_with("the_stack_name")
        client.create_stack.assert_called_once()
        kwargs = client.create_stack.call_args.kwargs
        self.assertEqual(kwargs["StackName"], "the_stack_name")
        self.assertTrue(kwargs["DisableRollback"])
        self.assertIn("CAPABILITY_NAMED_IAM", kwargs["Capabilities"])
        self.assertEqual(
            kwargs["Parameters"],
            self.live_stack.get_parameters(formatting="cloudformation"),
        )

    def test_update_calls_client(self):
        client = mock.Mock()
        self.live_stack.update(client)
        client.update_stack.assert_called_once()
        kwargs = client.update_stack.call_args.kwargs
        self.assertEqual(kwargs["StackName"], "the_stack_name")
        self.assertIn("CAPABILITY_AUTO_EXPAND", kwargs["Capabilities"])

    def test_describe_helpers(self):
        client = mock.Mock()
        client.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackId": "id",
                    "Outputs": [
                        {"OutputKey": "A", "OutputValue": "1"},
                        {"OutputKey": "B", "OutputValue": "2"},
                    ],
                }
            ]
        }
        self.assertEqual(self.live_stack.get_details(client)["StackId"], "id")
        self.assertEqual(len(self.live_stack.get_outputs(client)), 2)
        self.assertEqual(self.live_stack.get_output(client, "B"), "2")

    def test_tabulate_results_strips_optional_fields(self):
        outputs = [
            {
                "OutputKey": "A",
                "OutputValue": "1",
                "Description": "d",
                "ExportName": "e",
            },
            {"OutputKey": "B", "OutputValue": "2"},
        ]
        table = Stack.tabulate_results(outputs)
        self.assertNotIn("Description", outputs[0])
        self.assertNotIn("ExportName", outputs[0])
        self.assertIn("OutputKey", table)
        self.assertIn("OutputValue", table)

    def test_package_template_happy_path(self):
        credentials = {
            "AccessKeyId": "AK",
            "SecretAccessKey": "SK",
            "SessionToken": "TK",
        }
        s3 = mock.Mock()
        with (
            mock.patch("stacks.stack.boto3.client", return_value=s3) as boto_client,
            mock.patch(
                "stacks.stack.subprocess.check_output",
                return_value=b"Resources: {}\n",
            ) as check_output,
        ):
            result = self.live_stack.package_template(credentials, "bkt", "us-east-1")

        boto_client.assert_called_once_with(
            "s3",
            aws_access_key_id="AK",
            aws_secret_access_key="SK",
            aws_session_token="TK",
        )
        s3.head_bucket.assert_called_once_with(Bucket="bkt")
        check_output.assert_called_once()
        call = check_output.call_args
        self.assertIn("aws", call.args[0][0])
        self.assertEqual(call.kwargs["env"]["AWS_ACCESS_KEY_ID"], "AK")
        self.assertIn("Resources", result)

    def test_package_template_bucket_missing_prints(self):
        credentials = {
            "AccessKeyId": "AK",
            "SecretAccessKey": "SK",
            "SessionToken": "TK",
        }
        s3 = mock.Mock()
        s3.head_bucket.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadBucket",
        )
        with (
            mock.patch("stacks.stack.boto3.client", return_value=s3),
            mock.patch(
                "stacks.stack.subprocess.check_output",
                return_value=b"Resources: {}\n",
            ),
            mock.patch("builtins.print") as p,
        ):
            self.live_stack.package_template(credentials, "bkt", "us-east-1")
        p.assert_any_call("Bucket not available bkt")

    def test_main_guard_calls_unittest_main(self):
        test_file = os.path.abspath(__file__)
        with mock.patch("unittest.main") as main:
            runpy.run_path(test_file, run_name="__main__")
            main.assert_called_once()


if __name__ == "__main__":
    unittest.main()

import datetime
import os
from unittest import mock

import botocore.exceptions

from stacks.stack import Stack


class TestStack:
    def test_stack_name_property(self, live_stack, new_stack):
        assert live_stack.stack_name == "the_stack_name"
        fixed = datetime.datetime(2020, 1, 2, 3, 4, 5)
        with mock.patch("stacks.stack.datetime.datetime") as dt:
            dt.now.return_value = fixed
            assert new_stack.stack_name == "tests-cluster-core-202001020304"

    def test_account_name_property(self, live_stack, test_template_path):
        account_stack = Stack(
            project_name="tests",
            stack_type="account",
            name="acct",
            region="us-west-2",
            stack_config={"parameters": {}},
            template_dir=test_template_path,
        )
        assert account_stack.account_name == "acct"
        assert live_stack.account_name == "aws_account_for_the_stack"

    def test_get_template_path(self, new_stack, test_template_path):
        template_file = os.path.join(test_template_path, "cluster.yaml")
        assert new_stack.get_template_path() == template_file

    def test_get_template_body(self, new_stack, test_template_path):
        template_file = os.path.join(test_template_path, "cluster.yaml")
        with open(template_file) as f:
            template_body = f.read()
        assert new_stack.get_template_body == template_body

    def test_get_parameters(self, live_stack):
        assert live_stack.get_parameters(formatting="json") == {
            "Parameter1": "my_key",
            "Parameter2": "t3.small",
        }
        assert live_stack.get_parameters(formatting="cloudformation") == [
            {"ParameterKey": "Parameter1", "ParameterValue": "my_key"},
            {"ParameterKey": "Parameter2", "ParameterValue": "t3.small"},
        ]
        assert live_stack.get_parameters(formatting="unknown") is None

    def test_get_parameters_env_override(self, live_stack, monkeypatch):
        monkeypatch.setenv("Parameter1", "override_key")
        monkeypatch.setenv("Parameter2", "override_size")

        assert live_stack.get_parameters(formatting="json") == {
            "Parameter1": "override_key",
            "Parameter2": "override_size",
        }

        assert live_stack.get_parameters(formatting="cloudformation") == [
            {"ParameterKey": "Parameter1", "ParameterValue": "override_key"},
            {"ParameterKey": "Parameter2", "ParameterValue": "override_size"},
        ]

    def test_create_calls_client(self, live_stack, capsys):
        client = mock.Mock()
        live_stack.create(client, Tags=[{"Key": "k", "Value": "v"}])
        assert capsys.readouterr().out == "the_stack_name\n"
        client.create_stack.assert_called_once()
        kwargs = client.create_stack.call_args.kwargs
        assert kwargs["StackName"] == "the_stack_name"
        assert kwargs["DisableRollback"] is True
        assert "CAPABILITY_NAMED_IAM" in kwargs["Capabilities"]
        assert kwargs["Parameters"] == live_stack.get_parameters(formatting="cloudformation")

    def test_update_calls_client(self, live_stack):
        client = mock.Mock()
        live_stack.update(client)
        client.update_stack.assert_called_once()
        kwargs = client.update_stack.call_args.kwargs
        assert kwargs["StackName"] == "the_stack_name"
        assert "CAPABILITY_AUTO_EXPAND" in kwargs["Capabilities"]

    def test_describe_helpers(self, live_stack):
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
        assert live_stack.get_details(client)["StackId"] == "id"
        assert len(live_stack.get_outputs(client)) == 2
        assert live_stack.get_output(client, "B") == "2"

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
        assert "Description" not in outputs[0]
        assert "ExportName" not in outputs[0]
        assert "OutputKey" in table
        assert "OutputValue" in table

    def test_package_template_happy_path(self, live_stack):
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
            result = live_stack.package_template(credentials, "bkt", "us-east-1")

        boto_client.assert_called_once_with(
            "s3",
            aws_access_key_id="AK",
            aws_secret_access_key="SK",
            aws_session_token="TK",
        )
        s3.head_bucket.assert_called_once_with(Bucket="bkt")
        check_output.assert_called_once()
        call = check_output.call_args
        assert "aws" in call.args[0][0]
        assert call.kwargs["env"]["AWS_ACCESS_KEY_ID"] == "AK"
        assert "Resources" in result

    def test_package_template_bucket_missing_prints(self, live_stack, capsys):
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
        ):
            live_stack.package_template(credentials, "bkt", "us-east-1")
        assert "Bucket not available bkt" in capsys.readouterr().out

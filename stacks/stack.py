import datetime
import logging
import os
from botocore.exceptions import WaiterError
import subprocess
from tabulate import tabulate
from stacks.command import get_boto_client
from typing import AnyStr, Dict

logger = logging.getLogger(__name__)


class Stack:
    def __init__(
        self,
        stack_type: AnyStr,
        name: AnyStr,
        stack_config: Dict,
        template_dir: AnyStr = "templates",
    ):
        """
          :param stack_config: Dict
          A dictionary of the stack configuration like:

            account: aws_account_for_the_stack
            parameters:
              Parameter1: my_key
              Parameter2: t3.small
            stack_name: the_stack_name
        """
        self.type = stack_type
        self.name = name
        self.stack_config = stack_config
        self.template_dir = template_dir

    # def __init__(self, **kwargs):
    #     self.__dict__.update(kwargs)
    #     self.stack_name = None

    @property
    def stack_name(self):
        try:
            return self.stack_config["stack_name"]
        except KeyError:
            # Create a stack name
            date = f"{datetime.datetime.now():%Y%m%d%H%M}"
            stack_name = "-".join((self.type, self.name, date))
            logger.info("Setting stack name to %s" % stack_name)
            return stack_name

    @property
    def account_name(self):
        return self.stack_config["account"]

    def get_template_path(self):
        return os.path.join(os.path.realpath(self.template_dir), "%s.yaml" % self.type,)

    def get_template_body(self):
        template_path = self.get_template_path()
        file = open(template_path, "r")
        template = file.read()
        file.close()
        logger.info("Loaded template %s" % template_path)
        return template

    def get_parameters(self):
        parameters = self.stack_config["parameters"]
        parameters["EnvironmentType"] = self.name
        formatted_parameters = [
            {"ParameterKey": k, "ParameterValue": v} for k, v in parameters.items()
        ]
        return formatted_parameters

    def package_template(self, credentials, bucket):
        """
        boto3 does not support the Cloudformation package command, so we have to
        depends on the aws cli and make a subprocess call

        Returns the packaged template as a string
        """
        template_path = self.get_template_path()
        logger.info("Packaging template %s to %s" % (template_path, bucket))
        packaged_template = subprocess.check_output(
            [
                "aws",
                "cloudformation",
                "package",
                "--template-file",
                template_path,
                "--s3-bucket",
                bucket,
                "--s3-prefix",
                self.name,
            ],
            env={
                **os.environ,
                "AWS_ACCESS_KEY_ID": credentials["AccessKeyId"],
                "AWS_SECRET_ACCESS_KEY": credentials["SecretAccessKey"],
                "AWS_SESSION_TOKEN": credentials["SessionToken"],
            },
        )
        return packaged_template.decode("utf-8")

    def create(self, DisableRollback=True, **kwargs):
        kwargs["StackName"] = self.stack_name
        account_name = "_root"
        cf_client = get_boto_client(self.config, "cloudformation", account_name)
        cf_client.create_stack(**kwargs)
        logger.info("Creating stack %s" % self.stack_name)
        try:
            cf_client.get_waiter("stack_create_complete").wait(
                StackName=self.stack_name,
                WaiterConfig={"Delay": 20},  # checks the stack status every X seconds
            )
        except WaiterError:
            logger.error("Stack creation failed for %s" % self.stack_name)

    def update(self, client, **kwargs):
        kwargs.update(
            {
                "StackName": self.stack_name,
                "Parameters": self.get_parameters(),
                "Capabilities": ["CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"],
            }
        )
        client.update_stack(**kwargs)
        logger.info("Updating stack %s" % kwargs["StackName"])

    def get_outputs(self, client):
        response = client.describe_stacks(StackName=self.stack_name)
        return response["Stacks"][0]["Outputs"]

    @staticmethod
    def tabulate_outputs(outputs):
        for d in outputs:
            try:
                del d["Description"]
                del d["ExportName"]
            except KeyError:
                pass
        return tabulate(outputs, headers="keys")

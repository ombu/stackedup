import datetime
import logging
import os
import subprocess
import boto3
import botocore.exceptions
from tabulate import tabulate
from typing import AnyStr, Dict
import yaml

logger = logging.getLogger(__name__)


class Stack:
    def __init__(
        self,
        project_name: AnyStr,
        stack_type: AnyStr,
        name: AnyStr,
        region: AnyStr,
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
        self.project_name = project_name
        self.name = name
        self.stack_config = stack_config
        self.template_dir = template_dir
        self.region = region

    @property
    def stack_name(self):
        try:
            return self.stack_config["stack_name"]
        except KeyError:
            # Create a stack name
            date = f"{datetime.datetime.now():%Y%m%d%H%M}"
            stack_name = "-".join((self.project_name, self.type, self.name, date))
            logger.info("Setting stack name to %s" % stack_name)
            return stack_name

    @property
    def account_name(self):
        if self.type == "account":
            return self.name
        else:
            return self.stack_config["account"]

    def get_template_path(self):
        return os.path.join(
            os.path.realpath(self.template_dir),
            "%s.yaml" % self.type,
        )

    def get_template_body(self):
        template_path = self.get_template_path()
        file = open(template_path, "r")
        template = file.read()
        file.close()
        logger.info("Loaded template %s" % template_path)
        return template

    def get_parameters(self, formatting="json"):
        parameters = self.stack_config["parameters"]
        if formatting == "json":
            return parameters
        if formatting == "cloudformation":
            formatted_parameters = [
                {"ParameterKey": k, "ParameterValue": v} for k, v in parameters.items()
            ]
            return formatted_parameters

    def package_template(self, credentials, bucket, region_name):
        """
        boto3 does not support the Cloudformation package command, so we have to
        depends on the aws cli and make a subprocess call

        Returns the packaged template as a string
        """
        template_path = self.get_template_path()

        # check if bucket exists or create it

        s3 = boto3.client(
            "s3",
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
        try:
            s3.head_bucket(Bucket=bucket)
        except botocore.exceptions.ClientError:
            print(f"Bucket not available {bucket}")

        logger.info("Packaging template %s to %s" % (template_path, bucket))
        # TODO Check if bucket exists, and create it if necessary
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
                "--region",
                region_name,
            ],
            env={
                **os.environ,
                "AWS_ACCESS_KEY_ID": credentials["AccessKeyId"],
                "AWS_SECRET_ACCESS_KEY": credentials["SecretAccessKey"],
                "AWS_SESSION_TOKEN": credentials["SessionToken"],
            },
        )
        # Run the template through PyYaml, to catch formatting issues from
        # reading the output of the subprocess call
        y = yaml.load(packaged_template.decode("utf-8"), Loader=yaml.FullLoader)
        return yaml.dump(y)

    def create(self, client, **kwargs):
        kwargs.update(
            {
                "StackName": self.stack_name,
                "Parameters": self.get_parameters(formatting="cloudformation"),
                "DisableRollback": True,
                "Capabilities": ["CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"],
            }
        )
        print(self.stack_name)
        client.create_stack(**kwargs)
        logger.info("Creating stack %s" % self.stack_name)

    def update(self, client, **kwargs):
        kwargs.update(
            {
                "StackName": self.stack_name,
                "Parameters": self.get_parameters(formatting="cloudformation"),
                "Capabilities": ["CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"],
            }
        )
        client.update_stack(**kwargs)
        logger.info("Updating stack %s" % kwargs["StackName"])

    def get_details(self, client):
        response = client.describe_stacks(StackName=self.stack_name)
        return response["Stacks"][0]

    def get_outputs(self, client):
        response = client.describe_stacks(StackName=self.stack_name)
        return response["Stacks"][0]["Outputs"]

    def get_output(self, client, output_key):
        response = client.describe_stacks(StackName=self.stack_name)
        outputs = response["Stacks"][0]["Outputs"]
        v = [i["OutputValue"] for i in outputs if i["OutputKey"] == output_key]
        return v[0]

    @staticmethod
    def tabulate_results(outputs):
        for d in outputs:
            try:
                del d["Description"]
                del d["ExportName"]
            except KeyError:
                pass
        return tabulate(outputs, headers="keys")

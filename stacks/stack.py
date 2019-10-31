import datetime
import logging
import os
import boto3
from botocore.exceptions import WaiterError
import subprocess
from tabulate import tabulate


logger = logging.getLogger(__name__)


class Stack:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.stack_name = None

    def create_stack_name(self):
        if self.stack_name:
            raise Exception("Cannot redefine stack_name")
        date = f"{datetime.datetime.now():%Y%m%d%H%M}"
        self.stack_name = "-".join(
            (self.stack_type, self.name, date)
        )
        logger.info("Setting stack name to %s" % self.stack_name)
        return self.stack_name

    def get_template_path(self):
        # __location__ = os.path.realpath(
        #     os.path.join(os.getcwd(), os.path.dirname(__file__))
        # )
        return os.path.join(
            os.path.realpath(self.template_dir),
            "..",
            "infrastructure",
            "%s.yaml" % self.stack_type,
        )

    def get_template_body(self):
        template_path = self.get_template_path()
        file = open(template_path, "r")
        template = file.read()
        logger.info("Loaded template %s" % template_path)
        return template

    def package(self):
        """
        Because boto does not yet support the Cloudformation template package
        operation, we have to depends on the aws cli and make a subprocess call
        it

        Returns the packaged template as a string
        """
        template_path = self.get_template_path()
        bucket = "cloudformation-%s-%s" % (self.project_name, self.aws_account_id,)
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
            ]
        )
        return packaged_template.decode("utf-8")

    def create(self, DisableRollback=True, **kwargs):
        kwargs["StackName"] = self.create_stack_name()
        cf_client = boto3.client("cloudformation")
        cf_client.create_stack(**kwargs)
        logger.info("Creating stack %s" % self.stack_name)
        try:
            cf_client.get_waiter("stack_create_complete").wait(
                StackName=self.stack_name,
                WaiterConfig={"Delay": 20},  # checks the stack status every X seconds
            )
        except WaiterError:
            logger.error("Stack creation failed for %s" % self.stack_name)

    @staticmethod
    def update(DisableRollback=True, **kwargs):
        cf_client = boto3.client("cloudformation")
        cf_client.update_stack(**kwargs)
        logger.info("Updating stack %s" % kwargs["StackName"])
        try:
            cf_client.get_waiter("stack_update_complete").wait(
                StackName=kwargs["StackName"],
                WaiterConfig={"Delay": 20},  # checks the stack status every X seconds
            )
        except WaiterError:
            logger.error("Stack update failed for %s" % kwargs["StackName"])

    @staticmethod
    def get_outputs(stack_name):
        cf_client = boto3.client("cloudformation")
        response = cf_client.describe_stacks(StackName=stack_name)
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

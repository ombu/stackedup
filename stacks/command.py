import argparse
import logging
from functools import lru_cache

import boto3
from stacks.config import config_load, config_get_project_name

logger = logging.getLogger(__name__)


class BaseCommand:
    def __init__(self, *args):
        self._args = None
        self.argparser = argparse.ArgumentParser()
        self.argparser.add_argument(
            "--config", type=argparse.FileType("r"), default="config.yaml"
        )
        self.add_arguments()
        self.config = config_load(self.args.config)
        self.project_name = config_get_project_name(self.config)

    @property
    def args(self):
        if self._args:
            return self._args
        else:
            self._args = self.argparser.parse_args()
            return self._args

    def add_arguments(self):
        pass

    def run(self):
        pass


class StackCommand(BaseCommand):
    def __init__(self, *args):
        super().__init__(*args)

    def add_arguments(self):
        self.argparser.add_argument("stack_type", type=str)
        self.argparser.add_argument(
            "name", type=str,
        )

    def run(self):
        super().run()


class AccountCommand(BaseCommand):
    def __init__(self, *args):
        super().__init__(*args)

    def add_arguments(self):
        self.argparser.add_argument("account_name", type=str)

    def run(self):
        super().run()


@lru_cache(maxsize=10)
def get_boto_client(client_type, role_arn, account_name, region_name):
    credentials = get_boto_credentials(role_arn, account_name)
    return boto3.client(
        client_type,
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=region_name,
    )


@lru_cache(maxsize=10)
def get_boto_credentials(role_arn, account_name):
    response = boto3.client("sts").assume_role(
        RoleArn=role_arn, RoleSessionName=f"{account_name}_session"
    )
    logger.info(f"Assuming role {role_arn}")
    return response["Credentials"]


class InstanceCommand(BaseCommand):
    """
    A command that operates on instances
    """

    def __init__(self, *args):
        super().__init__(*args)

    def add_arguments(self):
        self.argparser.add_argument("name", type=str)

    def run(self):
        super().run()

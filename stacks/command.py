import argparse
import logging
import boto3
from stacks.config import config_load

logger = logging.getLogger(__name__)


class BaseCommand:
    def __init__(self, *args):
        self.config = config_load(args[0])
        self.argparser = argparse.ArgumentParser()

    @property
    def args(self):
        try:
            return self._args
        except AttributeError:
            self._args = self.argparser.parse_args()
            return self._args

    def run(self):
        def run(self):
            pass


class StackCommand(BaseCommand):
    def __init__(self, *args):
        super().__init__(*args)
        self.argparser.add_argument(
            "stack_type", type=str, choices=self.config["stack_types"]
        )
        self.argparser.add_argument(
            # TODO: This argument needs validation
            "name",
            type=str,  # , choices=self.config["instance_list"]
        )

    def run(self):
        super().run()


class AccountCommand(BaseCommand):
    def __init__(self, *args):
        super().__init__(*args)
        self.argparser.add_argument(
            "account_name", type=str, choices=list(self.config["accounts"].keys())
        )
        self._args = self.argparser.parse_args()


def run(self):
    super().run()


def get_boto_client(client_type, config, account_name):
    credentials = get_boto_credentials(config, account_name)
    return boto3.client(
        client_type,
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )


def get_boto_credentials(config, account_name):
    role_arn = config["accounts"][account_name]["provisioner_role_arn"]
    response = boto3.client("sts").assume_role(
        RoleArn=role_arn, RoleSessionName=f"{account_name}_session"
    )
    logger.info(f"Assuming role {role_arn}")
    return response["Credentials"]

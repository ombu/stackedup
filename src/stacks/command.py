import argparse
import logging
import logging.handlers
from functools import lru_cache

from botocore.exceptions import NoCredentialsError

from stacks.aws import get_boto_session
from stacks.config import config_get_project_name, config_load

logger = logging.getLogger(__name__)


class BaseCommand:
    def __init__(self, *args):
        self._args = None
        self.argparser = argparse.ArgumentParser()
        self.argparser.add_argument("--config", type=argparse.FileType("r"), default="config.yaml")
        self.add_arguments()
        self.config = config_load(self.args.config)
        self.project_name = config_get_project_name(self.config)
        logging.basicConfig(level=self.args.log_level, format="%(levelname)s - %(message)s")

    @property
    def args(self):
        if self._args:
            return self._args
        else:
            self._args = self.argparser.parse_args()
            return self._args

    def add_arguments(self):
        self.argparser.add_argument(
            "--log-level",
            default="WARNING",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Set the logging level (default: WARNING)",
        )

    def run(self):
        pass


class StackCommand(BaseCommand):
    def __init__(self, *args):
        super().__init__(*args)

    def add_arguments(self):
        super().add_arguments()
        self.argparser.add_argument("stack_type", type=str)
        self.argparser.add_argument(
            "name",
            type=str,
        )

    def run(self):
        super().run()


class AccountCommand(BaseCommand):
    def __init__(self, *args):
        super().__init__(*args)

    def add_arguments(self):
        super().add_arguments()
        self.argparser.add_argument("account_name", type=str)

    def run(self):
        super().run()


@lru_cache(maxsize=10)
def get_boto_client(client_type, region_name):
    return get_boto_session().client(client_type, region_name=region_name)


def get_boto_credentials():
    credentials = get_boto_session().get_credentials()
    if credentials is None:
        raise NoCredentialsError()
    credentials = credentials.get_frozen_credentials()
    logger.info("Get current session credentials")
    return {
        "AccessKeyId": credentials.access_key,
        "SecretAccessKey": credentials.secret_key,
        "SessionToken": credentials.token,
    }


@lru_cache(maxsize=10)
def get_boto_assumed_credentials(role_arn, account_name):
    response = (
        get_boto_session()
        .client("sts")
        .assume_role(RoleArn=role_arn, RoleSessionName=f"{account_name}_session")
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
        super().add_arguments()
        self.argparser.add_argument("name", type=str)

    def run(self):
        super().run()

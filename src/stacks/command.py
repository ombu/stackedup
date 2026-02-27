import argparse
import logging
import sys
from functools import lru_cache

import boto3

from stacks.config import config_get_project_name, config_load

logger = logging.getLogger(__name__)


class BaseCommand:
    def __init__(self, *args):
        self._args = None
        self.argparser = argparse.ArgumentParser()
        self.argparser.add_argument("--config", type=argparse.FileType("r"), default="config.yaml")
        self.argparser.add_argument(
            "-v", "--verbose",
            action="store_true",
            help="Print current AWS identity and assume-role decisions",
        )
        self.argparser.add_argument(
             "-f", "--force-assume-role",
            action="store_true",
            help="Always assume the provisioner role from config.yaml",
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
            "name",
            type=str,
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


def _parse_iam_role_arn(role_arn):
    """
    Return (partition, account_id, role_name) for an IAM role ARN.
    """
    # arn:partition:iam::account:role/path/to/RoleName
    if not isinstance(role_arn, str) or not role_arn.startswith("arn:"):
        return None
    parts = role_arn.split(":", 5)
    if len(parts) != 6:
        return None
    _, partition, service, _, account_id, resource = parts
    if service != "iam" or not resource.startswith("role/"):
        return None
    role_name = resource[len("role/") :].split("/")[-1]
    if not account_id or not role_name:
        return None
    return partition, account_id, role_name


@lru_cache(maxsize=1)
def _get_caller_identity():
    return boto3.client("sts").get_caller_identity()


def _current_assumed_role_identity():
    """
    Return (partition, account_id, role_name) if current creds are an assumed role.
    """
    arn = _get_caller_identity().get("Arn")
    # arn:partition:sts::account:assumed-role/RoleName/SessionName
    if not isinstance(arn, str) or not arn.startswith("arn:"):
        return None
    parts = arn.split(":", 5)
    if len(parts) != 6:
        return None
    _, partition, service, _, account_id, resource = parts
    if service != "sts" or not resource.startswith("assumed-role/"):
        return None
    role_name = resource[len("assumed-role/") :].split("/", 1)[0]
    if not account_id or not role_name:
        return None
    return partition, account_id, role_name


def _current_account_id():
    account_id = _get_caller_identity().get("Account")
    return account_id if isinstance(account_id, str) and account_id else None


def _identity_debug(verbose, lines):
    if not verbose:
        return
    for line in lines:
        print(line, file=sys.stderr)


def is_current_account(role_arn):
    """
    True if current AWS identity is already in the target account.
    """
    target = _parse_iam_role_arn(role_arn)
    if not target:
        return False
    _, target_account_id, _ = target
    current_account_id = _current_account_id()
    if not current_account_id:
        return False
    return current_account_id == target_account_id


def is_current_role(role_arn):
    """
    True if current AWS identity is already the target IAM role.
    """
    target = _parse_iam_role_arn(role_arn)
    current = _current_assumed_role_identity()
    if not target or not current:
        return False
    return target == current


def get_role_credentials_if_needed(role_arn, account_name, *, force_assume_role=False, verbose=False):
    """
    Return assumed-role credentials dict, or None if already using role_arn.
    """
    identity = _get_caller_identity()
    current_arn = identity.get("Arn")
    current_account = identity.get("Account")

    if not force_assume_role and (is_current_role(role_arn) or is_current_account(role_arn)):
        _identity_debug(
            verbose,
            [
                f"Current identity: {current_arn}",
                f"Current account: {current_account}",
                f"Target role: {role_arn}",
                "AssumeRole: skipped (already in target account/role)",
            ],
        )
        logger.info(f"Skipping STS assume_role for {role_arn}")
        return None

    if force_assume_role:
        _identity_debug(
            verbose,
            [
                f"Current identity: {current_arn}",
                f"Current account: {current_account}",
                f"Target role: {role_arn}",
                "AssumeRole: forcing assume_role (per --force-assume-role)",
            ],
        )
    else:
        _identity_debug(
            verbose,
            [
                f"Current identity: {current_arn}",
                f"Current account: {current_account}",
                f"Target role: {role_arn}",
                "AssumeRole: assuming role",
            ],
        )
    return get_boto_credentials(role_arn, account_name)


@lru_cache(maxsize=10)
def get_boto_client(
    client_type,
    role_arn,
    account_name,
    region_name,
    *,
    force_assume_role=False,
    verbose=False,
):
    identity = _get_caller_identity()
    current_arn = identity.get("Arn")
    current_account = identity.get("Account")

    if not force_assume_role and (is_current_role(role_arn) or is_current_account(role_arn)):
        _identity_debug(
            verbose,
            [
                f"Current identity: {current_arn}",
                f"Current account: {current_account}",
                f"Target role: {role_arn}",
                f"Client {client_type}: ambient credentials (no assume_role)",
            ],
        )
        logger.info(f"Using ambient credentials for {client_type}")
        return boto3.client(client_type, region_name=region_name)

    _identity_debug(
        verbose,
        [
            f"Current identity: {current_arn}",
            f"Current account: {current_account}",
            f"Target role: {role_arn}",
            f"Client {client_type}: assuming role",
        ],
    )

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
    response = boto3.client("sts").assume_role(RoleArn=role_arn, RoleSessionName=f"{account_name}_session")
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

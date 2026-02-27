import logging
import sys

import boto3

from stacks.command import (
    AccountCommand,
    get_boto_credentials,
    is_current_account,
    is_current_role,
)
from stacks.config import config_get_role

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")


class AssumeRoleCommand(AccountCommand):
    def __init__(self, config_file):
        super().__init__(config_file)

    def run(self):
        role_arn = config_get_role(self.config, self.args.account_name)
        if self.args.verbose:
            ident = boto3.client("sts").get_caller_identity()
            print(f"Current identity: {ident.get('Arn')}", file=sys.stderr)
            print(f"Current account: {ident.get('Account')}", file=sys.stderr)
            print(f"Target role: {role_arn}", file=sys.stderr)
        if not self.args.force_assume_role and (is_current_role(role_arn) or is_current_account(role_arn)):
            if self.args.verbose:
                print(
                    "AssumeRole: skipped (already in target account/role)",
                    file=sys.stderr,
                )
            creds = boto3.Session().get_credentials()
            frozen = creds.get_frozen_credentials() if creds else None
            if not frozen:
                logger.error("Unable to read current AWS credentials")
                return
            print(f"export AWS_ACCESS_KEY_ID={frozen.access_key}")
            print(f"export AWS_SECRET_ACCESS_KEY={frozen.secret_key}")
            if frozen.token:
                print(f"export AWS_SESSION_TOKEN={frozen.token}")
            return

        if self.args.verbose:
            if self.args.force_assume_role:
                print(
                    "AssumeRole: forcing assume_role (per --force-assume-role)",
                    file=sys.stderr,
                )
            else:
                print("AssumeRole: assuming role", file=sys.stderr)
        c = get_boto_credentials(role_arn, self.args.account_name)
        print(f"export AWS_ACCESS_KEY_ID={c['AccessKeyId']}")
        print(f"export AWS_SECRET_ACCESS_KEY={c['SecretAccessKey']}")
        print(f"export AWS_SESSION_TOKEN={c['SessionToken']}")


def run():
    cmd = AssumeRoleCommand("config.yaml")
    cmd.run()

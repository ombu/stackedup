import logging

from stacks.command import (
    AccountCommand,
    get_boto_credentials,
)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")


class AssumeRoleCommand(AccountCommand):
    def __init__(self, config_file):
        super().__init__(config_file)

    def run(self):
        c = get_boto_credentials(self.config, self.args.account_name)
        print(f'export AWS_ACCESS_KEY_ID={c["AccessKeyId"]}')
        print(f'export AWS_SECRET_ACCESS_KEY={c["SecretAccessKey"]}')
        print(f'export AWS_SESSION_TOKEN={c["SessionToken"]}')


def run():
    cmd = AssumeRoleCommand("config.yaml")
    cmd.run()

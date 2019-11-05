import logging
from stacks.config import (
    config_get_stack_config,
    config_get_stack_region,
    config_get_project_name,
    config_get_account_id,
)
from stacks.stack import Stack
from stacks.command import (
    StackCommand,
    get_boto_client,
    get_boto_credentials,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


class UpdateCommand(StackCommand):
    def __init__(self):
        super().__init__()
        stack_config = config_get_stack_config(
            self.config, self.args.stack_type, self.args.name
        )
        self.stack = Stack(
            stack_type=self.args.stack_type,
            name=self.args.name,
            stack_config=stack_config,
            region=config_get_stack_region(
                self.config, self.args.stack_type, self.args.name
            ),
            template_dir="../infrastructure",
        )

    def run(self):
        if self.args.stack_type == "account":
            account_name = "_root"
        else:
            account_name = self.stack.account_name
        credentials = get_boto_credentials(self.config, account_name)
        project_name = config_get_project_name(self.config)
        account_id = config_get_account_id(
            self.config, self.args.stack_type, self.args.name
        )
        bucket = f"cloudformation-{project_name}-{account_id}"
        template_body = self.stack.package_template(credentials, bucket)
        client = get_boto_client("cloudformation", self.config, account_name)
        self.stack.update(client, TemplateBody=template_body)


def run():
    cmd = UpdateCommand()
    cmd.run()

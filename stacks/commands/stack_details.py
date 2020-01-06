import logging
from stacks.config import (
    config_get_stack_config,
    config_get_stack_region,
    config_get_role,
)
from stacks.stack import Stack
from stacks.command import (
    StackCommand,
    get_boto_client,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


class OutputsCommand(StackCommand):
    def __init__(self):
        super().__init__()
        stack_config = config_get_stack_config(
            self.config, self.args.stack_type, self.args.name
        )
        self.stack = Stack(
            project_name=self.project_name,
            stack_type=self.args.stack_type,
            name=self.args.name,
            stack_config=stack_config,
            region=config_get_stack_region(
                self.config, self.args.stack_type, self.args.name
            ),
        )

    def run(self):
        if self.args.stack_type == "account":
            account_name = "_root"
        else:
            account_name = self.stack.account_name
        role_arn = config_get_role(self.config, account_name)
        region_name = config_get_stack_region(
            self.config, self.stack.type, self.stack.name
        )
        client = get_boto_client("cloudformation", role_arn, account_name, region_name)
        details = self.stack.get_details(client)
        print(f"\nStack Name: {self.stack.stack_name}")
        print(f"Status: {details['StackStatus']}\n")
        print(Stack.tabulate_results(details["Parameters"]) + "\n")
        if "Outputs" in details.keys():
            print(Stack.tabulate_results(details["Outputs"]))


def run():
    cmd = OutputsCommand()
    cmd.run()

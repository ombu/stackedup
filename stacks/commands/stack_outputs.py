import logging

from stacks.config import config_get_stack_config, config_get_stack_region
from stacks.stack import Stack
from stacks.command import (
    StackCommand,
    get_boto_client,
)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


class OutputsCommand(StackCommand):
    def __init__(self, config_file):
        super().__init__(config_file)
        stack_config = config_get_stack_config(
            self.config, self.args.stack_type, self.args.name
        )
        self.stack = Stack(
            stack_type=self.args.stack_type,
            name=self.args.name,
            region=config_get_stack_region(
                self.config, self.args.stack_type, self.args.name
            ),
            stack_config=stack_config,
        )

    def run(self):
        client = get_boto_client("cloudformation", self.config, self.stack.account_name)
        outputs = self.stack.get_outputs(client)
        print(Stack.tabulate_outputs(outputs))


def run():
    cmd = OutputsCommand("config.yaml")
    cmd.run()

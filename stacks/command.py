import argparse
from stacks.config import config_load


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


class InstanceCommand(BaseCommand):
    def __init__(self, *args):
        super().__init__(*args)
        self.argparser.add_argument(
            "stack_type", type=str #, choices=self.config["stack_types"]
        )
        self.argparser.add_argument(
            "name", type=str #, choices=self.config["instance_list"]
        )


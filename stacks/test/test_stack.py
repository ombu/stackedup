import unittest
import yaml
from stacks.stack import Stack
import datetime
import os


class TestStack(unittest.TestCase):
    def setUp(self):
        self.live_stack_yaml = """
account: aws_account_for_the_stack
parameters:
  Parameter1: my_key
  Parameter2: t3.small
stack_name: the_stack_name"""
        self.new_stack_yaml = """
account: aws_account_for_the_stack
parameters:
  Parameter1: my_key
  Parameter2: t3.small"""
        self.test_template_path = os.path.join(
            os.path.realpath(os.path.dirname(__file__)), "templates"
        )
        self.live_stack = Stack(
            stack_type="cluster",
            name="core",
            stack_config=yaml.load(self.live_stack_yaml, Loader=yaml.FullLoader),
            template_dir=self.test_template_path,
        )
        self.new_stack = Stack(
            stack_type="cluster",
            name="core",
            stack_config=yaml.load(self.new_stack_yaml, Loader=yaml.FullLoader),
            template_dir=self.test_template_path,
        )

    def test_stack_name_property(self):
        self.assertEqual("the_stack_name", self.live_stack.stack_name)
        date = f"{datetime.datetime.now():%Y%m%d%H%M}"
        self.assertEqual("cluster-core-%s" % date, self.new_stack.stack_name)

    def test_get_template_path(self):
        template_file = os.path.join(self.test_template_path, "cluster.yaml")
        self.assertEqual(template_file, self.new_stack.get_template_path())
        pass

    def test_get_template_body(self):
        template_file = os.path.join(self.test_template_path, "cluster.yaml")
        f = open(template_file, "r")
        template_body = f.read()
        f.close()
        self.assertEqual(template_body, self.new_stack.get_template_body())


if __name__ == "__main__":
    unittest.main()

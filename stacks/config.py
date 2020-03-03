import yaml
import logging
import boto3

logger = logging.getLogger(__name__)


def config_load(config_file):
    c = yaml.load(config_file, Loader=yaml.FullLoader)
    c["instance_list"] = list(c["instances"].keys())
    logger.debug("Found these instances in config.yaml: %s" % c["instance_list"])
    return c


def config_get_account_name(config, stack_type, name):
    if stack_type == "account":
        return "_root"
    elif stack_type == "cluster":
        return config[_pluralize_component_name(stack_type)][name]["account"]
    else:
        return config["instances"][name]["account"]


def config_get_account_id(config, stack_type, name):
    if stack_type == "account":
        return config_get_active_account_id()
    else:
        account_name = config_get_account_name(config, stack_type, name)
    aws_account_id = config["accounts"][account_name]["id"]
    return aws_account_id


def config_get_project_name(config):
    return config["project_name"]


def config_get_stack_config(config, stack_type, name):
    """Returns the slice of a project config file that defines a specific stack"""
    if stack_type in ["account", "cluster"]:
        return config[_pluralize_component_name(stack_type)][name]
    else:
        instance = config["instances"][name]
        stack_config = instance[stack_type]
        # The stack is a service withing an instance, so import the account and
        # cluster from the instance
        stack_config.update(
            {"account": instance["account"], "cluster": instance["cluster"],}
        )
        return stack_config


def config_get_stack_region(config, stack_type, name):
    """Returns the slice of a project config file that defines a specific stack"""
    if stack_type == "account":
        # The region for the account is irrelevant because accounts are global, but
        # `stackedup` functions require one
        return "us-west-2"
    if stack_type == "cluster":
        return config[_pluralize_component_name(stack_type)][name]["region"]
    else:
        cluster = config["instances"][name]["cluster"]
        return config["clusters"][cluster]["region"]


def config_get_role(config, account):
    return config["accounts"][account]["provisioner_role_arn"]


def _pluralize_component_name(name):
    return name + "s"


def config_get_active_account_id():
    return boto3.client("sts").get_caller_identity().get("Account")


def config_get_cloudformation_bucket(config, account):
    return config["accounts"][account]["cloudformation_bucket"]

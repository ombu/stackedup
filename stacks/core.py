import yaml
import argparse
import logging

logger = logging.getLogger(__name__)


def config_load(config_file):
    f = open(config_file, "r")
    c = yaml.load(f, Loader=yaml.FullLoader)
    f.close()
    c["instance_list"] = [i["name"] for i in c["instances"]]
    logger.info("Found these instances in config.yaml: %s" % c["instance_list"])
    return c


def config_get_account_id(config, instance_name):
    aws_account_name = next(
        (
            item["account"]
            for item in config["instances"]
            if item["name"] == instance_name
        ),
        False,
    )
    aws_account_id = next(
        (item["id"] for item in config["accounts"] if item["name"] == aws_account_name),
        False,
    )
    logger.info("Using AWS account ID %s" % aws_account_id)
    return aws_account_id


def config_get_stack_parameters(config, instance_name, stack_type):
    parameters = None
    stack = next(
        (
            item[stack_type]
            for item in config["instances"]
            if item["name"] == instance_name
        ),
        False,
    )
    # If stack is a dict, the parameters must be in the key 'parameters'
    if isinstance(stack, dict):
        parameters = stack["parameters"]
    # If stack is a string, it's a reference that needs to be resolved
    elif isinstance(stack, str):
        parameters = next(
            (
                item["parameters"]
                for item in config[stack_type + "s"]  # Precarious pluralization
                if item["name"] == stack
            ),
            False,
        )
    parameters["EnvironmentType"] = instance_name
    out = _reformat_parameters(parameters)
    return out


def _reformat_parameters(parameter_dict):
    items = [
        {"ParameterKey": k, "ParameterValue": v} for k, v in parameter_dict.items()
    ]
    return items


def config_get_project_name(config):
    return config["project_name"]


def parse_args(config):
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", type=str, choices=config["instance_list"])
    parser.add_argument("stack_type", type=str, choices=config["stack_types"])
    return parser.parse_args()


# config = config_load()

# args = parse_args()

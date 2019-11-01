import yaml
import logging

logger = logging.getLogger(__name__)


def config_load(config_file):
    f = open(config_file, "r")
    c = yaml.load(f, Loader=yaml.FullLoader)
    f.close()
    c["instance_list"] = list(c["instances"].keys())
    logger.info("Found these instances in config.yaml: %s" % c["instance_list"])
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
        return None
        #return config_get_active_account_id()
    else:
        account_name = config_get_account_name(config, stack_type, name)
    aws_account_id = config["accounts"][account_name]["id"]
    return aws_account_id


def config_get_stack_parameters(config, name, stack_type):
    parameters = None
    if stack_type == "account":
        r = config["accounts"]["_root"]
        return (
            {
                "ParameterKey": "OrganizationalUnitId",
                "ParameterValue": r["organizatuional_unit_id"],
            },
            {
                "ParameterKey": "OrganizationalRoot",
                "ParameterValue": r["organizational_root"],
            },
            {"ParameterKey": "AccountName", "ParameterValue": name},
        )
    else:
        try:
            config[_pluralize_component_name(stack_type)][name]["parameters"]
            stack = config[_pluralize_component_name(stack_type)][name]
        except KeyError:
            stack = config["instances"][name][stack_type]
        # If stack is a dict, the parameters must be in the key 'parameters'
        if isinstance(stack, dict):
            parameters = stack["parameters"]
        # If stack is a string, it's a reference that needs to be resolved
        elif isinstance(stack, str):
            parameters = config[_pluralize_component_name(stack_type)][stack][
                "parameters"
            ]
        parameters["EnvironmentType"] = name
        out = _reformat_parameters(parameters)
        return out


def _reformat_parameters(parameter_dict):
    items = [
        {"ParameterKey": k, "ParameterValue": v} for k, v in parameter_dict.items()
    ]
    return items


def config_get_project_name(config):
    return config["project_name"]


def config_get_stack_name(config, name, stack_type):
    if stack_type in ["account", "cluster"]:
        return config[_pluralize_component_name(stack_type)][name]["stack_name"]
    else:
        return config["instances"][name][stack_type]["stack_name"]


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


def _pluralize_component_name(name):
    return name + "s"


# def config_get_active_account_id():
#     return get_boto_client("sts").get_caller_identity().get("Account")

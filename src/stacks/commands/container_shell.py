import logging
from os import path

from stacks.command import InstanceCommand, get_boto_client
from stacks.config import (
    config_get_stack_config,
    config_get_stack_region,
)
from stacks.stack import Stack

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")

# Default file names of supported EC2 Instance Connect key pairs
# https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-connect-methods.html#ec2-instance-connect-connecting-aws-cli
DEFAULT_SSH_PUBLIC_KEY_FILENAMES = (
    "id_rsa.pub",
    "id_ed25519.pub",
)


def get_default_public_key():
    """
    Try to get a default public key of the user to use.
    """
    ssh_dir = path.join(path.expanduser("~"), ".ssh")
    for public_key_name in DEFAULT_SSH_PUBLIC_KEY_FILENAMES:
        public_key_path = path.join(ssh_dir, public_key_name)
        if path.exists(public_key_path):
            return public_key_path
    return None


def get_private_key(public_key_path):
    """
    Assume the private key is named the same as the public key and
    return it's path.
    """
    return public_key_path.removesuffix(".pub")


def validate_public_key(public_key_path):
    """
    Validate that the public key exist.
    """
    if not path.exists(public_key_path):
        logger.error(f"Could not find the required SSH public key {public_key_path}")
        exit(1)

    if not public_key_path.endswith(".pub"):
        logger.error("The public key path a .pub file")
        exit(1)


def validate_private_key(private_key_path):
    """
    Validate that the private key exist.
    """
    if not path.exists(private_key_path):
        logger.error(f"Could not find the required SSH key {private_key_path}")
        exit(1)


class ContainerShellCommand(InstanceCommand):
    def __init__(self):
        super().__init__()
        stack_type = "application"
        stack_config_instance = config_get_stack_config(self.config, self.args.service, self.args.name)
        self.stack = Stack(
            project_name=self.project_name,
            stack_type=stack_type,
            name=self.args.name,
            stack_config=stack_config_instance,
            region=config_get_stack_region(self.config, stack_type, self.args.name),
        )

        cluster_name = stack_config_instance["cluster"]
        stack_config_cluster = config_get_stack_config(self.config, "cluster", cluster_name)
        self.cluster_stack = Stack(
            project_name=self.project_name,
            stack_type="cluster",
            name=cluster_name,
            stack_config=stack_config_cluster,
            region=config_get_stack_region(self.config, stack_type, self.args.name),
        )

    def add_arguments(self):
        super().add_arguments()
        self.argparser.add_argument(
            "--public_key",
            type=str,
            help="Use a specified public key (.pub)",
        )
        self.argparser.add_argument(
            "--config_key",
            action="store_true",
            help="Use the provided ssh key pair in config.yaml",
        )
        self.argparser.add_argument("service", type=str)
        self.argparser.add_argument("ecsservice", type=str)
        self.argparser.add_argument("container_name", type=str)

    def run(self):
        public_key_name = get_default_public_key()
        key_name = get_private_key(public_key_name)

        if self.args.config_key:
            ssh_dir = path.join(path.expanduser("~"), ".ssh")
            parameter_key_name = self.cluster_stack.get_parameters()["KeyName"]
            key_name = path.join(ssh_dir, parameter_key_name)
            validate_private_key(key_name)

        if self.args.public_key:
            public_key_name = self.args.public_key
            key_name = get_private_key(public_key_name)
            validate_public_key(public_key_name)
            validate_private_key(key_name)

        region_name = config_get_stack_region(self.config, self.stack.type, self.stack.name)
        cf_client = get_boto_client("cloudformation", region_name)
        stack_details = self.stack.get_details(cf_client)
        cluster_name = self.cluster_stack.get_output(cf_client, "ECSClusterName")

        try:
            service_name = [
                d["OutputValue"]
                for d in stack_details["Outputs"]
                if d["OutputKey"] == f"ServiceName{self.args.ecsservice}"
            ][0]
        except IndexError:
            logger.error(f"Unable to find output ServiceName{self.args.ecsservice} in {cluster_name}")
            exit(1)

        # Get the task id from list_tasks
        ecs_client = get_boto_client("ecs", region_name)
        response = ecs_client.list_tasks(
            cluster=cluster_name,
            serviceName=service_name,
        )
        task_id = response["taskArns"][0]

        # Get the container instance ARN and the container id from ecs describe_tasks
        response = ecs_client.describe_tasks(cluster=cluster_name, tasks=(task_id,))
        container_instance_id = response["tasks"][0]["containerInstanceArn"]
        container_id = None
        try:
            container_id = [
                d["runtimeId"]
                for d in response["tasks"][0]["containers"]
                if d["name"] == self.args.container_name
            ][0]
            logger.info(f"Found an instance {container_instance_id} running the container {container_id}")
        except KeyError:
            logger.error(f"Unable to find a container id for the task {task_id}")
            exit(1)

        # Get the instance public IP from ec2 describe-instances
        response = ecs_client.describe_container_instances(
            cluster=cluster_name, containerInstances=(container_instance_id,)
        )
        instance_id = response["containerInstances"][0]["ec2InstanceId"]
        ec2_client = get_boto_client("ec2", region_name)
        response = ec2_client.describe_instances(InstanceIds=(instance_id,))
        instance = response["Reservations"][0]["Instances"][0]
        public_dns_name = instance["PublicDnsName"]

        # Use EC2 Instance Connect to push public key into authorized keys
        if not self.args.config_key:
            with open(public_key_name) as ssh_public_key_file:
                public_key_file = ssh_public_key_file.read().strip()

            ec2_instance_connect_client = get_boto_client("ec2-instance-connect", region_name)
            response = ec2_instance_connect_client.send_ssh_public_key(
                AvailabilityZone=instance["Placement"]["AvailabilityZone"],
                InstanceId=instance_id,
                InstanceOSUser="ec2-user",
                SSHPublicKey=public_key_file,
            )
            logger.info(f"Trying to add {key_name} to authorized keys in running the container {instance_id}")
            if not response["Success"]:
                logger.error(f"Unable to send SSH public key to instance {instance_id}")
                exit(1)
            else:
                logger.info(f"Added {key_name} to container {instance_id}")

        ssh_command = f"ssh -t -i {key_name} ec2-user@{public_dns_name} docker exec -it {container_id} sh"
        print(ssh_command)


def run():
    cmd = ContainerShellCommand()
    cmd.run()

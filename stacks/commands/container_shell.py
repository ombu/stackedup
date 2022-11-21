import logging
from os import path

from stacks.config import (
    config_get_stack_config,
    config_get_stack_region,
    config_get_role,
)

from stacks.stack import Stack

from stacks.command import (
    InstanceCommand,
    get_boto_client,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")


class ContainerShellCommand(InstanceCommand):
    def __init__(self):
        super().__init__()
        stack_type = "application"
        stack_config_instance = config_get_stack_config(
            self.config, self.args.service, self.args.name
        )
        self.stack = Stack(
            project_name=self.project_name,
            stack_type=stack_type,
            name=self.args.name,
            stack_config=stack_config_instance,
            region=config_get_stack_region(self.config, stack_type, self.args.name),
        )

        cluster_name = stack_config_instance["cluster"]
        stack_config_cluster = config_get_stack_config(
            self.config, "cluster", cluster_name
        )
        self.cluster_stack = Stack(
            project_name=self.project_name,
            stack_type="cluster",
            name=cluster_name,
            stack_config=stack_config_cluster,
            region=config_get_stack_region(self.config, stack_type, self.args.name),
        )

    def add_arguments(self):
        super().add_arguments()
        self.argparser.add_argument("service", type=str)
        self.argparser.add_argument("ecsservice", type=str)
        self.argparser.add_argument("container_name", type=str)

    def run(self):

        key_name = self.cluster_stack.get_parameters()["KeyName"]
        ssh_key = path.join(path.expanduser("~"), ".ssh", key_name)
        if not path.exists(ssh_key):
            logger.error(f"Could not find the required SSH key {ssh_key}")
            exit(1)

        account_name = self.stack.account_name
        role_arn = config_get_role(self.config, account_name)
        region_name = config_get_stack_region(
            self.config, self.stack.type, self.stack.name
        )
        cf_client = get_boto_client(
            "cloudformation", role_arn, account_name, region_name
        )
        stack_details = self.stack.get_details(cf_client)
        cluster_name = self.cluster_stack.get_output(cf_client, "ECSClusterName")

        service_name = None
        try:
            service_name = [
                d["OutputValue"]
                for d in stack_details["Outputs"]
                if d["OutputKey"] == f"ServiceName{self.args.ecsservice}"
            ][0]
        except IndexError:
            logger.error(
                f"Unable to find output ServiceName{self.args.ecsservice} in {cluster_name}"
            )
            exit(1)

        # Get the task id from list_tasks
        ecs_client = get_boto_client("ecs", role_arn, account_name, region_name)
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
            logger.info(
                f"Found an instance {container_instance_id} running the container {container_id}"
            )
        except KeyError:
            logger.error(f"Unable to find a container id for the task {task_id}")
            exit(1)

        # Get the instance public IP from ec2 describe-instances
        response = ecs_client.describe_container_instances(
            cluster=cluster_name, containerInstances=(container_instance_id,)
        )
        instance_id = response["containerInstances"][0]["ec2InstanceId"]
        ec2_client = get_boto_client("ec2", role_arn, account_name, region_name)
        response = ec2_client.describe_instances(InstanceIds=(instance_id,))
        public_dns_name = response["Reservations"][0]["Instances"][0]["PublicDnsName"]

        ssh_command = (
            f"ssh -t -i ~/.ssh/{key_name} ec2-user@{public_dns_name} "
            f"docker exec -it {container_id} sh"
        )
        print(ssh_command)


def run():
    cmd = ContainerShellCommand()
    cmd.run()

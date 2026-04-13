import logging
import json

from stacks.command import InstanceCommand, get_boto_client
from stacks.config import (
    config_get_stack_config,
    config_get_stack_region,
)
from stacks.stack import Stack

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")


class DatabaseShellCommand(InstanceCommand):
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
        self.argparser.add_argument("service", type=str)

    def run(self):
        LOCAL_DB_PORT = 25432
        region_name = config_get_stack_region(self.config, self.stack.type, self.stack.name)
        cf_client = get_boto_client("cloudformation", region_name)
        stack_details = self.stack.get_details(cf_client)
        cluster_name = self.cluster_stack.get_output(cf_client, "ECSClusterName")

        # Get database parameters
        database_instance = ""
        database_endpoint = ""
        database_user_secret = ""
        database_port = ""
        database_user = ""
        database_pass = ""

        # Get database stack from service cluster stack
        database_stack = cf_client.describe_stack_resources(
            StackName=stack_details["StackId"], LogicalResourceId="Database"
        )
        database_stack_arn = database_stack["StackResources"][0]["PhysicalResourceId"]

        # Get database stack outputs
        database_stack_details = cf_client.describe_stacks(StackName=database_stack_arn)
        database_stack_outputs = database_stack_details["Stacks"][0]["Outputs"]

        for output in database_stack_outputs:
            if output.get("OutputKey") == "DatabaseInstance":
                database_instance = output.get("OutputValue")
            if output.get("OutputKey") == "DatabaseEndpoint":
                database_endpoint = output.get("OutputValue")
            if output.get("OutputKey") == "DatabaseUserSecret":
                database_user_secret = output.get("OutputValue")

        rds_client = get_boto_client("rds", region_name)
        response = rds_client.describe_db_instances(DBInstanceIdentifier=database_instance)
        database_port = response["DBInstances"][0]["Endpoint"]["Port"]

        secrets_client = get_boto_client("secretsmanager", region_name)
        response = secrets_client.get_secret_value(SecretId=database_user_secret)
        secret_string = response["SecretString"]
        database_user = json.loads(secret_string)["username"]
        database_pass = json.loads(secret_string)["password"]

        # Get the task id from list_tasks
        ecs_client = get_boto_client("ecs", region_name)

        # Get the container instance ARN
        response = ecs_client.list_container_instances(
            cluster=cluster_name,
            status="ACTIVE",
        )
        container_instance_id = response["containerInstanceArns"][0]

        # Get the instance_id from ec2 describe-instances
        response = ecs_client.describe_container_instances(
            cluster=cluster_name, containerInstances=(container_instance_id,)
        )
        instance_id = response["containerInstances"][0]["ec2InstanceId"]

        # Start forward session
        ssm_client = get_boto_client("ssm", region_name)
        response = ssm_client.start_session(
            Target=instance_id,
            DocumentName="AWS-StartPortForwardingSessionToRemoteHost",
            Parameters={
                "host": [database_endpoint],
                "portNumber": [str(database_port)],
                "localPortNumber": [str(LOCAL_DB_PORT)],
            },
        )
        session_id = response["SessionId"]

        ssh_command = f"PGPASSWORD={database_pass} psql -h 127.0.0.1 -p {LOCAL_DB_PORT} -U {database_user} -d {database_pass} && aws ssm terminate-session --region {region_name} --session-id {session_id}"
        print(ssh_command)


def run():
    cmd = DatabaseShellCommand()
    cmd.run()

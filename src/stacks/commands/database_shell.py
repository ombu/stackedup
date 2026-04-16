import json
import logging
import os
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from stacks.command import InstanceCommand, get_boto_client
from stacks.config import (
    config_get_stack_config,
    config_get_stack_region,
)
from stacks.stack import Stack

logger = logging.getLogger(__name__)


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
        self.argparser.add_argument("database", type=str)
        self.argparser.add_argument(
            "--local-port",
            type=int,
            default=25432,
            help="Local port to forward the database connection to (default: 25432)",
        )
        self.argparser.add_argument(
            "--database-key",
            type=str,
            default="PostgresDatabase",
            help="Database logical key in the stack (default: PostgresDatabase)",
        )

    def run(self):
        local_db_port = self.args.local_port
        database_key = self.args.database_key
        region_name = config_get_stack_region(self.config, self.stack.type, self.stack.name)
        cf_client = get_boto_client("cloudformation", region_name)

        # Check for ClusterStack reference
        if "ClusterStack" in self.stack.stack_config["parameters"]:
            stack_details = self.cluster_stack.get_details(cf_client)
        # If no ClusterStack parameter assume Database output in service stack
        else:
            stack_details = self.stack.get_details(cf_client)

        cluster_name = self.cluster_stack.get_output(cf_client, "ECSClusterName")

        # Get database stack from service cluster stack
        database_stack = cf_client.describe_stack_resources(
            StackName=stack_details["StackId"], LogicalResourceId=database_key
        )
        database_stack_arn = database_stack["StackResources"][0]["PhysicalResourceId"]

        # Get database stack outputs
        database_stack_details = cf_client.describe_stacks(StackName=database_stack_arn)
        database_stack_outputs = database_stack_details["Stacks"][0]["Outputs"]

        database_instance = None
        database_endpoint = None
        database_user_secret = None

        for output in database_stack_outputs:
            key = output.get("OutputKey")
            if key == "DatabaseInstance":
                database_instance = output.get("OutputValue")
            elif key == "DatabaseEndpoint":
                database_endpoint = output.get("OutputValue")
            elif key == "DatabaseUserSecret":
                database_user_secret = output.get("OutputValue")

        missing = [
            k
            for k, v in {
                "DatabaseInstance": database_instance,
                "DatabaseEndpoint": database_endpoint,
                "DatabaseUserSecret": database_user_secret,
            }.items()
            if v is None
        ]
        if missing:
            logger.error(f"Missing required database stack outputs: {', '.join(missing)}")
            exit(1)

        rds_client = get_boto_client("rds", region_name)
        response = rds_client.describe_db_instances(DBInstanceIdentifier=database_instance)
        database_port = response["DBInstances"][0]["Endpoint"]["Port"]

        secrets_client = get_boto_client("secretsmanager", region_name)
        response = secrets_client.get_secret_value(SecretId=database_user_secret)
        secret = json.loads(response["SecretString"])
        database_user = secret["username"]
        database_pass = secret["password"]

        # Get an active container instance to use as the SSM tunnel target
        ecs_client = get_boto_client("ecs", region_name)
        response = ecs_client.list_container_instances(
            cluster=cluster_name,
            status="ACTIVE",
        )
        container_instance_arns = response["containerInstanceArns"]
        if not container_instance_arns:
            logger.error(f"No active container instances found in cluster {cluster_name}")
            exit(1)
        container_instance_id = container_instance_arns[0]

        # Get the EC2 instance ID
        response = ecs_client.describe_container_instances(
            cluster=cluster_name, containerInstances=(container_instance_id,)
        )
        instance_id = response["containerInstances"][0]["ec2InstanceId"]
        logger.info(f"Using EC2 instance {instance_id} for SSM tunnel")

        # Start port-forwarding session
        ssm_command = [
            "aws",
            "ssm",
            "start-session",
            "--region",
            region_name,
            "--target",
            instance_id,
            "--document-name",
            "AWS-StartPortForwardingSessionToRemoteHost",
            "--parameters",
            f"host={database_endpoint},portNumber={database_port},localPortNumber={local_db_port}",
        ]

        fd, path_str = tempfile.mkstemp(prefix="ssm-", suffix=".log")
        os.close(fd)
        log_path = Path(path_str)
        ssm_proc = None
        session_id = None

        try:
            # Start SSM port-forwarding session
            try:
                with open(log_path, "w") as log_file:
                    ssm_proc = subprocess.Popen(
                        ssm_command,
                        stdout=log_file,
                        stderr=log_file,
                        start_new_session=True,
                    )
                logger.info("Starting SSM port-forwarding session...")
            except OSError as e:
                logger.error(f"Failed to start SSM session: {e}")
                exit(1)

            # Wait for the session ID to appear in the log before connecting
            timeout = time.time() + 30
            while time.time() < timeout:
                text = log_path.read_text(errors="ignore")
                match = re.search(r"SessionId[:\s]+([^\s]+)", text)
                if match:
                    session_id = match.group(1)
                    logger.info(f"Started SSM session {session_id}")
                    break
                time.sleep(0.1)

            if not session_id:
                logger.error("Timed out waiting for SSM session to start")
                exit(1)

            # Wait for the local port to be accepting connections before launching psql
            logger.info(f"Waiting for local port {local_db_port} to be ready...")
            port_ready = False
            timeout = time.time() + 30
            while time.time() < timeout:
                try:
                    with socket.create_connection(("127.0.0.1", local_db_port), timeout=1):
                        port_ready = True
                        break
                except OSError:
                    time.sleep(0.1)

            if not port_ready:
                logger.error(f"Timed out waiting for local port {local_db_port} to be ready")
                exit(1)

            # Open the psql shell directly — blocks until the user exits
            subprocess.run(
                [
                    "psql",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(local_db_port),
                    "-U",
                    database_user,
                    "-d",
                    self.args.database,
                ],
                env={**os.environ, "PGPASSWORD": database_pass},
            )
        finally:
            log_path.unlink(missing_ok=True)
            # Always terminate the SSM session and stop the tunnel process
            if session_id:
                try:
                    subprocess.run(
                        [
                            "aws",
                            "ssm",
                            "terminate-session",
                            "--region",
                            region_name,
                            "--session-id",
                            session_id,
                        ],
                        check=False,
                        capture_output=True,
                    )
                    logger.info(f"Terminated SSM session {session_id}")
                except OSError as e:
                    logger.warning(f"Failed to terminate SSM session {session_id}: {e}")
            if ssm_proc is not None:
                ssm_proc.terminate()
                try:
                    ssm_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    ssm_proc.kill()


def run():
    cmd = DatabaseShellCommand()
    cmd.run()

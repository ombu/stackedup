# Stackedup

[![Python tests](https://github.com/ombu/stacks/actions/workflows/python-tests.yml/badge.svg)](https://github.com/ombu/stacks/actions/workflows/python-tests.yml)

stackedup provides tools to launch and manage micro-service based applications
in AWS using CloudFormation.

stackedup relies on three core abstractions:

- **account**: An AWS account used by the application
- **cluster**: A collection of AWS resources where applications run, such as
  compute capacity, database, networking configuration, etc that allows running
  one more instances
- **instance**: An instance of an application, such as testing or production
- **service**: An application service, such as an API or a web UI

As much as possible, stackedup aims to get out of the way between you and your
CloudFormation Stacks. Clusters, instances and services are plain CloudFormation
stacks. stackedup helps you launch and update them, recording state and current
parameters in an instance manifest, a YAML file usually named `config.yaml. A
common instance manifest, may look like this:

```yaml
---
project_name: my-project

# The types of stacks supported in this project
stack_types:
  - pipeline
  - application

# The AWS accounts involved
accounts:
  my-aws-account:
    cloudformation_bucket: <my-bucket> # A bucket name used for building and deploying stacks
    id: my-aws-account
    provisioner_role_arn: arn:aws:iam::123...:role/my-role # The ARN of the IAM role stacked
                                                           # should assume to run AWS API call
                                                           # commands on this account

# The clusters
clusters:
  dev:
    stack_name: my-project-cluster-dev-2005251008         # Once launched, this key stores the
                                                          # stack name for future updates
    account: my-aws-account
    region: us-west-2
    parameters:                                            # These are the CloudFormation parameters
      KeyName: my-ssh-key                                  # sent to the stack

instances:

  # One instance of the application, called testing
  testing:
    account: ombu
    cluster: dev
    application:
      stack_name: my-project-testing-2005251108
      parameters:
        ClusterStack: my-project-cluster-dev-2005251008
        DatabaseHost: ...rds.amazonaws.com
        DatabaseName: my-project-testing
        DatabaseUser: my-project-testing
        Domain: my-project.com
        ECRRepository: ....dkr.ecr.us-east-1.amazonaws.com
        EnvironmentType: testing
        ImageTag: '0.1.10'
        SentryDsn: "https://...@....ingest.sentry.io/..."

  # Another instance of the application, called staging
  staging:
    account: ombu
    cluster: dev
    application:
      stack_name: my-project-stagomg-2005251208
      parameters:
      ...
```

## Installation

Stacked up is distributed in the Python Package Index (PyPI). To install it:

    pip install stackedup

This will install the current version of stackedup. Older projects may depend on
specific versions, so stacked up is usually installed as part of the project
Python requirements. In a project with a `requirements.txt` file:

    pip install -r requirements.txt

## Usage

To run any stackedup command, your AWS CLI environment must be configured such
that you are able to assume the roles included in the accounts section of the
instance manifest. When running commands, stacked up will attempt to assume
these roles.

### Launching stacks

For a cluster:

    stack-launch cluster <cluster-name>

For an instance service:

    stack-launch <service> <instance>

### Obtaining details on a running stack

For a cluster:

    stack-details cluster <cluster-name>

    stack-details <service> <instance>

### Updating stacks

After updating the parameters for an existing stack in the instance manifest
(often \_config.yaml`), update the instance:

    stack-update <service> <instance>

### Opening a shell session in a service container (==experimental==)

For service stacks that run
[ECS Services](<[https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html)>)
stacked up includes an experimental command to start a shell session in one of
the service containers:

    $ container-shell <instance> <service> <service-name> <container>
    ssh -t -i <ssh-key> ec2-user@ec2-54-218-12-133... docker exec -it 380f02d109d9a038e1e1909e0f31e85a6491312d3c29726b269bde8621ce1212 sh

The command returns an SSH command, so it's often ran in backticks as command
substitution:

    $ `container-shell <instance> <service> <service-name> <container>`
    #    (← you are in container bash session)

## AWS accounts

stackedup can manage instances across AWS accounts, through IAM roles. The AWS
accounts their IAM roles for a project are defined in the `accounts:` section of
the instance manifest (usually a file named `config.yaml`). stackedup commands
automatically switch roles into the right account when performing stack
operations. One can also use the information in the instance manifest to assume
a role for a desired account in the AWS console:

1. Log into the AWS console for the master AWS account and open the _Switch
   Role_ view
   ([screenshot](https://tickets.ombuweb.com/attachments/download/8875/20200310-1038-aws-switch-role-1.png))

2. Obtain the desired AWS account ID and role name for the target role from the
   instance manifest and enter it into the _Switch Role_ view:
   ([screenshot](https://tickets.ombuweb.com/attachments/download/8876/20200310-1038-aws-switch-role.png))

## Developing stacked up

### Running tests

```console
python -m unittest discover
```

### Packaged and distribute

Edit `setup.py` with the desired target version. Then:

```console
pip install wheel twine
python setup.py sdist bdist_wheel
python -m twine upload dist/stackedup-<tag>*

```

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="stackedup",
    version="0.0.14",
    author="OMBU",
    author_email="martin@ombuweb.com",
    url="https://github.com/ombu/stacks",
    description="Tooling to help manage CloudFormation stacks",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=["boto3==1.34.53", "tabulate==0.9.0", "PyYaml==6.0.1", "awscliv2"],
    entry_points={
        "console_scripts": [
            "assume-role = stacks.commands.assume_role:run",
            "stack-launch = stacks.commands.stack_launch:run",
            "stack-update = stacks.commands.stack_update:run",
            "stack-details = stacks.commands.stack_details:run",
            "container-shell = stacks.commands.container_shell:run",
        ],
    },
)

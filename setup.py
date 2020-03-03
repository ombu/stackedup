import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="stackedup",
    version="0.0.7",
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
    python_requires=">=3.6",
    install_requires=["boto3==1.10.20", "awscli==1.16.284", "tabulate==0.8.5"],
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

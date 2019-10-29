import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="stacks-pkg-ombu",
    version="0.1",
    author="OMBU",
    author_email="martin@ombuweb.com",
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
    install_requires=["boto3==1.10.2", "awscli==1.16.266"],
)

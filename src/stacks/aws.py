"""AWS sessions using the standard credential chain and the CLI role cache."""

from functools import lru_cache
from pathlib import Path

import boto3
from botocore.credentials import JSONFileCache


@lru_cache(maxsize=1)
def get_boto_session():
    session = boto3.Session()
    # Boto3 already reads the CLI's SSO token cache. Assume-role credentials
    # otherwise live only in memory, so share the CLI's disk cache as well.
    resolver = session._session.get_component("credential_provider")
    resolver.get_provider("assume-role").cache = JSONFileCache(
        str(Path.home() / ".aws" / "cli" / "cache")
    )
    return session

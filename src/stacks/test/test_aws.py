import hashlib
import json
from unittest import mock

import pytest
from botocore.credentials import JSONFileCache, ReadOnlyCredentials
from botocore.exceptions import NoCredentialsError

from stacks.aws import get_boto_session
from stacks.command import get_boto_assumed_credentials, get_boto_client, get_boto_credentials


@pytest.fixture(autouse=True)
def clear_caches():
    get_boto_session.cache_clear()
    get_boto_client.cache_clear()
    get_boto_assumed_credentials.cache_clear()
    yield
    get_boto_session.cache_clear()
    get_boto_client.cache_clear()
    get_boto_assumed_credentials.cache_clear()


def test_session_uses_cli_role_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_PROFILE", raising=False)
    with mock.patch("stacks.aws.Path.home", return_value=tmp_path):
        session = get_boto_session()
    resolver = session._session.get_component("credential_provider")
    cache = resolver.get_provider("assume-role").cache
    assert isinstance(cache, JSONFileCache)
    cache["test"] = {"Credentials": {"AccessKeyId": "test"}}
    assert (tmp_path / ".aws" / "cli" / "cache" / "test.json").exists()
    assert get_boto_session() is session


def test_exported_credentials_take_precedence(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.write_text(
        "[profile selected]\naws_access_key_id = profile-key\naws_secret_access_key = profile-secret\n"
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("AWS_PROFILE", "selected")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "exported-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "exported-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "exported-token")
    assert get_boto_credentials() == {
        "AccessKeyId": "exported-key",
        "SecretAccessKey": "exported-secret",
        "SessionToken": "exported-token",
    }


def test_profile_reads_cached_role_without_sts(tmp_path, monkeypatch):
    config = tmp_path / "config"
    role_arn = "arn:aws:iam::123456789012:role/example"
    config.write_text(
        f"[profile selected]\nrole_arn = {role_arn}\n"
        "source_profile = source\nrole_session_name = test-session\n"
        "[profile source]\naws_access_key_id = source-key\naws_secret_access_key = source-secret\n"
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("AWS_PROFILE", "selected")
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_DEFAULT_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    # AWS CLI/botocore cache keys hash the sorted AssumeRole parameters.
    params = {"RoleArn": role_arn, "RoleSessionName": "test-session"}
    key = hashlib.sha1(json.dumps(params, sort_keys=True).encode(), usedforsecurity=False).hexdigest()
    cache = JSONFileCache(str(tmp_path / ".aws" / "cli" / "cache"))
    cache[key] = {
        "Credentials": {
            "AccessKeyId": "cached-key",
            "SecretAccessKey": "cached-secret",
            "SessionToken": "cached-token",
            "Expiration": "2099-01-01T00:00:00Z",
        }
    }
    with (
        mock.patch("stacks.aws.Path.home", return_value=tmp_path),
        mock.patch("botocore.client.BaseClient._make_api_call") as api_call,
    ):
        assert get_boto_credentials()["AccessKeyId"] == "cached-key"
        api_call.assert_not_called()


def test_client_keeps_session_credential_provider():
    with mock.patch("stacks.command.get_boto_session") as session:
        assert get_boto_client("ec2", "us-west-2") is session.return_value.client.return_value
        session.return_value.client.assert_called_once_with("ec2", region_name="us-west-2")


def test_credentials_are_not_frozen_forever():
    with mock.patch("stacks.command.get_boto_session") as session:
        credentials = session.return_value.get_credentials.return_value
        credentials.get_frozen_credentials.side_effect = [
            ReadOnlyCredentials("old", "secret", "token"),
            ReadOnlyCredentials("new", "secret", "token"),
        ]
        assert get_boto_credentials()["AccessKeyId"] == "old"
        assert get_boto_credentials()["AccessKeyId"] == "new"


def test_missing_credentials():
    with mock.patch("stacks.command.get_boto_session") as session:
        session.return_value.get_credentials.return_value = None
        with pytest.raises(NoCredentialsError):
            get_boto_credentials()


def test_assume_role_uses_shared_session():
    with mock.patch("stacks.command.get_boto_session") as session:
        sts = session.return_value.client.return_value
        sts.assume_role.return_value = {"Credentials": {"AccessKeyId": "assumed"}}
        assert get_boto_assumed_credentials("arn:role", "account") == {"AccessKeyId": "assumed"}
        session.return_value.client.assert_called_once_with("sts")
        sts.assume_role.assert_called_once_with(RoleArn="arn:role", RoleSessionName="account_session")

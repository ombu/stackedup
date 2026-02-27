import pytest
from unittest.mock import Mock, patch


@pytest.fixture(autouse=True)
def _clear_command_caches():
    # Clear caches to avoid cross-test contamination.
    from stacks import command

    command.get_boto_client.cache_clear()
    command.get_boto_credentials.cache_clear()
    command._get_caller_identity.cache_clear()


def test_get_boto_client_skips_assume_role_when_already_in_role():
    from stacks.command import get_boto_client

    role_arn = "arn:aws:iam::123456789012:role/path/CustomAdminAccess"
    current_arn = "arn:aws:sts::123456789012:assumed-role/CustomAdminAccess/my-session"

    mock_sts = Mock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": current_arn,
        "Account": "123456789012",
    }
    mock_cf = Mock()

    def client_side_effect(service_name, *args, **kwargs):
        if service_name == "sts":
            return mock_sts
        if service_name == "cloudformation":
            return mock_cf
        raise AssertionError(f"Unexpected client: {service_name}")

    with patch("stacks.command.boto3.client") as mock_client:
        mock_client.side_effect = client_side_effect

        c = get_boto_client("cloudformation", role_arn, "acct", "us-west-2")
        assert c is mock_cf
        assert not mock_sts.assume_role.called

        # Ensure we didn't pass explicit credentials to the target client.
        cloudformation_calls = [
            call for call in mock_client.call_args_list if call.args[0] == "cloudformation"
        ]
        assert len(cloudformation_calls) == 1
        assert "aws_access_key_id" not in cloudformation_calls[0].kwargs


def test_get_boto_client_assumes_role_when_not_in_role():
    from stacks.command import get_boto_client

    role_arn = "arn:aws:iam::123456789012:role/CustomAdminAccess"
    current_arn = "arn:aws:sts::999999999999:assumed-role/OtherRole/my-session"

    mock_sts = Mock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": current_arn,
        "Account": "999999999999",
    }
    mock_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "AKIA_TEST",
            "SecretAccessKey": "SECRET_TEST",
            "SessionToken": "TOKEN_TEST",
        }
    }
    mock_cf = Mock()

    captured_cf_kwargs = {}

    def client_side_effect(service_name, *args, **kwargs):
        nonlocal captured_cf_kwargs
        if service_name == "sts":
            return mock_sts
        if service_name == "cloudformation":
            captured_cf_kwargs = dict(kwargs)
            return mock_cf
        raise AssertionError(f"Unexpected client: {service_name}")

    with patch("stacks.command.boto3.client") as mock_client:
        mock_client.side_effect = client_side_effect
        c = get_boto_client("cloudformation", role_arn, "acct", "us-west-2")

    assert c is mock_cf
    mock_sts.assume_role.assert_called_once()
    assert captured_cf_kwargs.get("aws_access_key_id") == "AKIA_TEST"
    assert captured_cf_kwargs.get("aws_secret_access_key") == "SECRET_TEST"
    assert captured_cf_kwargs.get("aws_session_token") == "TOKEN_TEST"


def test_get_boto_client_skips_assume_role_when_already_in_account():
    from stacks.command import get_boto_client

    role_arn = "arn:aws:iam::123456789012:role/CustomAdminAccess"
    # Different role name, but same account id.
    current_arn = "arn:aws:sts::123456789012:assumed-role/OtherRole/my-session"

    mock_sts = Mock()
    mock_sts.get_caller_identity.return_value = {"Arn": current_arn, "Account": "123456789012"}
    mock_cf = Mock()

    def client_side_effect(service_name, *args, **kwargs):
        if service_name == "sts":
            return mock_sts
        if service_name == "cloudformation":
            return mock_cf
        raise AssertionError(f"Unexpected client: {service_name}")

    with patch("stacks.command.boto3.client") as mock_client:
        mock_client.side_effect = client_side_effect
        c = get_boto_client("cloudformation", role_arn, "acct", "us-west-2")

    assert c is mock_cf
    assert not mock_sts.assume_role.called


def test_get_boto_client_force_assumes_even_when_already_in_account():
    from stacks.command import get_boto_client

    role_arn = "arn:aws:iam::123456789012:role/CustomAdminAccess"
    current_arn = "arn:aws:sts::123456789012:assumed-role/OtherRole/my-session"

    mock_sts = Mock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": current_arn,
        "Account": "123456789012",
    }
    mock_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "AKIA_FORCED",
            "SecretAccessKey": "SECRET_FORCED",
            "SessionToken": "TOKEN_FORCED",
        }
    }
    mock_cf = Mock()

    captured_cf_kwargs = {}

    def client_side_effect(service_name, *args, **kwargs):
        nonlocal captured_cf_kwargs
        if service_name == "sts":
            return mock_sts
        if service_name == "cloudformation":
            captured_cf_kwargs = dict(kwargs)
            return mock_cf
        raise AssertionError(f"Unexpected client: {service_name}")

    with patch("stacks.command.boto3.client") as mock_client:
        mock_client.side_effect = client_side_effect
        c = get_boto_client(
            "cloudformation",
            role_arn,
            "acct",
            "us-west-2",
            force_assume_role=True,
        )

    assert c is mock_cf
    mock_sts.assume_role.assert_called_once()
    assert captured_cf_kwargs.get("aws_access_key_id") == "AKIA_FORCED"


def test_verbose_prints_decision_to_stderr(capsys):
    from stacks.command import get_boto_client

    role_arn = "arn:aws:iam::123456789012:role/CustomAdminAccess"
    current_arn = "arn:aws:sts::123456789012:assumed-role/CustomAdminAccess/my-session"

    mock_sts = Mock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": current_arn,
        "Account": "123456789012",
    }
    mock_cf = Mock()

    def client_side_effect(service_name, *args, **kwargs):
        if service_name == "sts":
            return mock_sts
        if service_name == "cloudformation":
            return mock_cf
        raise AssertionError(f"Unexpected client: {service_name}")

    with patch("stacks.command.boto3.client") as mock_client:
        mock_client.side_effect = client_side_effect
        get_boto_client(
            "cloudformation",
            role_arn,
            "acct",
            "us-west-2",
            verbose=True,
        )

    out = capsys.readouterr().err
    assert "Current identity:" in out
    assert "Target role:" in out
    assert "ambient credentials" in out


def test_get_role_credentials_if_needed_returns_none_when_already_in_role():
    from stacks.command import get_role_credentials_if_needed

    role_arn = "arn:aws:iam::123456789012:role/CustomAdminAccess"
    current_arn = "arn:aws:sts::123456789012:assumed-role/CustomAdminAccess/my-session"

    mock_sts = Mock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": current_arn,
        "Account": "123456789012",
    }

    with patch("stacks.command.boto3.client") as mock_client:
        mock_client.side_effect = lambda service_name, *a, **k: (
            mock_sts if service_name == "sts" else Mock()
        )
        creds = get_role_credentials_if_needed(role_arn, "acct")

    assert creds is None
    assert not mock_sts.assume_role.called

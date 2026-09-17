import pytest

from src.newwords_api.auth import is_authorized
from src.newwords_api.config import ConfigError, Settings


def test_authorization_requires_matching_bearer_token():
    assert is_authorized("Bearer secret", "secret") is True
    assert is_authorized("bearer secret", "secret") is True
    assert is_authorized("Bearer wrong", "secret") is False
    assert is_authorized(None, "secret") is False
    assert is_authorized("Basic secret", "secret") is False


def test_settings_reads_required_environment_and_normalizes_customer_id():
    settings = Settings.from_env(
        {
            "GOOGLE_ADS_CLIENT_ID": "client",
            "GOOGLE_ADS_CLIENT_SECRET": "secret",
            "GOOGLE_ADS_REFRESH_TOKEN": "refresh",
            "GOOGLE_ADS_CUSTOMER_ID": "136-765-4543",
            "SEO_DATA_API_KEY": "api-key",
        }
    )

    assert settings.client_id == "client"
    assert settings.customer_id == "1367654543"
    assert settings.api_version == "v24"


def test_settings_rejects_missing_required_value():
    with pytest.raises(ConfigError, match="GOOGLE_ADS_CLIENT_SECRET"):
        Settings.from_env(
            {
                "GOOGLE_ADS_CLIENT_ID": "client",
                "GOOGLE_ADS_REFRESH_TOKEN": "refresh",
                "GOOGLE_ADS_CUSTOMER_ID": "1367654543",
                "SEO_DATA_API_KEY": "api-key",
            }
        )


def test_settings_rejects_invalid_customer_and_version():
    base = {
        "GOOGLE_ADS_CLIENT_ID": "client",
        "GOOGLE_ADS_CLIENT_SECRET": "secret",
        "GOOGLE_ADS_REFRESH_TOKEN": "refresh",
        "SEO_DATA_API_KEY": "api-key",
    }

    with pytest.raises(ConfigError, match="GOOGLE_ADS_CUSTOMER_ID"):
        Settings.from_env({**base, "GOOGLE_ADS_CUSTOMER_ID": "not-a-customer"})

    with pytest.raises(ConfigError, match="GOOGLE_ADS_API_VERSION"):
        Settings.from_env(
            {
                **base,
                "GOOGLE_ADS_CUSTOMER_ID": "1367654543",
                "GOOGLE_ADS_API_VERSION": "latest",
            }
        )

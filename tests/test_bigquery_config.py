import json

import pytest

from api.lib._config import BigQuerySettings, ConfigError


def valid_env():
    service_account = {
        "type": "service_account",
        "project_id": "kinetic-genre-508803-t8",
        "client_email": "test@example.iam.gserviceaccount.com",
        "private_key": "not-a-real-key",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return {
        "SEO_DATA_API_KEY": "api-key",
        "GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON": json.dumps(service_account),
    }


def test_bigquery_settings_use_service_account_project_and_safe_defaults():
    settings = BigQuerySettings.from_env(valid_env())

    assert settings.project_id == "kinetic-genre-508803-t8"
    assert settings.location == "US"
    assert settings.maximum_bytes_billed == 1_000_000_000
    assert settings.api_key == "api-key"


def test_bigquery_settings_allow_project_and_billing_cap_override():
    env = valid_env()
    env["GOOGLE_CLOUD_PROJECT"] = "query-project"
    env["BIGQUERY_LOCATION"] = "US"
    env["BIGQUERY_MAX_BYTES_BILLED"] = "250000000"

    settings = BigQuerySettings.from_env(env)

    assert settings.project_id == "query-project"
    assert settings.maximum_bytes_billed == 250_000_000


@pytest.mark.parametrize(
    "mutator",
    [
        lambda env: env.pop("SEO_DATA_API_KEY"),
        lambda env: env.pop("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON"),
        lambda env: env.__setitem__("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON", "not-json"),
        lambda env: env.__setitem__("BIGQUERY_MAX_BYTES_BILLED", "0"),
    ],
)
def test_bigquery_settings_reject_incomplete_or_invalid_configuration(mutator):
    env = valid_env()
    mutator(env)

    with pytest.raises(ConfigError):
        BigQuerySettings.from_env(env)

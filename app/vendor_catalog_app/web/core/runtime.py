from __future__ import annotations

from functools import lru_cache

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.env import (
    TVENDOR_ALLOW_TEST_ROLE_OVERRIDE,
    TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS,
    get_env_bool,
)
from vendor_catalog_app.repository import VendorRepository


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig.from_env()


@lru_cache(maxsize=1)
def get_repo() -> VendorRepository:
    return VendorRepository(get_config())


def trust_forwarded_identity_headers(config: AppConfig) -> bool:
    is_dev_env = bool(getattr(config, "is_dev_env", False))
    return get_env_bool(
        TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS,
        default=is_dev_env,
    )


def testing_role_override_enabled(config: AppConfig) -> bool:
    is_dev_env = bool(getattr(config, "is_dev_env", False))
    return get_env_bool(
        TVENDOR_ALLOW_TEST_ROLE_OVERRIDE,
        default=is_dev_env,
    )

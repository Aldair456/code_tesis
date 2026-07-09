from typing import Dict, Any

from common.regulatory.profiles.base import CountryProfile
from common.regulatory.exceptions import TaxIdValidationError, CurrencyValidationError


def apply_business_defaults(profile: CountryProfile, data: Dict[str, Any]) -> Dict[str, Any]:
    return profile.apply_business_defaults(data)


def validate_business_payload(profile: CountryProfile, data: Dict[str, Any]) -> None:
    ruc = data.get("ruc")
    if ruc is not None:
        profile.validate_tax_id(ruc)

    currency = data.get("currency")
    if currency is not None:
        profile.validate_currency(currency)


def validate_fs_currency(profile: CountryProfile, currency: str) -> None:
    profile.validate_currency(currency)

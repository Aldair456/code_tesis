from dataclasses import dataclass
from typing import Dict, Any, Optional

from common.models.models import Evaluator
from common.regulatory.applicator import (
    apply_business_defaults,
    validate_business_payload,
    validate_fs_currency,
)
from common.regulatory.evaluator_lookup import get_evaluator
from common.regulatory.exceptions import UnknownCountryError
from common.regulatory.profiles.base import CountryProfile
from common.regulatory.registry import CountryRegistry


@dataclass(frozen=True)
class RegulatoryContext:
    profile: CountryProfile
    evaluator: Evaluator
    country: str

    @classmethod
    def for_evaluator(cls, evaluator_id: str) -> "RegulatoryContext":
        evaluator = get_evaluator(evaluator_id)
        if not evaluator:
            raise UnknownCountryError("UNKNOWN")
        country = (getattr(evaluator, "country", None) or "PE").strip().upper()
        profile = CountryRegistry.get(country)
        return cls(profile=profile, evaluator=evaluator, country=country)

    @classmethod
    def for_country_code(cls, country_code: str, evaluator: Optional[Evaluator] = None) -> "RegulatoryContext":
        """Útil en tests sin BD."""
        country = (country_code or "PE").strip().upper()
        profile = CountryRegistry.get(country)
        if evaluator is None:
            raise ValueError("evaluator requerido para RegulatoryContext.for_country_code en runtime")
        return cls(profile=profile, evaluator=evaluator, country=country)

    def apply_business_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return apply_business_defaults(self.profile, data)

    def validate_business_payload(self, data: Dict[str, Any]) -> None:
        validate_business_payload(self.profile, data)

    def validate_fs_currency(self, currency: str) -> None:
        validate_fs_currency(self.profile, currency)

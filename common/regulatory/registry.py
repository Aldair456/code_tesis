from typing import Dict

from common.regulatory.exceptions import UnknownCountryError
from common.regulatory.profiles.base import CountryProfile
from common.regulatory.profiles.peru import PeruProfile
from common.regulatory.profiles.chile import ChileProfile

_PROFILES: Dict[str, CountryProfile] = {
    PeruProfile.code: PeruProfile,
    ChileProfile.code: ChileProfile,
}


class CountryRegistry:
    @staticmethod
    def get(country_code: str) -> CountryProfile:
        code = (country_code or "").strip().upper()
        profile = _PROFILES.get(code)
        if not profile:
            raise UnknownCountryError(code)
        return profile

    @staticmethod
    def registered_codes() -> frozenset[str]:
        return frozenset(_PROFILES.keys())

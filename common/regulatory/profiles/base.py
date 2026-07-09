from dataclasses import dataclass
from typing import Dict, Any
import re

from common.regulatory.exceptions import TaxIdValidationError, CurrencyValidationError


@dataclass(frozen=True)
class CountryProfile:
    code: str
    tax_id_label: str
    tax_id_pattern: str
    default_currency: str
    allowed_currencies: frozenset[str]
    default_scale_type: str = "THOUSANDS"

    def validate_tax_id(self, value: str) -> None:
        if not value or not str(value).strip():
            raise TaxIdValidationError(self.tax_id_label, f"{self.tax_id_label} es requerido.")
        cleaned = str(value).strip()
        if not re.fullmatch(self.tax_id_pattern, cleaned):
            raise TaxIdValidationError(
                self.tax_id_label,
                f"{self.tax_id_label} inválido para {self.code}.",
            )

    def normalize_tax_id(self, value: str) -> str:
        return str(value).strip()

    def validate_currency(self, currency: str) -> None:
        if currency not in self.allowed_currencies:
            raise CurrencyValidationError(currency, self.allowed_currencies)

    def apply_business_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(data)
        if not result.get("currency"):
            result["currency"] = self.default_currency
        if not result.get("scale_type"):
            result["scale_type"] = self.default_scale_type
        if result.get("ruc"):
            result["ruc"] = self.normalize_tax_id(result["ruc"])
        return result

    def currency_symbol(self, currency: str) -> str:
        symbols = {
            "PEN": "S/",
            "CLP": "$",
            "USD": "US$",
            "EUR": "€",
        }
        return symbols.get(currency, currency)

    def note_currency_hint(self) -> str:
        if self.code == "CL":
            return "pesos chilenos o dólares"
        return "soles o dólares"

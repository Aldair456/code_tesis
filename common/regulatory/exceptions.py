class RegulatoryError(Exception):
    """Base para errores de reglas por país."""


class UnknownCountryError(RegulatoryError):
    def __init__(self, country_code: str):
        super().__init__(f"País no soportado: {country_code}")
        self.country_code = country_code


class TaxIdValidationError(RegulatoryError):
    def __init__(self, label: str, message: str):
        super().__init__(message)
        self.label = label


class CurrencyValidationError(RegulatoryError):
    def __init__(self, currency: str, allowed: frozenset[str]):
        allowed_str = ", ".join(sorted(allowed))
        super().__init__(f"Moneda '{currency}' no permitida. Permitidas: {allowed_str}")
        self.currency = currency

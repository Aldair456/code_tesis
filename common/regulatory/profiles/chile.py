from common.regulatory.profiles.base import CountryProfile

ChileProfile = CountryProfile(
    code="CL",
    tax_id_label="RUT",
    tax_id_pattern=r"\d{8,20}",
    default_currency="CLP",
    allowed_currencies=frozenset({"CLP", "USD", "EUR"}),
)

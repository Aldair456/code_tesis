from common.regulatory.profiles.base import CountryProfile

PeruProfile = CountryProfile(
    code="PE",
    tax_id_label="RUC",
    tax_id_pattern=r"\d{11}",
    default_currency="PEN",
    allowed_currencies=frozenset({"PEN", "USD", "EUR"}),
)

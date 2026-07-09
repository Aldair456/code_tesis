from marshmallow import Schema, fields, EXCLUDE
class CalculatedOutputResponseSchema(Schema):
    """
    Esquema optimizado solo para serialización (dump)
    """

    # --capos de financial datapoint
    id = fields.UUID(allow_none=True)
    output_id = fields.Str(allow_none=True)
    value = fields.Float(allow_none=True)
    year = fields.Integer(allow_none=True)
    period_type = fields.Str(allow_none=True)
    period_identifier = fields.Str(allow_none=True)
    is_covenant_metric = fields.Bool(allow_none=True)
    financial_statement_id = fields.Str(allow_none=True)
    created_at = fields.DateTime(allow_none=True)
    updated_at = fields.DateTime(allow_none=True)

    # -- account_
    output_name = fields.String(allow_none=True)
    output_category = fields.String(allow_none=True)
    output_format = fields.String(allow_none=True)
    output_description = fields.String(allow_none=True)

    class Meta:
        unknown = EXCLUDE


class OutputResponseSchema(Schema):
    """
    Esquema optimizado solo para serialización (dump) del modelo Output
    """
    id = fields.UUID(allow_none=True)
    name = fields.String(allow_none=True)
    script = fields.String(allow_none=True)
    format = fields.String(allow_none=True)
    category = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    evaluator_id = fields.Str(allow_none=True)
    created_at = fields.DateTime(allow_none=True)
    updated_at = fields.DateTime(allow_none=True)

    class Meta:
        unknown = EXCLUDE


class DerivedCashflowResponseSchema(Schema):
    id = fields.UUID(allow_none=True)
    evaluator_id = fields.Str(allow_none=True)
    name = fields.String(allow_none=True)
    script = fields.String(allow_none=True)
    format = fields.String(allow_none=True)
    category = fields.String(allow_none=True)
    priority = fields.Integer(allow_none=True)
    description = fields.String(allow_none=True)
    created_at = fields.DateTime(allow_none=True)
    updated_at = fields.DateTime(allow_none=True)

    class Meta:
        unknown = EXCLUDE


class CalculatedDerivedCashflowResponseSchema(Schema):
    id = fields.UUID(allow_none=True)
    derived_cashflow_id = fields.Str(allow_none=True)
    financial_statement_id = fields.Str(allow_none=True)
    value = fields.Float(allow_none=True)
    year = fields.Integer(allow_none=True)
    period_type = fields.Str(allow_none=True)
    period_identifier = fields.Str(allow_none=True)
    created_at = fields.DateTime(allow_none=True)
    updated_at = fields.DateTime(allow_none=True)
    dcf_name = fields.String(allow_none=True)
    dcf_format = fields.String(allow_none=True)
    dcf_category = fields.String(allow_none=True)
    dcf_description = fields.String(allow_none=True)
    dcf_priority = fields.Integer(allow_none=True)

    class Meta:
        unknown = EXCLUDE
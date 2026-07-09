from marshmallow import Schema, fields, validate, EXCLUDE, missing, pre_load
from datetime import datetime


class JobCreateSchema(Schema):
    """Esquema para crear jobs - atributos mínimos y opcionales permitidos"""
    class Meta:
        unknown = EXCLUDE
    id = fields.UUID(required=True)
    # Campos opcionales
    job_name = fields.Str(allow_none=True)
    metadata = fields.Dict(allow_none=True)
    job_description = fields.Str(allow_none=True)
    priority = fields.Int(validate=validate.Range(min=1, max=10))
    config_data = fields.Dict(allow_none=True)
    max_retries = fields.Int(validate=validate.Range(min=0, max=10))


# class JobUpdateSchema(Schema):
#     """Esquema para actualizar jobs - solo campos actualizables"""
#
#     class Meta:
#         unknown = EXCLUDE
#
#     # Campos actualizables
#     job_name = fields.Str(validate=validate.Length(min=3, max=255))
#     job_description = fields.Str(allow_none=True)
#     status = fields.Str(
#         validate=validate.OneOf([
#             'PENDING', 'RUNNING', 'COMPLETED',
#             'FAILED', 'CANCELLED', 'RETRY'
#         ])
#     )
#     priority = fields.Int(validate=validate.Range(min=1, max=10))
#     config_data = fields.Dict(allow_none=True)
#     result_data = fields.Dict(allow_none=True)
#     error_message = fields.Str(allow_none=True)
#     started_at = fields.DateTime(allow_none=True)
#     completed_at = fields.DateTime(allow_none=True)
#     retry_count = fields.Int(validate=validate.Range(min=0))
#     max_retries = fields.Int(validate=validate.Range(min=0, max=10))


class JobUpdateSchema(Schema):
    """Esquema para actualizar jobs - solo campos actualizables"""

    class Meta:
        unknown = EXCLUDE

    @pre_load
    def remove_null_values(self, data, **kwargs):
        """Pre-procesador que elimina todos los campos con valor null"""
        return {
            key: value
            for key, value in data.items()
            if value is not None
        }

    # Campos actualizables - se omiten si no vienen o si vienen como null
    job_name = fields.Str(
        validate=validate.Length(min=3, max=255),
        load_default=missing  # En Marshmallow 3.x se usa load_default
    )
    job_description = fields.Str(
        allow_none=True,
        load_default=missing
    )
    status = fields.Str(
        validate=validate.OneOf([
            'PENDING', 'RUNNING', 'COMPLETED',
            'FAILED', 'CANCELLED', 'RETRY'
        ]),
        load_default=missing
    )
    priority = fields.Int(
        validate=validate.Range(min=1, max=10),
        load_default=missing
    )
    config_data = fields.Dict(
        allow_none=True,
        load_default=missing
    )
    result_data = fields.Dict(
        allow_none=True,
        load_default=missing
    )
    metadata = fields.Dict(
        allow_none=True,
        load_default=missing
    )
    error_message = fields.Str(
        allow_none=True,
        load_default=missing
    )
    started_at = fields.DateTime(
        allow_none=True,
        load_default=missing
    )
    completed_at = fields.DateTime(
        allow_none=True,
        load_default=missing
    )
    retry_count = fields.Int(
        validate=validate.Range(min=0),
        load_default=missing
    )
    max_retries = fields.Int(
        validate=validate.Range(min=0, max=10),
        load_default=missing
    )

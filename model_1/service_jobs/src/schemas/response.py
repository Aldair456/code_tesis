from marshmallow import Schema, fields, validate, EXCLUDE
from datetime import datetime
class JobResponseSchema(Schema):
    """Esquema para respuestas de API - serialización completa"""

    class Meta:
        unknown = EXCLUDE

    # Todos los campos para respuesta
    id = fields.UUID()
    job_name = fields.Str()
    job_description = fields.Str(allow_none=True)
    job_type = fields.Str()

    # Relación polimórfica
    resource_table = fields.Str()
    resource_id = fields.UUID()

    # Contexto
    business_id = fields.UUID()
    evaluator_id = fields.UUID()
    user_id = fields.UUID()

    user_name = fields.Str(allow_none=True)
    business_name = fields.Str(allow_none=True)

    # Estado y control
    status = fields.Str()
    priority = fields.Int()

    # Metadatos - con formato específico para notas financieras
    metadata = fields.Dict(allow_none=True)
    config_data = fields.Dict(allow_none=True)
    result_data = fields.Dict(allow_none=True)
    error_message = fields.Str(allow_none=True)

    # Timestamps
    started_at = fields.DateTime(allow_none=True)
    completed_at = fields.DateTime(allow_none=True)
    retry_count = fields.Int()
    max_retries = fields.Int()
    created_at = fields.DateTime(allow_none=True)
    updated_at = fields.DateTime(allow_none=True)

    # Campos calculados adicionales para contexto de notas
    duration_seconds = fields.Method('calculate_duration')
    # progress_percentage = fields.Method('calculate_progress')

    def calculate_duration(self, obj):
        """Calcula duración del job para jobs de procesamiento de notas"""
        if obj.get("started_at") and obj.get("completed_at"):
            delta = obj.get("completed_at") - obj.get("started_at")
            return int(delta.total_seconds())
        return None

    # def calculate_progress(self, obj):
    #     """Calcula progreso basado en result_data para jobs de notas"""
    #     if obj.result_data and obj.job_type in ['EXTRACT_NOTES', 'PROCESS_FS']:
    #         total = obj.result_data.get('total_notes_count', 0)
    #         processed = obj.result_data.get('processed_notes_count', 0)
    #         if total > 0:
    #             return round((processed / total) * 100, 2)
    #     return None
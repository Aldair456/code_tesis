# services/service_alerts/src/schemas/request.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID


# request.py - Para ENTRADA:
class SQSMessageRequest(BaseModel):
    """Schema para mensajes SQS de financial-alerts-queue"""
    financialStatementId: str = Field(..., description="ID del estado financiero")


class AlertCreateRequest(BaseModel):
    """Schema para crear una nueva alerta"""
    business_id: UUID = Field(..., description="ID del business")
    indicator: str = Field(..., description="Indicador financiero")
    previous_value: Optional[float] = Field(None, description="Valor anterior")
    current_value: Optional[float] = Field(None, description="Valor actual")
    is_archived: bool = Field(..., description="Si está archivada")
    description: str = Field(..., description="Descripción de la alerta")


class AlertUpdateRequest(BaseModel):
    """Schema para actualizar una alerta"""
    is_archived: Optional[bool] = Field(None, description="Si está archivada")




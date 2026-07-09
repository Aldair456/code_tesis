from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID
from common.models.utils import uuid_string_properties

@uuid_string_properties("id", "business_id")
class Alert(BaseModel):
    """
    Modelo para alertas financieras generadas automáticamente
    """
    id: UUID
    business_id: UUID
    indicator: str
    previous_value: Optional[float]
    current_value: Optional[float]
    description: str
    is_archived: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
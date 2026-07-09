from datetime import datetime

from common.models.models import (
    BaseIgnoreExtraModel,
    FinancialDataPoint,
    CalculatedOutput,
    CalculatedDerivedCashflow,
    Optional,
    UUID,
    List,
)
from common.models.utils import uuid_string_properties
from pydantic import Field


@uuid_string_properties("id", "evaluator_id")
class FinancialStatementConfig(BaseIgnoreExtraModel):
    """Config de visualización por evaluador (show_ltm, show_annualized)."""

    id: UUID
    evaluator_id: UUID
    show_ltm: bool = True
    show_annualized: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FinancialDataPointWithAccount(FinancialDataPoint):
    """
    Modelo extendido que incluye información de la cuenta asociada.
    Hereda todos los campos de FinancialDataPoint y agrega los campos de Account.
    """

    # Campos de la cuenta asociada
    account_name: str = Field(..., description="Nombre único de la cuenta")
    account_display_name: Optional[str] = Field(None, description="Nombre para mostrar de la cuenta")
    account_type: Optional[str] = Field(None, description="Tipo de cuenta")
    account_value_type: Optional[str] = Field(None, description="Tipo de valor de la cuenta")
    account_tags: Optional[List[str]] = Field(default_factory=list, description="Etiquetas de la cuenta")
    account_priority: Optional[int] = Field(None, description="Prioridad de la cuenta")


class CalculatedOutputWithOutput(CalculatedOutput):
    output_name: str
    output_format: str
    output_category: str
    output_description: Optional[str] = None


class CalculatedDerivedCashflowWithDef(CalculatedDerivedCashflow):
    dcf_name: str
    dcf_format: str
    dcf_category: str
    dcf_description: Optional[str] = None
    dcf_priority: Optional[int] = None






from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import datetime, date
from typing import Optional, List, Literal, Dict, Any
from uuid import UUID
from common.models.utils import uuid_string_properties
from decimal import Decimal
from enum import Enum


class BaseIgnoreExtraModel(BaseModel):
    model_config = ConfigDict(extra="ignore")





@uuid_string_properties("id", "evaluator_id", "sector_id")
class Business(BaseIgnoreExtraModel):
    id: UUID
    name: str
    ruc: str
    legal_name: Optional[str] = None
    account_executive: Optional[str] = None
    evaluator_id: UUID
    currency: str
    scale_type: str
    sector_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

@uuid_string_properties("id", "evaluator_id", "account_id")
class accounts_evaluator(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: UUID
    account_id: UUID
    account_group_name: str
    account_group_category: str
    priority: Optional[int] = None
    tags: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@uuid_string_properties("id", "business_id")
class Contact(BaseIgnoreExtraModel):
    id: UUID
    business_id: UUID
    name: Optional[str]
    position: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    created_at: datetime
    updated_at: datetime

@uuid_string_properties("id", "evaluator_id")
class User(BaseIgnoreExtraModel):
    id: UUID
    role: Literal['ADMIN', 'ANALYST', 'GERENCIA', 'SUPERVISOR']
    evaluator_id: UUID
    name: Optional[str]
    email: Optional[str]
    dni: Optional[str]
    phone_number: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

@uuid_string_properties("id", "business_id", "user_id")
class BusinessUser(BaseIgnoreExtraModel):
    id: Optional[UUID]
    business_id: UUID
    user_id: UUID
    created_at: datetime

@uuid_string_properties("id", "business_id")
class FinancialStatement(BaseIgnoreExtraModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    business_id: UUID
    years: List[int]
    periods: List[str]
    type: Optional[str]
    currency: Optional[str] = "PEN"
    scale_type: Optional[str] = "THOUSANDS"
    status: Optional[str]
    status_notes: Optional[str]
    notes_processed: Optional[bool] = False
    has_notes: Optional[bool] = True
    statement_periodicity: Optional[str]
    file_name: Optional[str]
    doc_type: Optional[str]
    total_notes_count: Optional[int] = 0
    processed_notes_count: Optional[int] = 0
    failed_notes_count: Optional[int] = 0
    ltm_composition: Optional[List]
    ltm_title: Optional[str]
    monthly_annualized_title: Optional[str] = None
    monthly_annualized_composition: Optional[List] = None
    is_blocked_by_admin: Optional[bool] = False
    auto_confirm: Optional[bool] = False
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "account_id", "financial_statement_id", "account_extract_id")
class FinancialDataPoint(BaseIgnoreExtraModel):
    id: UUID
    value: float
    financial_statement_id: UUID
    account_id: Optional[UUID] = None
    account_extract_id: Optional[UUID] = None
    details: Optional[List]  # JSON -> dict en Python
    year: Optional[int]
    period: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    @model_validator(mode="before")
    @classmethod
    def coalesce_account_id_from_extract(cls, data: Any) -> Any:
        """Filas legacy (post-migración 006): account_id NULL, account_extract_id poblado."""
        if isinstance(data, dict):
            if data.get("account_id") is None and data.get("account_extract_id") is not None:
                return {**data, "account_id": data["account_extract_id"]}
        return data


@uuid_string_properties("id", "financial_statement_id")
class FinancialCashflowDatapoint(BaseIgnoreExtraModel):
    id: UUID
    value: float
    financial_statement_id: UUID
    details: Optional[List]  # JSON -> dict en Python
    year: Optional[int]
    period: Optional[str]
    name: str  # 'Flujo de caja de operación', 'Flujo de caja de inversión', 'Flujo de caja de financiación', 'details', etc.
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "evaluator_id")
class Evaluator(BaseIgnoreExtraModel):
    id: UUID
    name: str
    country: str = "PE"
    created_at: datetime
    updated_at: datetime


@uuid_string_properties("id")
class AccountExtract(BaseIgnoreExtraModel):
    id: UUID
    name: str
    display_name: Optional[str]
    type: Optional[str]
    value_type: Optional[str]
    tags: Optional[List[str]]
    priority: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "evaluator_id")
class Account(BaseIgnoreExtraModel):
    """Catálogo accounts. Si la BD tiene evaluator_id (multi-tenant), puede venir en lecturas desde PostgreSQL."""

    id: UUID
    evaluator_id: Optional[UUID] = None
    name: str
    display_name: Optional[str]
    type: Optional[str]
    value_type: Optional[str]
    tags: Optional[List[str]]
    priority: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "account_id", "account_extract_id")
class MatchAccountExtract(BaseIgnoreExtraModel):
    id: UUID
    account_id: UUID
    account_extract_id: UUID
    order: Optional[int]
    created_at: Optional[datetime]


@uuid_string_properties("id")
class secciones(BaseIgnoreExtraModel):
    id: UUID
    seccion: str
    name: str


@uuid_string_properties("id", "seccion_id")
class sectores(BaseIgnoreExtraModel):
    id: UUID
    codigo: str
    name: str
    seccion_id: Optional[UUID]


@uuid_string_properties("id")
class AccountExtract(BaseIgnoreExtraModel):
    """Catálogo de cuentas para extracción IA (tabla account_extracts). Mismo shape que Account."""

    id: UUID
    name: str
    display_name: Optional[str]
    type: Optional[str]
    value_type: Optional[str]
    tags: Optional[List[str]]
    priority: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "account_id", "account_extract_id")
class MatchAccountExtract(BaseIgnoreExtraModel):
    """Puente cuenta de banco ↔ cuenta de extracción. Tabla match_account_extracts."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    account_id: UUID
    account_extract_id: UUID
    sort_order: Optional[int] = Field(default=None, alias="order")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "evaluator_id")
class Output(BaseIgnoreExtraModel):
    id: UUID
    name: str
    script: str
    format: str
    category: str
    description: Optional[str]
    evaluator_id: Optional[UUID] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "output_id", "financial_statement_id")
class CalculatedOutput(BaseIgnoreExtraModel):
    id: UUID
    output_id: UUID
    value: Optional[float]
    year: Optional[int]
    period_type: Literal["annual", "quarterly", "ltm", "monthly_annualized"] = "annual"
    period_identifier: Optional[str]
    is_covenant_metric: bool = False
    financial_statement_id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "evaluator_id")
class DerivedCashflow(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: UUID
    name: str
    script: str
    format: str
    category: str
    priority: int = 0
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "derived_cashflow_id", "financial_statement_id")
class CalculatedDerivedCashflow(BaseIgnoreExtraModel):
    id: UUID
    derived_cashflow_id: UUID
    financial_statement_id: UUID
    value: Optional[float] = None
    year: Optional[int] = None
    period_type: Literal["annual", "quarterly", "ltm", "monthly_annualized"] = "annual"
    period_identifier: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "user_id")
class ConfigDeal(BaseIgnoreExtraModel):
    id: UUID
    user_id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "config_id")
class StatusDeal(BaseIgnoreExtraModel):
    id: UUID
    config_id: UUID
    name: str
    color: Optional[str]
    position: int
    can_erase: Optional[bool] = False
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "config_id")
class ColumnDeal(BaseIgnoreExtraModel):
    id: UUID
    config_id: UUID
    title: Optional[str]
    position: Optional[int]
    data_type: Optional[str]
    optional: Optional[bool] = False
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "status_id", "user_id", "business_id", "evaluator_id")
class Deal(BaseIgnoreExtraModel):
    id: UUID
    title: str
    description: str
    value: Optional[Decimal] = Decimal('0')
    status_id: Optional[UUID]
    user_id: Optional[UUID]
    business_id: Optional[UUID]
    evaluator_id: Optional[UUID]
    is_closed: Optional[bool] = False
    closed_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "column_id", "deal_id")
class ColumnValueDeal(BaseIgnoreExtraModel):
    id: UUID
    column_id: UUID
    deal_id: UUID
    value: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


#aca lo relacionado a loans

@uuid_string_properties("id", "evaluator_id", "business_id", "deal_id")
class Loan(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: UUID
    business_id: UUID
    deal_id: Optional[UUID]
    title: str
    description: str
    principal_amount: Optional[Decimal] = Decimal('0')
    interest_rate: Optional[Decimal] = Decimal('0')
    start_year: Optional[int]
    end_year: Optional[int]
    start_date: Optional[date]
    total_periods: Optional[int]
    type: Optional[str]
    grace_periods_count: Optional[int]
    grace_type: Optional[str]
    amortization_frequency: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "loan_id")
class Covenant(BaseIgnoreExtraModel):
    id: UUID
    loan_id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "covenant_id", "output_id")
class CovenantDetail(BaseIgnoreExtraModel):
    id: UUID
    covenant_id: UUID
    output_id: UUID
    value: Optional[Decimal] = Decimal('0')
    year: Optional[int]

@uuid_string_properties("id", "loan_id")
class PaymentSchedule(BaseIgnoreExtraModel):
    id: UUID
    loan_id: UUID
    installments_count: Optional[int]
    frequency: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "payment_id")
class Installment(BaseIgnoreExtraModel):
    id: UUID
    payment_id: UUID
    period_number: Optional[int]
    interest: Optional[Decimal] = Decimal('0')
    principal: Optional[Decimal] = Decimal('0')
    due_date: Optional[date]

@uuid_string_properties("id")
class Sector(BaseIgnoreExtraModel):
    id: UUID
    name: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "sector_id")
class Subsector(BaseIgnoreExtraModel):
    id: UUID
    name: str
    sector_id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "user_id", "business_id", "evaluator_id")
class AnalystActivityLog(BaseIgnoreExtraModel):
    id: UUID
    user_id: UUID
    business_id: UUID
    evaluator_id: UUID

    name: Optional[str]
    module: Literal["CRM", "EEFF"]
    action: Literal[
        "CREATE_DEAL", "CLOSE_DEAL", "DELETE_DEAL",
        "UPLOAD_DOCUMENT", "ADJUST_FS", "NEW_FS_VERSION"
    ]
    description: Optional[str]
    extra_data: Optional[dict]

    created_at: Optional[datetime]


@uuid_string_properties("id", "business_id", "evaluator_id", "user_id", "resource_id")
class Job(BaseIgnoreExtraModel):
    id: UUID
    job_name: str
    job_description: Optional[str]
    job_type: str

    resource_table: str
    resource_id: UUID

    business_id: UUID
    evaluator_id: UUID
    user_id: Optional[UUID] = None

    status: str = 'PENDING'
    priority: int = 5

    config_data: Optional[Dict[str, Any]]
    result_data: Optional[Dict[str, Any]]
    error_message: Optional[str]

    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    retry_count: int = 0
    max_retries: int = 3

    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "financial_statement_id")
class Note(BaseIgnoreExtraModel):
    """Coincide con tabla notes: id, number, name, display_name, financial_statement_id, content, start_page, end_page, year (+ created_at, updated_at)."""
    id: Optional[UUID] = None
    number: str
    name: str
    display_name: str
    financial_statement_id: UUID
    content: Optional[Dict[str, Any]] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    year: Optional[int] = None
    # Campos legacy/opcionales (pueden no existir en la tabla)
    accounts: List[str] = []
    text: Optional[str] = None
    full_content_length: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None





@uuid_string_properties("id", "financial_statement_id")
class FinancialStatementVersion(BaseIgnoreExtraModel):
    id: UUID
    financial_statement_id: UUID
    comment: str
    description: str
    display_version: str
    version: int = 1
    is_active: bool = False
    datapoints: Optional[List[Dict[str, Any]]] = []
    created_at: Optional[datetime]
    updated_at: Optional[datetime]



@uuid_string_properties("id", "business_id", "deal_id", "user_id")
class BusinessLogEvent(BaseIgnoreExtraModel):
    id: UUID
    business_id: UUID
    deal_id: UUID
    user_id: Optional[UUID]
    title: Optional[str]
    date: Optional[datetime]
    data: Optional[List[Dict[str, Any]]]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]




@uuid_string_properties("id", "evaluator_id")
class RatingCategory(BaseIgnoreExtraModel):
    id: UUID
    category_code: str
    category_name: str
    description: Optional[str]
    numeric_value: Optional[int]
    evaluator_id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "rule_id", "target_id", "rating_category_id")
class RuleCondition(BaseIgnoreExtraModel):
    id: UUID
    rule_id: UUID
    target_type: str
    target_id: UUID
    rating_category_id: Optional[UUID]
    operator: Optional[str]
    min_value: Optional[int]
    max_value: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]





@uuid_string_properties("id", "evaluator_id", "sector_id", "subsector_id")
class RatingMethodology(BaseIgnoreExtraModel):
    id: UUID
    name: str
    description: Optional[str]
    evaluator_id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "evaluator_id", "sector_id", "subsector_id")
class RatingMethodologySector(BaseIgnoreExtraModel):#rating_methodology_sector
    id: UUID
    rating_methodology_id: UUID
    sector_id: UUID
    created_at: Optional[datetime]

@uuid_string_properties("id", "evaluator_id", "sector_id", "subsector_id")
class RatingMethodologySubSector(BaseIgnoreExtraModel):#rating_methodology_sector_subsector
    id: UUID
    rating_methodology_sector_id: UUID
    subsector_id: UUID
    created_at: Optional[datetime]
@uuid_string_properties("id", "rating_methodology_id")
class Rule(BaseIgnoreExtraModel):
    id: UUID
    rating_methodology_id: UUID
    name: str
    description: Optional[str]
    weight: Optional[float]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "rule_id", "target_id", "output_id", "account_id")
class SubRule(BaseIgnoreExtraModel):
    id: UUID
    rule_id: UUID
    type: str
    name: str
    description: Optional[str]
    target_type: Optional[str]
    output_id: Optional[UUID]
    account_id: Optional[UUID]
    weight: Optional[float]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "sub_rule_id", "rating_category_id")
class SubRuleCondition(BaseIgnoreExtraModel):
    id: UUID
    sub_rule_id: UUID
    rating_category_id: UUID
    label: Optional[str]
    description: Optional[str]
    operator: Optional[str]
    min_value: Optional[Decimal]
    max_value: Optional[Decimal]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "business_id", "rating_category_id")
class CompanyCreditRating(BaseIgnoreExtraModel):
    id: UUID
    business_id: UUID
    rating_category_id: UUID
    final_score: Optional[float]
    rating_value: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "credit_rating_id", "sub_rule_id", "rating_category_id")
class RatingCalculationLog(BaseIgnoreExtraModel):
    id: UUID
    credit_rating_id: UUID
    sub_rule_id: UUID
    rating_category_id: UUID
    intermediate_score: Optional[float]
    weight_applied: Optional[float]
    created_at: Optional[datetime]


#news
@uuid_string_properties("id")
class NodeType(BaseIgnoreExtraModel):
    id: UUID
    name: str
    description: Optional[str]
    category: Optional[str]
    input_schema: Optional[Dict[str, Any]]
    output_schema: Optional[Dict[str, Any]]
    version: Optional[str]
    is_active: Optional[bool]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "evaluator_id")
class Workflow(BaseIgnoreExtraModel):
    id: UUID
    name: str
    description: Optional[str]
    evaluator_id: UUID
    status: str
    version: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "workflow_id", "node_type_id")
class Node(BaseIgnoreExtraModel):
    id: UUID
    workflow_id: UUID
    node_type_id: UUID
    name: Optional[str]
    position_x: Optional[int]
    position_y: Optional[int]
    configuration: Optional[dict]
    retry_policy: Optional[dict]
    is_active: Optional[bool]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id","workflow_id" , "source_node_id", "target_node_id")
class NodeConnection(BaseIgnoreExtraModel):
    id: UUID
    workflow_id: UUID
    source_node_id: UUID
    target_node_id: UUID
    source_output_key: Optional[str] = None
    target_input_key: Optional[str] = None
    condition: Optional[dict] = None
    connection_order: Optional[int] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

@uuid_string_properties("id", "workflow_id")
class WorkflowExecution(BaseIgnoreExtraModel):
    id: UUID
    workflow_id: UUID
    status: str
    trigger_type: Optional[str]
    trigger_data: Optional[dict]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_context: Optional[dict]
@uuid_string_properties("id", "workflow_execution_id", "node_id")
class NodeExecution(BaseIgnoreExtraModel):
    id: UUID
    workflow_execution_id: UUID
    node_id: UUID
    status: str
    input_data: Optional[dict]
    output_data: Optional[dict]
    error_details: Optional[dict]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    retry_count: Optional[int]
    execution_time_ms: Optional[int]
@uuid_string_properties("id", "evaluator_id", "key_id")
class ApiKey(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: UUID
    key_id: str
    name: Optional[str]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]




@uuid_string_properties("id")
class Block(BaseIgnoreExtraModel):
    id: UUID
    name: str
    display_name: Optional[str] = None
    block_type: Literal['TRIGGER', 'ACTION', 'CONDITIONAL']
    output_schema: Optional[Dict[str, Any]] = None 
    parameters: List[Dict[str, Any]]  # Array de parámetros con {name, input_type, values?}
    lambda_arn: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "evaluator_id")
class Flow(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: Optional[UUID]
    name: str
    description: Optional[str]
    status: Literal['DRAFT', 'DEPLOYED', 'ACTIVE', 'FAIL_DEPLOYED'] = 'DRAFT'
    step_function_arn: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "flow_id", "block_id")
class FlowNode(BaseIgnoreExtraModel):
    id: UUID
    flow_id: UUID
    block_id: UUID
    name: str  
    position_x: int = 0
    position_y: int = 0
    parameters: Dict[str, Any]  
    outputs: Optional[Dict[str, Any]] = None  
    created_at: Optional[datetime]
    updated_at: Optional[datetime]



@uuid_string_properties("id")
class ModelJob(BaseIgnoreExtraModel):
    id: UUID
    job_name: Optional[str]
    job_description: Optional[str]


    status: str = 'PENDING'
    priority: int = 5

    metadata: Optional[Dict[str, Any]]
    config_data: Optional[Dict[str, Any]]
    result_data: Optional[Dict[str, Any]]
    error_message: Optional[str]

    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    retry_count: int = 0
    max_retries: int = 3

    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("user_id")
class WebSocketConnection(BaseIgnoreExtraModel):
    connection_id: str
    user_id: UUID
    watching: List[Dict[str, str]] = Field(default_factory=list)
    connected_at: Optional[datetime]
    last_activity: Optional[datetime]


# ============================================================================
# MODELOS DE TAREAS (TASKS)
# ============================================================================

@uuid_string_properties("id", "business_id")
class TaskKanbanConfig(BaseIgnoreExtraModel):
    id: UUID
    business_id: UUID
    created_at: datetime
    updated_at: datetime


@uuid_string_properties("id", "evaluator_id")
class ColumnTask(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: UUID
    name: str
    position: int
    color: Optional[str]
    system_stage: Literal['TODO', 'DOING', 'BLOCKED', 'DONE']
    created_at: datetime
    updated_at: datetime


@uuid_string_properties(
    "id", 
    "column_task_id", 
    "assigned_to_user_id", 
    "created_by_user_id",
    "evaluator_id"
)
class Task(BaseIgnoreExtraModel):
    id: UUID
    title: str
    description: Optional[str]
    
    # UBICACIÓN EN EL KANBAN
    column_task_id: UUID
    
    # ASIGNACIÓN
    assigned_to_user_id: Optional[UUID] = None
    created_by_user_id: Optional[UUID] = None
    evaluator_id: Optional[UUID] = None

    # OPTIMIZACIÓN DE BLOQUEO
    is_blocked: bool = False 
    blocked_reason: Optional[str] = None
    
    # GESTIÓN DE TIEMPO
    spent_hours: Decimal = Decimal('0')
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # VISIBILIDAD
    priority: Optional[Literal['BAJA', 'MEDIA', 'ALTA', 'URGENTE']] = None
    is_archived: bool = False
    
    created_at: datetime
    updated_at: datetime


@uuid_string_properties("id", "task_id")
class TaskBlockLog(BaseIgnoreExtraModel):
    id: UUID
    task_id: UUID
    blocked_at: datetime
    unblocked_at: Optional[datetime]
    blocked_reason: Optional[str]
    created_at: datetime


@uuid_string_properties("id", "deal_id", "task_id")
class DealTask(BaseIgnoreExtraModel):
    id: UUID
    deal_id: UUID
    task_id: UUID
    created_at: datetime


@uuid_string_properties("id", "task_id", "user_id")
class TaskUser(BaseIgnoreExtraModel):
    id: UUID
    task_id: UUID
    user_id: UUID
    role: Optional[str] = 'ASSIGNEE'
    created_at: datetime


@uuid_string_properties("id", "task_id")
class TaskSLA(BaseIgnoreExtraModel):
    id: UUID
    task_id: UUID
    start_date: datetime
    status: str = 'ON_TIME'
    extension_hours: Decimal = Decimal('0')
    is_breached: bool = False
    breach_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


@uuid_string_properties("id", "task_id")
class TaskComment(BaseIgnoreExtraModel):
    id: UUID
    task_id: UUID
    content: Dict[str, Any]  # jsonb en la base de datos
    content_type: Optional[str]
    created_at: datetime
    updated_at: datetime

@uuid_string_properties("id", "task_id")
class TaskCollaborativeDoc(BaseIgnoreExtraModel):
    id: UUID
    task_id: UUID
    yjs_state: Optional[bytes]  # BYTEA - Estado Yjs
    last_snapshot: Optional[bytes]  # BYTEA
    last_snapshot_version: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    
    def __init__(self, **data):
        # Convertir memoryview a bytes (PostgreSQL devuelve BYTEA como memoryview)
        if 'yjs_state' in data and isinstance(data['yjs_state'], memoryview):
            data['yjs_state'] = bytes(data['yjs_state'])
        if 'last_snapshot' in data and isinstance(data['last_snapshot'], memoryview):
            data['last_snapshot'] = bytes(data['last_snapshot'])
        super().__init__(**data)



@uuid_string_properties("id", "business_id", "deal_id", "user_id")
class CreditProposal(BaseIgnoreExtraModel):
    """Modelo para representar una propuesta de crédito."""
    
    id: UUID
    proposal_number: Optional[str] = None  # Se genera automáticamente por trigger si es None
    business_id: UUID
    deal_id: Optional[UUID] = None
    user_id: UUID
    proposal_date: Optional[date] = None
    total_amount: Optional[float] = None
    currency: str = "USD"
    pdf_s3_key: Optional[str] = None
    proposal_data: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@uuid_string_properties("user_id", "task_id")
class WebSocketConnectionTask(BaseIgnoreExtraModel):
    connection_id: str  # ID de la conexión WebSocket
    user_id: UUID
    task_id: Optional[UUID]
    user_color: Optional[str]  # Color del usuario en el editor
    cursor_position: Optional[Dict[str, Any]]  # {line: 3, col: 15}
    selection_range: Optional[Dict[str, Any]]  # {from: 20, to: 30}


@uuid_string_properties("id", "business_id")
class ExperianReport(BaseIgnoreExtraModel):
    id: Optional[UUID] = None          # lo genera la DB (DEFAULT)
    business_id: UUID
    id:UUID
    data: Dict[str, Any]  #  (antes: dic)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


#rating evaluation
class EvaluationMode:
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    HYBRID = "HYBRID"


class EvaluationStatus:
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EvaluationRuleStatus:
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class EvaluationSubRuleStatus:
    PENDING = "PENDING"
    EVALUATED = "EVALUATED"
    SKIPPED = "SKIPPED"


class EvaluationType:
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"


class InputSource:
    ACCOUNT_VALUE = "ACCOUNT_VALUE"
    OUTPUT_VALUE = "OUTPUT_VALUE"
    MANUAL_INPUT = "MANUAL_INPUT"


# ──────────────────────────────────────────────────────────────────────────────
# Model: RatingEvaluation
# ──────────────────────────────────────────────────────────────────────────────

@uuid_string_properties(
    "id",
    "evaluator_id",
    "business_id",
    "rating_methodology_id",
    "final_rating_category_id",
    "approved_by",
    "created_by"
)
class RatingEvaluation(BaseIgnoreExtraModel):
    """Modelo principal de evaluación de calificación."""

    id: UUID
    evaluator_id: UUID
    business_id: UUID
    rating_methodology_id: UUID

    # Información de la evaluación
    name: Optional[str] = None
    evaluation_date: date
    period_start: Optional[date] = None
    period_end: Optional[date] = None

    # Configuración
    evaluation_mode: str = EvaluationMode.HYBRID

    # Estado y progreso
    status: str = EvaluationStatus.DRAFT
    progress_percentage: Optional[Decimal] = Decimal("0.00")

    # Resultado final
    final_score: Optional[Decimal] = None
    final_rating_category_id: Optional[UUID] = None

    # Metadata
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None

    # Auditoría
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None


# ──────────────────────────────────────────────────────────────────────────────
# Model: RatingEvaluationRule
# ──────────────────────────────────────────────────────────────────────────────

@uuid_string_properties(
    "id",
    "rating_evaluation_id",
    "rule_id",
    "rating_category_id"
)
class RatingEvaluationRule(BaseIgnoreExtraModel):
    """Resultado de evaluación por regla."""

    id: UUID
    rating_evaluation_id: UUID
    rule_id: UUID

    # Estado
    status: str = EvaluationRuleStatus.PENDING
    progress_percentage: Optional[Decimal] = Decimal("0.00")

    # Peso aplicado (snapshot)
    applied_weight: Decimal

    # Resultado
    weighted_score: Optional[Decimal] = None
    rating_category_id: Optional[UUID] = None

    # Metadata
    notes: Optional[str] = None

    # Auditoría
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ──────────────────────────────────────────────────────────────────────────────
# Model: RatingEvaluationSubRule
# ──────────────────────────────────────────────────────────────────────────────

@uuid_string_properties(
    "id",
    "rating_evaluation_rule_id",
    "sub_rule_id",
    "source_reference_id",
    "matched_condition_id",
    "rating_category_id",
    "evaluated_by"
)
class RatingEvaluationSubRule(BaseIgnoreExtraModel):
    """Resultado de evaluación por sub-regla."""

    id: UUID
    rating_evaluation_rule_id: UUID
    sub_rule_id: UUID

    # Tipo de evaluación
    evaluation_type: str  # AUTOMATIC o MANUAL

    # Estado
    status: str = EvaluationSubRuleStatus.PENDING

    # Peso aplicado (snapshot)
    applied_weight: Decimal

    # Datos de entrada (para AUTOMATIC o MANUAL con valor)
    input_value: Optional[Decimal] = None
    input_source: Optional[str] = None  # ACCOUNT_VALUE, OUTPUT_VALUE, MANUAL_INPUT
    source_reference_id: Optional[UUID] = None
    source_reference_date: Optional[date] = None

    # Resultado
    matched_condition_id: Optional[UUID] = None
    rating_category_id: Optional[UUID] = None
    weighted_score: Optional[Decimal] = None

    # Justificación / Trazabilidad
    justification: Optional[str] = None
    evaluation_details: Optional[dict] = None  # JSONB

    # Evaluador
    evaluated_by: Optional[UUID] = None
    evaluated_at: Optional[datetime] = None

    # Auditoría
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None




class DealFileCategory(str, Enum):
    FINANCIAL_DATA = "FINANCIAL_DATA"
    COMPANY_DATA = "COMPANY_DATA"
    MARKET_DATA = "MARKET_DATA"
    GUARANTEES = "GUARANTEES"
    OTHER = "OTHER"


# ============================================
# MODELO - DealFile
# ============================================

@uuid_string_properties("id", "deal_id", "uploaded_by")
class DealFile(BaseIgnoreExtraModel):
    id: UUID
    deal_id: UUID
    s3_key: str
    original_name: str
    category: str
    file_type: str
    file_size: Optional[int]
    uploaded_by: Optional[UUID]
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "business_id")
class BusinessContext(BaseIgnoreExtraModel):
    id: UUID
    business_id: UUID
    context_name: str
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "user_id", "business_id")
class Conversation(BaseIgnoreExtraModel):
    id: UUID
    user_id: UUID
    business_id: UUID
    title: Optional[str]
    summary_context: Optional[str]
    agent_config: Optional[Dict]
    message_count: Optional[int]
    total_tokens_used: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@uuid_string_properties("id", "conversation_id")
class ConversationMessage(BaseIgnoreExtraModel):
    id: UUID
    conversation_id: UUID
    request_content: str
    response_content: Optional[str] = None
    status: Optional[str] = "PENDING"
    ai_process: Optional[Dict]
    facts: Optional[str] = None   # Hechos extraídos del turno (Phase 2 — memoria entre turns)
    created_at: Optional[datetime]
    updated_at: Optional[datetime]




# =============
# GUARANTEE
# =============

# ENUMS / LITERALS
GuaranteeType = Literal[
    'INMUEBLE',  # Inmueble / Real Estate
    'PRENDA',  # Prenda / Pledge
    'FIANZA',  # Fianza / Surety
    'DEPOSITO',  # Depósito / Cash Deposit
    'ACCIONES',  # Acciones / Stocks
    'VEHICULO',  # Vehículo
    'MAQUINARIA',  # Maquinaria y Equipo
    'INVENTARIO',  # Inventario
    'CUENTAS_COBRAR',  # Cuentas por cobrar
    'OTRA'  # Otra
]

GuaranteeStatus = Literal[
    'ACTIVE',
    'RELEASED',
    'EXPIRED',
    'PENDING_APPRAISAL'
]

GuaranteeDocumentType = Literal[
    'APPRAISAL',  # Tasación
    'CONTRACT',  # Contrato de garantía
    'REGISTRATION',  # Inscripción registral
    'INSURANCE',  # Póliza de seguro
    'PHOTO',  # Fotografías
    'LEGAL_OPINION',  # Opinión legal
    'OTHER'  # Otro
]

@uuid_string_properties(
    "id",
    "evaluator_id",
    "deal_id",
    "loan_id",
    "business_id",
    "created_by"
)
class Guarantee(BaseIgnoreExtraModel):
    """
    Garantía asociada a un Deal o Loan.

    El valor ajustado se calcula como: appraisal_value * (1 - haircut_percentage/100)
    """
    id: UUID

    # Relación flexible: puede estar vinculada a Deal, Loan, o ambos
    deal_id: UUID
    loan_id: Optional[UUID] = None

    # Información de la garantía
    guarantee_type: GuaranteeType
    description: str

    # Valores financieros
    appraisal_value: Decimal = Decimal('0')  # Valor de tasación
    haircut_percentage: Decimal = Decimal('0')  # % de descuento (0-100)
    adjusted_value: Decimal = Decimal('0')  # Valor ajustado (calculado)
    currency: str = "PEN"

    # Fechas de tasación
    appraisal_date: Optional[date] = None
    expiration_date: Optional[date] = None  # Cuándo vence la tasación

    # Estado
    status: GuaranteeStatus = 'ACTIVE'

    # Metadata adicional (ubicación, datos registrales, etc.)
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    # Auditoría
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# DOCUMENTOS DE GARANTÍA
# ============================================================================

@uuid_string_properties("id", "guarantee_id", "uploaded_by")
class GuaranteeDocument(BaseIgnoreExtraModel):
    """Documentos adjuntos a una garantía (tasaciones, contratos, fotos)."""

    id: UUID
    guarantee_id: UUID

    document_type: GuaranteeDocumentType
    file_name: str#nombe originl
    s3_key: str  # S3 URL o similar#clave del documento en s3
    file_size: Optional[int] = None  # bytes
    file_type: Optional[str] = None

    # Auditoría
    uploaded_by: Optional[UUID] = None
    created_at: Optional[datetime] = None

# ============================================================================
# HISTORIAL DE CAMBIOS EN GARANTÍAS
# ============================================================================

@uuid_string_properties("id", "guarantee_id", "changed_by")
class GuaranteeHistory(BaseIgnoreExtraModel):
    """Log de cambios en garantías para auditoría y tracking."""
    id: UUID
    guarantee_id: UUID

    change_type: Literal['CREATED', 'UPDATED', 'VALUE_CHANGED', 'STATUS_CHANGED', 'RELEASED']
    previous_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None

    change_reason: Optional[str] = None
    changed_by: Optional[UUID] = None
    created_at: Optional[datetime] = None

class GuaranteeDocumentHistory(BaseIgnoreExtraModel):
    id: UUID
    guarantee_history_id: UUID
    previous_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None



###
# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────

@uuid_string_properties("id", "business_id", "created_by")
class ProjectionScenario(BaseIgnoreExtraModel):
    id: UUID
    business_id: UUID
    name: str
    type: Literal["BASE", "DOWNSIDE", "STRESS", "CUSTOM", "AI_GENERATED"] = "BASE"
    is_active: bool = True
    base_year: int
    projection_years: int = 5
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION DRIVERS (catálogo)
# ─────────────────────────────────────────────────────────────────────────────

@uuid_string_properties("id")
class ProjectionDriver(BaseIgnoreExtraModel):
    id: UUID
    name: str                   # clave única snake_case, ej: revenue_growth_pct
    display_name: str           # nombre legible para UI
    category: Literal[
        "REVENUE", "COSTS", "WORKING_CAPITAL", "CAPEX", "DEBT", "NEW_DEBT"
    ]
    format: Literal[
        "percentage", "days", "currency", "years", "toggle"
    ] = "percentage"
    script: Optional[str] = None        # script para calcular default desde históricos
    default_value: Optional[Decimal] = None
    min_allowed: Optional[Decimal] = None
    max_allowed: Optional[Decimal] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION DRIVER VALUES
# ─────────────────────────────────────────────────────────────────────────────

@uuid_string_properties("id", "scenario_id", "driver_id")
class ProjectionDriverValue(BaseIgnoreExtraModel):
    id: UUID
    scenario_id: UUID
    driver_id: UUID
    year: int               # año relativo: 1 a projection_years
    value: Decimal
    is_default: bool = True # True = calculado por sistema, False = modificado por analista
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION ACCOUNTS (catálogo)
# ─────────────────────────────────────────────────────────────────────────────

@uuid_string_properties("id")
class ProjectionAccount(BaseIgnoreExtraModel):
    id: UUID
    name: str               # clave única UPPER_SNAKE_CASE, ej: SALES, EBITDA
    display_name: str
    statement: Literal["PL", "BS", "CF"]
    sign: Literal["positive", "negative", "calculated", "variable"] = "positive"
    tags: List[str] = []    # clasificación jerárquica, ej: ["pl", "revenue", "gm"]
    script: Optional[str] = None             # fórmula del mini-compilador (AccountScriptEngine)
    historical_script: Optional[str] = None  # fórmula para extraer valor histórico (DriverScriptEngine DSL)
    calculation_order: int          # orden de ejecución del motor
    sort_order: int = 0             # orden de presentación en UI
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION ACCOUNT VALUES
# ─────────────────────────────────────────────────────────────────────────────

@uuid_string_properties("id", "scenario_id", "projection_account_id")
class ProjectionAccountValue(BaseIgnoreExtraModel):
    id: UUID
    scenario_id: UUID
    projection_account_id: UUID
    year: int               # relativo: -2,-1,0=histórico, 1-5=proyectado
    value: Decimal          # negativo para costos/deuda según signo de la cuenta
    is_historical: bool = False  # True para year <= 0
    details: Optional[Dict[str, Any]] = None  # desglose del cálculo para auditoría
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION CHECKS (catálogo global)
# ─────────────────────────────────────────────────────────────────────────────

@uuid_string_properties("id")
class ProjectionCheck(BaseIgnoreExtraModel):
    id: UUID
    name: str               # clave única snake_case, ej: balance_check
    display_name: str       # nombre legible para UI
    category: Literal["BS", "CF", "PL", "CUSTOM"]
    description: Optional[str] = None
    script: str             # expresión Python evaluada por CheckScriptEngine
    tolerance: Decimal = Decimal("0.01")   # abs(difference) <= tolerance → passed
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION CHECK VALUES
# ─────────────────────────────────────────────────────────────────────────────

@uuid_string_properties("id", "scenario_id", "check_id")
class ProjectionCheckValue(BaseIgnoreExtraModel):
    id: UUID
    scenario_id: UUID
    check_id: UUID
    year: int               # relativo: ≤0 = histórico, ≥1 = proyectado
    difference: Decimal     # resultado del script (idealmente ≈ 0)
    passed: bool            # abs(difference) <= tolerance
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None



# ─── AgentPendingConfirmation ─────────────────────────────────────────────────
# Representa el estado suspendido de un agente esperando respuesta del usuario.
#
# SQL — tabla + índice de performance (ejecutar una vez):
#
#   CREATE TABLE agent_pending_confirmations (
#       id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
#       message_id          UUID NOT NULL REFERENCES conversation_messages(id),
#       conversation_id     UUID NOT NULL REFERENCES conversations(id),
#       agent_name          VARCHAR(100) NOT NULL,
#       question            TEXT NOT NULL,
#       options             JSONB,
#       agent_state         JSONB NOT NULL,
#       resolved            BOOLEAN DEFAULT FALSE,
#       user_response       TEXT,
#       responded_at        TIMESTAMPTZ,
#       expires_at          TIMESTAMPTZ,
#       created_at          TIMESTAMPTZ DEFAULT NOW()
#   );
#
#   -- Índice para find_one_by_attributes({message_id, conversation_id, resolved: False})
#   CREATE INDEX idx_apc_message_resolved
#       ON agent_pending_confirmations (message_id, conversation_id, resolved);
#
# SQL — migración columna facts en conversation_messages (Phase 2):
#
#   ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS facts TEXT;
#   -- facts almacena los hechos extraídos del turno (bullet points) para
#   -- inyectarlos en el system prompt del siguiente turno como memoria persistente.


@uuid_string_properties("id", "message_id", "conversation_id")
class AgentPendingConfirmation(BaseModel):
    id: UUID
    message_id: UUID
    conversation_id: UUID
    agent_name: str
    question: str
    options: Optional[List[str]] = None
    agent_state: Dict[str, Any]          # Estado completo: messages, tool_use_id, etc.
    resolved: bool = False
    user_response: Optional[str] = None
    responded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @field_validator("options", mode="before")
    @classmethod
    def parse_options(cls, v):
        """Acepta tanto List[str] como JSON string (cuando viene de columna JSONB como texto)."""
        if isinstance(v, str):
            import json as _json
            try:
                parsed = _json.loads(v)
                return parsed if isinstance(parsed, list) else None
            except (ValueError, TypeError):
                return None
        return v


# ─── Context Engineering V3 ───────────────────────────────────────────────────

@uuid_string_properties("id", "conversation_id", "business_id")
class AgentContext(BaseIgnoreExtraModel):
    """
    Contexto estructurado del agente — una fila por conversación.
    Reemplaza facts TEXT como fuente primaria de memoria del agente.
    """
    id: UUID
    conversation_id: UUID
    business_id: UUID
    content: Dict[str, Any]          # JSONB: analyzed_data, conclusions, executed_actions, user_decisions, pending
    content_archive: Dict[str, Any]  # JSONB: entradas antiguas archivadas
    token_estimate: int = 0
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "conversation_id", "message_id")
class AgentTurnTrace(BaseIgnoreExtraModel):
    """
    Traza por turno del agente — flight recorder para debugging y métricas.
    """
    turn_id: UUID
    conversation_id: UUID
    message_id: Optional[UUID] = None
    agent_name: str
    turn_number: int = 0

    # Token metrics
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    # Tool call metrics
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_guard_stats: Optional[Dict[str, Any]] = None

    # Loop metrics
    iterations: int = 0
    loop_guard_triggered: bool = False

    # Context metrics
    compression_triggered: bool = False
    context_tokens_start: Optional[int] = None
    context_tokens_end: Optional[int] = None

    # Guardrails (Fase 4)
    input_screening_result: Optional[str] = None  # "low" | "medium" | "high" | None

    # Status
    duration_ms: Optional[int] = None
    status: str = "COMPLETED"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

class AiAuditLog(BaseIgnoreExtraModel):
    """
    Registro de auditoría inmutable por turno — compliance financiero (ECOA/Reg B, FCRA).
    Solo INSERT; UPDATE y DELETE revocados a nivel DB.
    """
    id: Optional[int] = None
    trace_id: UUID
    turn_id: Optional[UUID] = None                 # FK → agent_turn_traces.turn_id
    conversation_id: Optional[UUID] = None
    agent_name: str
    model_version: str
    action: str

    # Hashes (SHA-256) — no PII en cleartext
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None

    # Datos estructurados sin PII
    tool_calls: Optional[List[Dict[str, Any]]] = None
    decision_factors: Optional[Dict[str, Any]] = None
    guardrail_flags: Optional[Dict[str, Any]] = None
    tokens_used: Optional[Dict[str, Any]] = None

    # Encadenamiento para inmutabilidad verificable
    prev_record_hash: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# SUMMARIES
# ──────────────────────────────────────────────────────────────────────────────

@uuid_string_properties("id", "evaluator_id")
class SummaryDefinition(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: UUID
    code: str
    label: str
    prompt: str
    output_names: List[str] = []
    account_names: List[str] = []
    account_types: List[str] = []
    is_active: bool = True
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "business_id")
class SummaryResult(BaseIgnoreExtraModel):
    id: UUID
    business_id: UUID
    status: str
    generated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "summary_result_id", "definition_id")
class SummaryBullet(BaseIgnoreExtraModel):
    id: UUID
    summary_result_id: UUID
    definition_id: UUID
    content: Optional[str] = None
    ratios_snapshot: Optional[Dict[str, Any]] = None
    status: str
    error_detail: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# RELATION 360 — Vista Fase 1 CRM
# =============================================================================

@uuid_string_properties("id", "business_id", "evaluator_id", "deal_id", "loan_id")
class CreditProduct(BaseIgnoreExtraModel):
    id: UUID
    business_id: UUID
    evaluator_id: UUID
    deal_id: Optional[UUID] = None
    loan_id: Optional[UUID] = None
    product_type: str
    approved_limit: Decimal = Decimal("0")
    drawn_amount: Decimal = Decimal("0")
    currency: str = "PEN"
    maturity_date: Optional[date] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "evaluator_id")
class EconomicGroup(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: UUID
    name: str
    group_credit_limit: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "group_id", "business_id")
class EconomicGroupMember(BaseIgnoreExtraModel):
    id: UUID
    group_id: UUID
    business_id: UUID
    relation_type: str
    ownership_pct: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@uuid_string_properties("id", "evaluator_id", "business_id", "deal_id", "user_id")
class CompanyActivityLog(BaseIgnoreExtraModel):
    id: UUID
    evaluator_id: UUID
    business_id: UUID
    deal_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    activity_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    occurred_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@uuid_string_properties("rating_category_id",)
class RatingCategoryRiskMetric(BaseIgnoreExtraModel):
    rating_category_id: UUID
    estimated_pd: Optional[Decimal] = None
    estimated_lgd: Optional[Decimal] = None
    updated_at: Optional[datetime] = None




import os
from services.service_outputs.src.services.output import OutputService
from services.service_outputs.src.services.derived_cashflow import DerivedCashflowService
from services.service_outputs.src.repositories.financial_datapoints import FinancialDatapointRepository
from services.service_outputs.src.repositories.financial_statement import FinancialStatementRepository
from services.service_outputs.src.repositories.output import OutputRepository
from services.service_outputs.src.repositories.calculated_output import CalculatedOutputRepository
from services.service_outputs.src.repositories.derived_cashflow import DerivedCashflowRepository
from services.service_outputs.src.repositories.calculated_derived_cashflow import CalculatedDerivedCashflowRepository
from services.service_outputs.src.repositories.business import BusinessRepository
from services.service_outputs.src.repositories.financial_statement_config import FinancialStatementConfigRepository
from services.service_outputs.src.utils.calculator_v3 import DSLCalculator
from common_aws_clients.sqs_client import SQSClient
from common_eventbridge.eventbridge_client import EventBridgeClient

SQS_URL_PROCESS_ALERTS          = os.environ["SQS_URL_PROCESS_ALERTS"]
EVENTBRIDGE_WORKFLOWS_BUS_NAME  = os.environ["EVENTBRIDGE_WORKFLOWS_BUS_NAME"]


def get_output_service() -> OutputService:
    return OutputService(
        financial_statement_repository=FinancialStatementRepository(),
        financial_datapoint_repository=FinancialDatapointRepository(),
        output_repository=OutputRepository(),
        calculated_output_repository=CalculatedOutputRepository(),
        calculator=DSLCalculator(),
        sqs_client=SQSClient(queue_url=SQS_URL_PROCESS_ALERTS),
        eventbridge_client=EventBridgeClient(event_bus_name=EVENTBRIDGE_WORKFLOWS_BUS_NAME),
        business_repository=BusinessRepository(),
        fs_config_repository=FinancialStatementConfigRepository(),
    )


def get_derived_cashflow_service() -> DerivedCashflowService:
    return DerivedCashflowService(
        financial_statement_repository=FinancialStatementRepository(),
        financial_datapoint_repository=FinancialDatapointRepository(),
        derived_cashflow_repository=DerivedCashflowRepository(),
        calculated_derived_cashflow_repository=CalculatedDerivedCashflowRepository(),
        calculator=DSLCalculator(),
    )

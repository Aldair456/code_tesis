import logging
from typing import List, Dict, Any, Optional, Tuple

from common.exceptions.exceptions import ServiceError, NotFoundError
from services.service_outputs.src.repositories.derived_cashflow import DerivedCashflowRepository
from services.service_outputs.src.repositories.calculated_derived_cashflow import CalculatedDerivedCashflowRepository
from services.service_outputs.src.repositories.financial_statement import FinancialStatementRepository
from services.service_outputs.src.repositories.financial_datapoints import FinancialDatapointRepository
from services.service_outputs.src.utils.calculator_v3 import DSLCalculator
from services.service_outputs.src.utils.datapoint_helpers import (
    fetch_all_datapoints,
    group_datapoints_by_year,
    group_datapoints_by_period,
    get_ltm_composition,
    get_monthly_annualized_composition,
    count_months_in_composition,
    find_latest_composition_period,
    build_ltm_structure,
    build_monthly_annualized_structure,
)

logger = logging.getLogger(__name__)

UPSERT_CONSTRAINT = ["derived_cashflow_id", "financial_statement_id", "period_type", "period_identifier"]


class DerivedCashflowService:
    def __init__(self,
                 financial_statement_repository: FinancialStatementRepository,
                 financial_datapoint_repository: FinancialDatapointRepository,
                 derived_cashflow_repository: DerivedCashflowRepository,
                 calculated_derived_cashflow_repository: CalculatedDerivedCashflowRepository,
                 calculator: DSLCalculator):
        self.financial_statement_repository = financial_statement_repository
        self.financial_datapoint_repository = financial_datapoint_repository
        self.derived_cashflow_repository = derived_cashflow_repository
        self.calculated_derived_cashflow_repository = calculated_derived_cashflow_repository
        self.calculator = calculator

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers: delegated to datapoint_helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _fetch_all_datapoints(self, statement_id: str):
        return fetch_all_datapoints(self.financial_datapoint_repository, statement_id)

    def _datapoints_by_year(self, statement_id: str) -> Tuple[Dict, List]:
        """Agrupa datapoints por año (para cálculo anual)."""
        all_datapoints = self._fetch_all_datapoints(statement_id)
        if not all_datapoints:
            return {}, []
        datapoints_by_year, years = group_datapoints_by_year(all_datapoints)
        logger.info(f"Grouped datapoints into {len(years)} years for statement {statement_id}")
        return datapoints_by_year, years

    def _datapoints_by_period(self, statement_id: str) -> Dict[str, List]:
        """Agrupa datapoints por período (año + trimestres/meses) para LTM y MA."""
        all_datapoints = self._fetch_all_datapoints(statement_id)
        if not all_datapoints:
            return {}
        return group_datapoints_by_period(all_datapoints)

    def _get_ltm(self, statement_id: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
        return get_ltm_composition(self.financial_statement_repository, statement_id)

    def _get_monthly_annualized(self, statement_id: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
        return get_monthly_annualized_composition(self.financial_statement_repository, statement_id)

    def _count_months_in_composition(self, ma_composition: List[Dict]) -> int:
        return count_months_in_composition(ma_composition)

    def _find_latest_composition_period(self, ma_composition: List[Dict]) -> Optional[str]:
        return find_latest_composition_period(ma_composition)

    def _build_ltm_structure(self, ltm_composition, datapoints_by_period, ltm_title) -> Dict[str, List]:
        return build_ltm_structure(ltm_composition, datapoints_by_period, ltm_title)

    def _build_monthly_annualized_structure(self, ma_composition, datapoints_by_period,
                                            ma_title, factor) -> Dict[str, List]:
        return build_monthly_annualized_structure(ma_composition, datapoints_by_period, ma_title, factor)

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers: definiciones del evaluador
    # ──────────────────────────────────────────────────────────────────────────

    def _fetch_definitions(self, evaluator_id: str):
        definitions = self.derived_cashflow_repository.find_by_evaluator(evaluator_id)
        if not definitions:
            raise ServiceError(f"No hay derived_cashflows definidos para evaluator {evaluator_id}")
        return definitions

    def _run_calculations(self, definitions, current_period, datapoints_period,
                          statement_id, period_type, period_identifier) -> List[Dict]:
        records = []
        for defn in definitions:
            if not defn.script or not defn.script.strip():
                continue
            try:
                value = self.calculator.calculate(
                    expression=defn.script,
                    current_period=current_period,
                    datapoints_period=datapoints_period
                )
            except Exception as e:
                logger.error(f"Error calculando {defn.name} en {current_period}: {e}")
                value = None
            records.append({
                "derived_cashflow_id": defn.id,
                "financial_statement_id": statement_id,
                "value": value,
                "year": None if period_type != "annual" else current_period,
                "period_type": period_type,
                "period_identifier": period_identifier,
            })
        return records

    def _upsert(self, records: List[Dict]) -> int:
        with self.calculated_derived_cashflow_repository.transaction() as tx:
            return tx.upsert_many(records, UPSERT_CONSTRAINT)

    # ──────────────────────────────────────────────────────────────────────────
    # Cálculo — Anual
    # ──────────────────────────────────────────────────────────────────────────

    def calculate_derived_cashflows(self, statement_id: str, evaluator_id: str) -> bool:
        """Calcula derived cashflows anuales para el statement dado."""
        if not statement_id or not evaluator_id:
            raise ServiceError("statement_id y evaluator_id son requeridos")

        logger.info(f"Cálculo anual: statement={statement_id}, evaluator={evaluator_id}")

        datapoints_by_year, years = self._datapoints_by_year(statement_id)
        if not years:
            raise ServiceError(f"Sin datapoints anuales para statement {statement_id}")

        definitions = self._fetch_definitions(evaluator_id)
        logger.info(f"Calculando {len(years)} años × {len(definitions)} definiciones")

        records = []
        for year in years:
            if not datapoints_by_year.get(year):
                continue
            records.extend(self._run_calculations(
                definitions=definitions,
                current_period=year,
                datapoints_period=datapoints_by_year,
                statement_id=statement_id,
                period_type="annual",
                period_identifier=str(year)
            ))

        if not records:
            raise ServiceError(f"No se generaron registros anuales para statement {statement_id}")

        count = self._upsert(records)
        logger.info(f"Upserted {count} calculated_derived_cashflows anuales para {statement_id}")
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # Cálculo — LTM
    # ──────────────────────────────────────────────────────────────────────────

    def calculate_derived_cashflows_ltm(self, statement_id: str, evaluator_id: str) -> bool:
        """Calcula derived cashflows LTM para el statement dado."""
        if not statement_id or not evaluator_id:
            raise ServiceError("statement_id y evaluator_id son requeridos")

        logger.info(f"Cálculo LTM: statement={statement_id}, evaluator={evaluator_id}")

        ltm_composition, ltm_title = self._get_ltm(statement_id)
        if not ltm_composition:
            logger.warning(f"Sin ltm_composition para statement {statement_id}, se omite LTM")
            return False

        datapoints_by_period = self._datapoints_by_period(statement_id)
        if not datapoints_by_period:
            logger.warning(f"Sin datapoints por período para statement {statement_id}")
            return False

        ltm_structure = self._build_ltm_structure(ltm_composition, datapoints_by_period, ltm_title)
        if not ltm_structure:
            logger.warning("Estructura LTM vacía, se omite")
            return False

        definitions = self._fetch_definitions(evaluator_id)
        ltm_period_identifier = f"LTM_{ltm_title}"

        records = self._run_calculations(
            definitions=definitions,
            current_period=ltm_period_identifier,
            datapoints_period=ltm_structure,
            statement_id=statement_id,
            period_type="ltm",
            period_identifier=ltm_period_identifier
        )

        if not records:
            logger.warning(f"No se generaron registros LTM para statement {statement_id}")
            return False

        count = self._upsert(records)
        logger.info(f"Upserted {count} calculated_derived_cashflows LTM para {statement_id}")
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # Cálculo — Monthly Annualized
    # ──────────────────────────────────────────────────────────────────────────

    def calculate_derived_cashflows_monthly_annualized(self, statement_id: str, evaluator_id: str) -> bool:
        """Calcula derived cashflows mensuales anualizados para el statement dado."""
        if not statement_id or not evaluator_id:
            raise ServiceError("statement_id y evaluator_id son requeridos")

        logger.info(f"Cálculo monthly annualized: statement={statement_id}, evaluator={evaluator_id}")

        ma_composition, ma_title = self._get_monthly_annualized(statement_id)
        if not ma_composition:
            logger.info(
                f"Sin tramo parcial para anualizar en statement {statement_id}; "
                "se omite derived cashflows MA"
            )
            return False

        n_months = self._count_months_in_composition(ma_composition)
        factor = 12.0 / n_months if n_months > 0 else 1.0
        logger.info(f"Factor anualización: 12/{n_months} = {factor:.4f}")

        datapoints_by_period = self._datapoints_by_period(statement_id)
        if not datapoints_by_period:
            logger.warning(f"Sin datapoints por período para statement {statement_id}")
            return False

        ma_structure = self._build_monthly_annualized_structure(
            ma_composition, datapoints_by_period, ma_title, factor
        )
        if not ma_structure:
            logger.warning("Estructura MA vacía, se omite")
            return False

        definitions = self._fetch_definitions(evaluator_id)
        ma_period_identifier = f"MA_{ma_title}"

        records = self._run_calculations(
            definitions=definitions,
            current_period=ma_period_identifier,
            datapoints_period=ma_structure,
            statement_id=statement_id,
            period_type="monthly_annualized",
            period_identifier=ma_period_identifier
        )

        if not records:
            logger.warning(f"No se generaron registros MA para statement {statement_id}")
            return False

        count = self._upsert(records)
        logger.info(f"Upserted {count} calculated_derived_cashflows MA para {statement_id}")
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # Recálculo manual
    # ──────────────────────────────────────────────────────────────────────────

    def recalculate_all(self, business_id: str, evaluator_id: str) -> Dict[str, Any]:
        """
        Recalcula todos los derived cashflows (annual + LTM + MA) para un business.
        Busca el financial statement OFFICIAL y ejecuta los 3 tipos de cálculo.
        """
        if not business_id or not evaluator_id:
            raise ServiceError("business_id y evaluator_id son requeridos")

        statement = self.financial_statement_repository.find_one_by_attributes(
            filters={"business_id": business_id, "type": "OFFICIAL"}
        )
        if not statement:
            raise NotFoundError(f"No existe financial statement OFFICIAL para business {business_id}")

        statement_id = str(statement.id)
        results = {}

        # Annual
        try:
            results["annual"] = {"success": self.calculate_derived_cashflows(
                statement_id=statement_id, evaluator_id=evaluator_id
            )}
        except Exception as e:
            logger.error(f"Error en cálculo anual derived cashflows: {e}")
            results["annual"] = {"success": False, "error": str(e)}

        # LTM
        try:
            results["ltm"] = {"success": self.calculate_derived_cashflows_ltm(
                statement_id=statement_id, evaluator_id=evaluator_id
            )}
        except Exception as e:
            logger.warning(f"Error en cálculo LTM derived cashflows: {e}")
            results["ltm"] = {"success": False, "error": str(e)}

        # Monthly Annualized
        try:
            results["monthly_annualized"] = {"success": self.calculate_derived_cashflows_monthly_annualized(
                statement_id=statement_id, evaluator_id=evaluator_id
            )}
        except Exception as e:
            logger.warning(f"Error en cálculo MA derived cashflows: {e}")
            results["monthly_annualized"] = {"success": False, "error": str(e)}

        return {"statement_id": statement_id, "results": results}

    # ──────────────────────────────────────────────────────────────────────────
    # Consultas
    # ──────────────────────────────────────────────────────────────────────────

    def get_definitions(self, evaluator_id: str):
        if not evaluator_id:
            raise ServiceError("evaluator_id es requerido")
        return self.derived_cashflow_repository.find_by_evaluator(evaluator_id)

    def get_calculated(self,
                       user: dict,
                       business_id: str,
                       evaluator_id: str,
                       categories: Optional[List[str]] = None,
                       names: Optional[List[str]] = None,
                       period_types: Optional[List[str]] = None,
                       period_identifiers: Optional[List[str]] = None,
                       page: int = 0,
                       size: int = 100) -> List[Dict[str, Any]]:
        if not business_id or not evaluator_id:
            raise ServiceError("business_id y evaluator_id son requeridos")

        statement = self.financial_statement_repository.find_one_by_attributes(
            filters={"business_id": business_id, "type": "OFFICIAL"}
        )
        if not statement:
            raise NotFoundError(f"No existe financial statement OFFICIAL para business {business_id}")

        statement_id = str(statement.id)
        size = max(1, min(size, 1000))
        offset = max(0, page) * size

        results = self.calculated_derived_cashflow_repository.find_with_def_info(
            statement_id=statement_id,
            evaluator_id=evaluator_id,
            categories=categories,
            names=names,
            period_types=period_types,
            period_identifiers=period_identifiers,
            limit=size,
            offset=offset
        )

        logger.info(f"get_calculated: {len(results)} registros para business={business_id}, evaluator={evaluator_id}")
        return [r.model_dump() for r in results]

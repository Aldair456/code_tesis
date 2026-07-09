import logging
from typing import List, Dict, Any, Optional, Tuple

from common.exceptions.exceptions import (
    ServiceError,
    NotFoundError
)

from common_aws_clients.sqs_client import SQSClient
from common_eventbridge.eventbridge_client import EventBridgeClient
from services.service_outputs.src.repositories.financial_statement import FinancialStatementRepository
from services.service_outputs.src.utils.datapoint_helpers import (
    is_pl_datapoint,
    is_bs_datapoint,
    create_negative_datapoints,
    fetch_all_datapoints,
    group_datapoints_by_year,
    group_datapoints_by_period,
    get_ltm_composition,
    get_monthly_annualized_composition,
    resolve_trailing_compositions_from_datapoints,
    count_months_in_composition,
    find_latest_composition_period,
    build_ltm_pl_datapoints,
    build_ltm_structure,
    build_monthly_pl_datapoints,
    build_monthly_annualized_structure,
)

logger = logging.getLogger(__name__)


class OutputService:
    def __init__(self,
                 financial_statement_repository: FinancialStatementRepository,
                 financial_datapoint_repository,
                 output_repository,
                 calculated_output_repository,
                 calculator,
                 sqs_client: SQSClient,
                 eventbridge_client: Optional[EventBridgeClient] = None,
                 business_repository=None,
                 fs_config_repository=None,
                 ):
        self.financial_statement_repository = financial_statement_repository
        self.financial_datapoint_repository = financial_datapoint_repository
        self.output_repository = output_repository
        self.calculated_output_repository = calculated_output_repository
        self.calculator = calculator
        self.sqs_client = sqs_client
        self.eventbridge_client = eventbridge_client
        self.business_repository = business_repository
        self.fs_config_repository = fs_config_repository

    def _fetch_all_datapoints(self,
                              statement_id: str,
                              account_names: Optional[List[str]] = None,
                              account_types: Optional[List[str]] = None,
                              years: Optional[List[int]] = None,
                              periods: Optional[List[str]] = None
                              ):
        """
        Función auxiliar para obtener todos los datapoints con paginación interna
        return devuelve datapoints con modelo pydantic
        """
        return fetch_all_datapoints(
            self.financial_datapoint_repository, statement_id,
            account_names=account_names, account_types=account_types,
            years=years, periods=periods
        )

    def _datapoints_by_year(self, statement_id: str) -> Tuple[Dict[int, List], List[int]]:
        """
        Agrupa datapoints por año y retorna años únicos
        """
        try:
            logger.info(f"Starting datapoints grouping by year for statement_id: {statement_id}")

            all_datapoints = self._fetch_all_datapoints(statement_id=statement_id)

            if not all_datapoints:
                logger.warning(f"No datapoints found for statement_id: {statement_id}")
                return {}, []

            # Pre-filter with OutputService-specific validation
            valid_datapoints = [
                dp for idx, dp in enumerate(all_datapoints)
                if self._validate_datapoint(dp, idx)
            ]

            datapoints_by_year, years = group_datapoints_by_year(valid_datapoints)

            logger.info(f"Datapoints grouped successfully for statement_id {statement_id}: "
                        f"{len(years)} years, {len(all_datapoints)} total datapoints, "
                        f"{len(all_datapoints) - len(valid_datapoints)} invalid datapoints")

            return datapoints_by_year, years

        except Exception as e:
            logger.error(f"Critical error in _datapoints_by_year for statement_id {statement_id}: {str(e)}")
            raise ServiceError(f"Error grouping datapoints by year: {str(e)}")

    def _validate_datapoint(self, datapoint: Any, index: int) -> bool:
        """
        Valida un datapoint individual
        """
        try:
            # Verificar que tenga año
            if not hasattr(datapoint, 'year') or datapoint.year is None:
                logger.debug(f"Datapoint {index}: Missing or null year")
                return False

            # Verificar que el año sea válido
            if not isinstance(datapoint.year, int) or datapoint.year < 1900 or datapoint.year > 2100:
                logger.debug(f"Datapoint {index}: Invalid year {datapoint.year}")
                return False

            # Verificar período si existe
            if hasattr(datapoint, 'period') and datapoint.period is not None:
                if not isinstance(datapoint.period, str):
                    logger.debug(f"Datapoint {index}: Period is not string: {datapoint.period}")
                    return False

            # Verificar que tenga valor
            if not hasattr(datapoint, 'value') or datapoint.value is None:
                logger.debug(f"Datapoint {index}: Missing or null value")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating datapoint {index}: {str(e)}")
            return False

    def _calculate_outputs(self, datapoints_by_year: Dict[int, List], outputs: List[Any],
                           years: List[int], statement_id: str) -> List[Dict]:
        """
        Calcula outputs para todos los años y outputs dados (VERSION ACTUALIZADA)
        """
        new_calculated_datapoints = []
        total_calculations = len(years) * len(outputs)
        successful_calculations = 0
        failed_calculations = 0

        logger.info(f"Starting calculations for statement_id {statement_id}: "
                    f"{len(years)} years × {len(outputs)} outputs = {total_calculations} total calculations")

        for year_idx, year in enumerate(years):
            logger.debug(f"Processing year {year} ({year_idx + 1}/{len(years)})")

            # Verificar que existan datapoints para este año
            year_datapoints = datapoints_by_year.get(year, [])
            if not year_datapoints:
                logger.warning(f"No datapoints found for year {year}, skipping calculations")
                failed_calculations += len(outputs)
                continue

            for output_idx, output in enumerate(outputs):
                calculation_id = f"year_{year}_output_{output.id}"

                try:
                    # Validar output
                    if not self._validate_output(output, output_idx):
                        logger.error(f"Invalid output {output_idx} (id: {getattr(output, 'id', 'unknown')})")
                        failed_calculations += 1
                        continue

                    script = output.script
                    output_id = output.id
                    result = None

                    logger.debug(f"Calculating {calculation_id}: script='{script}'")

                    # Ejecutar cálculo
                    result = self.calculator.calculate(
                        expression=script,
                        current_period=year,  # Cambio: current_year -> current_period
                        datapoints_period=datapoints_by_year  # Cambio: datapoints_year -> datapoints_period
                    )

                    # Validar resultado
                    if result is not None:
                        logger.debug(f"Calculation {calculation_id} successful: result={result}")
                        successful_calculations += 1
                    else:
                        logger.warning(f"Calculation {calculation_id} returned None")
                        failed_calculations += 1

                    # Crear registro de resultado con campos nuevos
                    new_calculated_result = {
                        "output_id": output_id,
                        "financial_statement_id": statement_id,
                        "value": result,
                        "year": year,
                        "period_type": "annual",  # NUEVO: Especificar que es anual
                        "period_identifier": str(year)  # NUEVO: Usar año como identificador
                    }
                    new_calculated_datapoints.append(new_calculated_result)

                except Exception as e:
                    logger.error(f"Error calculating {calculation_id}: {str(e)}")
                    failed_calculations += 1

                    # Crear registro con error (valor None)
                    try:
                        error_result = {
                            "output_id": getattr(output, 'id', None),
                            "financial_statement_id": statement_id,
                            "value": None,
                            "year": year,
                            "period_type": "annual",  # NUEVO
                            "period_identifier": str(year),  # NUEVO
                            "is_covenant_metric": False  # NUEVO
                        }
                        new_calculated_datapoints.append(error_result)
                    except Exception as nested_e:
                        logger.error(f"Error creating error record for {calculation_id}: {str(nested_e)}")

        # Logging de resumen
        logger.info(f"Calculations completed for statement_id {statement_id}: "
                    f"{successful_calculations} successful, {failed_calculations} failed, "
                    f"{len(new_calculated_datapoints)} total records created")

        if failed_calculations > 0:
            logger.warning(f"{failed_calculations} calculations failed for statement_id {statement_id}")

        return new_calculated_datapoints

    def _validate_output(self, output: Any, index: int) -> bool:
        """
        Valida un output individual
        """
        try:
            # Verificar que tenga ID
            if not hasattr(output, 'id') or output.id is None:
                logger.error(f"Output {index}: Missing or null id")
                return False

            # Verificar que tenga script
            if not hasattr(output, 'script') or output.script is None:
                logger.error(f"Output {index} (id: {output.id}): Missing or null script")
                return False

            # Verificar que el script no esté vacío
            if not isinstance(output.script, str) or not output.script.strip():
                logger.error(f"Output {index} (id: {output.id}): Empty or invalid script")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating output {index}: {str(e)}")
            return False

    def _fetch_all_outputs(self, evaluator_id: str = None) -> List[Any]:
        """
        Función auxiliar para obtener todos los outputs.
        Filtra por evaluador si se proporciona evaluator_id.
        """
        try:
            all_outputs = self.output_repository.find_distinct_outputs(evaluator_id=evaluator_id)
            logger.info(f"Retrieved {len(all_outputs)} outputs (evaluator_id={evaluator_id})")
            return all_outputs
        except Exception as e:
            logger.error(f"Error fetching outputs: {str(e)}")
            raise

    def calculate_outputs(self, statement_id: str) -> bool:
        """
        Método principal para calcular todos los outputs de un financial statement (VERSION ACTUALIZADA)
        """
        try:
            logger.info(f"Starting output calculation process for statement_id: {statement_id}")

            if not statement_id:
                raise ServiceError("statement_id is required and cannot be empty")

            # Paso 1: Agrupar datapoints por año
            logger.info(f"Step 1: Grouping datapoints by year for statement_id: {statement_id}")
            datapoints_by_year, years = self._datapoints_by_year(statement_id)

            if not years:
                logger.info(
                    f"No annual periods found for statement_id {statement_id} "
                    "(trimestral/mensual sin buckets YYYY); se omite cálculo anual"
                )
                return False

            if not datapoints_by_year:
                logger.info(f"No datapoints found for statement_id {statement_id}")
                return False

            logger.info(f"Step 1 completed: Found {len(years)} years with datapoints")

            # Paso 2: Obtener todos los outputs (filtrados por evaluador del business)
            logger.info("Step 2: Fetching all outputs")
            statement    = self.financial_statement_repository.find_by_id(statement_id)
            business     = self.business_repository.find_by_id(str(statement.business_id)) if statement else None
            evaluator_id = str(business.evaluator_id) if business else None
            all_outputs = self._fetch_all_outputs(evaluator_id=evaluator_id)

            if not all_outputs:
                raise ServiceError("No outputs found in system. Cannot perform calculations.")

            logger.info(f"Step 2 completed: Found {len(all_outputs)} outputs")

            # Paso 3: Calcular outputs
            logger.info(f"Step 3: Calculating outputs for statement_id: {statement_id}")
            calculated_outputs = self._calculate_outputs(
                datapoints_by_year=datapoints_by_year,
                outputs=all_outputs,
                years=years,
                statement_id=statement_id
            )

            if not calculated_outputs:
                raise ServiceError(f"No calculated outputs generated for statement_id {statement_id}")

            logger.info(f"Step 3 completed: Generated {len(calculated_outputs)} calculated outputs")

            # Paso 4: Guardar resultados con nuevo constraint
            logger.info(f"Step 4: Saving calculated outputs to database")

            try:
                with self.calculated_output_repository.transaction() as tx:
                    count = tx.upsert_many(
                        calculated_outputs,
                        ["output_id", "financial_statement_id", "period_type", "period_identifier"]  # NUEVO CONSTRAINT
                    )

                    logger.info(f"Step 4 completed: Successfully upserted {count} calculated outputs "
                                f"for statement_id: {statement_id}")

            except Exception as e:
                logger.error(f"Database transaction failed for statement_id {statement_id}: {str(e)}")
                raise ServiceError(f"Failed to save calculated outputs: {str(e)}")

            # Resumen final
            logger.info(f"✅ Output calculation process completed successfully for statement_id: {statement_id}")
            logger.info(f"Summary: {len(years)} years, {len(all_outputs)} outputs, "
                        f"{len(calculated_outputs)} calculations, {count} records saved")

            self._send_alerts(str(statement_id))
            self._publish_outputs_calculated(str(statement_id))

            return True

        except ServiceError:
            # Re-raise ServiceError as-is
            raise

        except Exception as e:
            logger.error(f"❌ Critical error in calculate_outputs for statement_id {statement_id}: {str(e)}")
            raise ServiceError(f"Unexpected error during output calculation: {str(e)}")

    # def _fetch_all_calculated_outputs(self,
    #                                   statement_id: str,
    #                                   output_names: Optional[List[str]] = None,
    #                                   output_categories: Optional[List[str]] = None,
    #                                   years: Optional[List[int]] = None
    #                                   ):
    #     """
    #     Función auxiliar para obtener todos los calculated outputs con paginación interna
    #     return devuelve calculated outputs con modelo pydantic
    #     """
    #     batch_size = 1000
    #     offset = 0
    #     all_calculated_outputs = []
    #     batch_count = 0
    #
    #     logger.debug(f"Starting batch retrieval of calculated outputs for statement_id: {statement_id}")
    #
    #     while True:
    #         try:
    #             batch_count += 1
    #
    #             batch = self.calculated_output_repository.find_with_output_info_arrays(
    #                 statement_id=statement_id,
    #                 output_names=output_names,
    #                 output_categories=output_categories,
    #                 years=years,
    #                 limit=batch_size,
    #                 offset=offset
    #             )
    #
    #             if not batch:
    #                 logger.debug(f"No data found in batch {batch_count}. Complete.")
    #                 break
    #
    #             all_calculated_outputs.extend(batch)
    #
    #             if len(batch) < batch_size:
    #                 logger.debug(f"Last batch: {len(batch)} items (< {batch_size})")
    #                 break
    #
    #             if len(all_calculated_outputs) >= 50000:
    #                 logger.warning(f"Safety limit reached: {len(all_calculated_outputs)} items")
    #                 break
    #
    #             offset += batch_size
    #             logger.debug(f"Batch {batch_count}: +{len(batch)} items. Total: {len(all_calculated_outputs)}")
    #
    #         except Exception as e:
    #             logger.error(f"Error in batch {batch_count} for statement_id {statement_id}: {str(e)}")
    #             raise
    #
    #     logger.info(
    #         f"Retrieved ALL calculated outputs: {len(all_calculated_outputs)} items in {batch_count} batch(es) for statement_id: {statement_id}")
    #     return all_calculated_outputs
    #
    # def get_calculated_outputs(self,
    #                            user: dict,
    #                            business_id: str,
    #                            output_names: Optional[List[str]] = None,
    #                            output_categories: Optional[List[str]] = None,
    #                            years: Optional[List[int]] = None,
    #                            page: int = 0,
    #                            size: int = 100,
    #                            required_all: bool = False
    #                            ) -> List[Dict[str, Any]]:
    #     """
    #     Obtiene calculated outputs con información del output asociado
    #
    #     Args:
    #         user: Usuario que realiza la consulta
    #         business_id: ID del business
    #         output_names: Lista de nombres de output a filtrar
    #         output_categories: Lista de categorías de output a filtrar
    #         years: Lista de años
    #         page: Número de página (empezando en 0)
    #         size: Tamaño de página (máximo 1000)
    #         required_all: Si True, obtiene todos los resultados ignorando paginación
    #
    #     Returns:
    #         Lista de calculated outputs como diccionarios
    #     """
    #     user_id = user.get('sub', 'unknown')
    #     logger.info(f"get_calculated_outputs called by user {user_id} for business {business_id}")
    #
    #     if not business_id:
    #         logger.error("business_id is required")
    #         raise ServiceError("business_id is required")
    #
    #     filters = {
    #         "business_id": business_id,
    #         "type": "OFFICIAL"
    #     }
    #
    #     statement_official = self.financial_statement_repository.find_one_by_attributes(filters=filters)
    #
    #     if not statement_official:
    #         logger.error("No se encontro financial statement oficial para business_id {business_id}")
    #         raise NotFoundError("No se encontro financial statement oficial para business_id {business_id}")
    #
    #     statement_id = str(statement_official.id)
    #
    #     size = max(1, min(size, 1000))
    #     page = max(0, page)
    #
    #     filters_applied = []
    #     if output_names:
    #         filters_applied.append(f"output_names({len(output_names)})")
    #     if output_categories:
    #         filters_applied.append(f"output_categories({len(output_categories)})")
    #     if years:
    #         filters_applied.append(f"years({len(years)})")
    #
    #     if filters_applied:
    #         logger.info(f"Applied filters: {', '.join(filters_applied)}")
    #
    #     try:
    #         if required_all:
    #             logger.info("Fetching ALL calculated outputs (ignoring pagination)")
    #             all_calculated_outputs = self._fetch_all_calculated_outputs(
    #                 statement_id, output_names, output_categories, years
    #             )
    #             return [co.model_dump() for co in all_calculated_outputs]
    #         else:
    #             # Paginación normal
    #             offset = page * size
    #             logger.debug(f"Fetching page {page} with size {size} (offset: {offset})")
    #
    #             calculated_outputs = self.calculated_output_repository.find_with_output_info_arrays(
    #                 statement_id=statement_id,
    #                 output_names=output_names,
    #                 output_categories=output_categories,
    #                 years=years,
    #                 limit=size,
    #                 offset=offset
    #             )
    #
    #             logger.info(f"Retrieved {len(calculated_outputs)} calculated outputs for page {page}")
    #             return [co.model_dump() for co in calculated_outputs]
    #
    #     except Exception as e:
    #         logger.error(f"Error fetching calculated outputs: {str(e)}", exc_info=True)
    #         raise ServiceError(f"Error fetching calculated outputs: {str(e)}")
    
    def get_outputs(self, filters: Dict[str, Any] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Obtiene outputs agrupados por categoría con id, name y category
        
        Args:
            filters: Filtros opcionales (ej: category)
            
        Returns:
            Diccionario agrupado por categoría con listas de outputs
        """
        try:
            logger.info("Fetching outputs grouped by category (id, name and category)")
            
            # Extraer filtros
            category     = filters.get('category')     if filters else None
            evaluator_id = filters.get('evaluator_id') if filters else None

            # Obtener outputs usando el repositorio
            outputs = self.output_repository.find_distinct_outputs(category=category, evaluator_id=evaluator_id)
            
            # Agrupar outputs por categoría
            return outputs
            
        except Exception as e:
            logger.error(f"Error getting outputs: {str(e)}", exc_info=True)
            raise ServiceError("Error getting outputs") from e

    def _publish_outputs_calculated(self, statement_id: str) -> None:
        """
        Publica el evento outputs_calculated a EventBridge para disparar
        la generación de summaries. Fallo silencioso: no interrumpe el flujo principal.
        Requiere que eventbridge_client esté inyectado.
        """
        if not self.eventbridge_client:
            return
        try:
            fs = self.financial_statement_repository.find_by_id(statement_id)
            if not fs:
                logger.warning(f"No se encontró financial_statement {statement_id} para publicar evento.")
                return
            self.eventbridge_client.publish_event(
                source="vera.outputs",
                detail_type="outputs_calculated",
                detail={"business_id": str(fs.business_id), "statement_id": statement_id},
            )
            logger.info(f"Evento outputs_calculated publicado para business_id={fs.business_id}")
        except Exception as e:
            logger.error(f"Error publicando outputs_calculated (no crítico): {e}", exc_info=True)

    def _send_alerts(self, statement_id: str):
        """
        Envía el log de actividad con mejor manejo de errores
        """
        try:
            data = {
                "financialStatementId": statement_id,
            }

            self.sqs_client.send_message(
                message=data,
                message_group_id=f"activity_1"  # Mejor particionamiento
            )

            logger.info(f"Log de actividad enviado para statement con id {statement_id}")

        except Exception as e:
            # Log el error pero no fallar la operación principal
            logger.error(f"Error enviando log de actividad (no crítico): {str(e)}")
            # No re-lanzar la excepción para no bloquear el flujo principal


    def _resolve_trailing_from_statement(
        self, statement_id: str
    ) -> Tuple[Optional[List[Dict]], Optional[str], Optional[List[Dict]], Optional[str]]:
        """
        LTM y MA desde períodos vivos en datapoints; fallback a metadata persistida en FS.
        Retorna (ltm_composition, ltm_title, ma_composition, ma_title).
        """
        statement = self.financial_statement_repository.find_by_id(statement_id)
        if not statement:
            raise NotFoundError(f"Financial statement {statement_id} not found")

        periodicity = getattr(statement, "statement_periodicity", None)
        all_datapoints = self._fetch_all_datapoints(statement_id=statement_id)
        valid = [
            dp for idx, dp in enumerate(all_datapoints)
            if self._validate_datapoint(dp, idx)
        ]

        ltm_title = ltm_composition = ma_title = ma_composition = None
        if valid:
            ltm_title, ltm_composition, ma_title, ma_composition = (
                resolve_trailing_compositions_from_datapoints(valid, periodicity)
            )

        if not ltm_composition:
            ltm_composition, ltm_title = get_ltm_composition(
                self.financial_statement_repository, statement_id
            )
        if not ma_composition:
            ma_composition, ma_title = get_monthly_annualized_composition(
                self.financial_statement_repository, statement_id
            )

        return ltm_composition, ltm_title, ma_composition, ma_title

    def _get_ltm(self, statement_id: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Obtiene composición LTM desde períodos vivos con fallback a FS."""
        try:
            ltm_composition, ltm_title, _, _ = self._resolve_trailing_from_statement(statement_id)
            if ltm_composition and ltm_title:
                logger.info(f"LTM found: title={ltm_title}, periods={len(ltm_composition)}")
            else:
                logger.info(f"No LTM data found for statement {statement_id}")
            return ltm_composition, ltm_title
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting LTM data for statement {statement_id}: {str(e)}")
            raise ServiceError(f"Error retrieving LTM data: {str(e)}")

    def _datapoints_by_period(self, statement_id: str) -> Dict[str, List]:
        """
        Agrupa datapoints por períodos (años y trimestres) para uso en LTM
        Retorna formato: {"2023": [datapoints], "2024Q1": [datapoints], ...}
        """
        try:
            logger.info(f"Starting datapoints grouping by period for LTM calculation: {statement_id}")

            all_datapoints = self._fetch_all_datapoints(statement_id=statement_id)

            if not all_datapoints:
                logger.warning(f"No datapoints found for statement_id: {statement_id}")
                return {}

            # Pre-filter with OutputService-specific validation
            valid_datapoints = [
                dp for idx, dp in enumerate(all_datapoints)
                if self._validate_datapoint(dp, idx)
            ]

            result = group_datapoints_by_period(valid_datapoints)

            logger.info(f"Datapoints grouped by period: {len(result)} periods, "
                        f"{len(all_datapoints)} total datapoints, "
                        f"{len(all_datapoints) - len(valid_datapoints)} invalid")

            return result

        except Exception as e:
            logger.error(f"Critical error in _datapoints_by_period: {str(e)}")
            raise ServiceError(f"Error grouping datapoints by period: {str(e)}")

    def _calculate_ltm_outputs(self, statement_id: str) -> List[Dict]:
        """
        Calcula outputs LTM usando la composición específica del financial statement
        """
        try:
            logger.info(f"Starting LTM output calculation for statement_id: {statement_id}")

            # 1. Obtener composición LTM del financial statement
            ltm_composition, ltm_title = self._get_ltm(statement_id)

            if not ltm_composition:
                logger.warning(f"No LTM composition found for statement_id: {statement_id}")
                return []

            logger.info(f"LTM composition: {ltm_composition}, title: {ltm_title}")

            # 2. Agrupar datapoints por período
            datapoints_by_period = self._datapoints_by_period(statement_id)

            if not datapoints_by_period:
                logger.warning(f"No datapoints found for LTM calculation: {statement_id}")
                return []

            # 3. Crear estructura LTM aplicando la fórmula a P&L
            ltm_datapoints = self._build_ltm_datapoints_structure(
                ltm_composition, datapoints_by_period, ltm_title
            )

            # 4. Obtener outputs aplicables para LTM (filtrados por evaluador del business)
            _stmt_ltm    = self.financial_statement_repository.find_by_id(statement_id)
            _biz_ltm     = self.business_repository.find_by_id(str(_stmt_ltm.business_id)) if _stmt_ltm else None
            _eval_ltm    = str(_biz_ltm.evaluator_id) if _biz_ltm else None
            all_outputs = self._fetch_all_outputs(evaluator_id=_eval_ltm)


            if not all_outputs:
                logger.warning("No LTM applicable outputs found")
                return []

            # 5. Calcular outputs LTM
            ltm_period_identifier = f"LTM_{ltm_title}"
            current_period = ltm_period_identifier  # El calculador usará este período para encontrar los datos LTM

            calculated_ltm_outputs = []
            successful_calculations = 0
            failed_calculations = 0

            logger.info(f"Calculating {len(all_outputs)} LTM outputs using period: {current_period}")

            for output_idx, output in enumerate(all_outputs):
                try:
                    if not self._validate_output(output, output_idx):
                        failed_calculations += 1
                        continue

                    script = output.script
                    output_id = output.id

                    logger.debug(f"Calculating LTM output {output.name}: script='{script}'")

                    # Usar calculadora con estructura LTM
                    # El calculador buscará automáticamente en ltm_datapoints[current_period]
                    result = self.calculator.calculate(
                        expression=script,
                        current_period=current_period,
                        datapoints_period=ltm_datapoints
                    )

                    if result is not None:
                        logger.debug(f"LTM calculation successful for {output.name}: result={result}")
                        successful_calculations += 1
                    else:
                        logger.warning(f"LTM calculation returned None for {output.name}")
                        failed_calculations += 1

                    # Crear registro LTM
                    ltm_output = {
                        "output_id": output_id,
                        "financial_statement_id": statement_id,
                        "value": result,
                        "year": None,  # LTM no tiene año específico
                        "period_type": "ltm",
                        "period_identifier": ltm_period_identifier,
                        "is_covenant_metric": self._is_covenant_output(output)
                    }
                    calculated_ltm_outputs.append(ltm_output)

                except Exception as e:
                    logger.error(f"Error calculating LTM output {getattr(output, 'name', 'unknown')}: {str(e)}")
                    failed_calculations += 1

                    # Crear registro con error
                    error_output = {
                        "output_id": getattr(output, 'id', None),
                        "financial_statement_id": statement_id,
                        "value": None,
                        "year": None,
                        "period_type": "ltm",
                        "period_identifier": ltm_period_identifier,
                        "is_covenant_metric": False
                    }
                    calculated_ltm_outputs.append(error_output)

            logger.info(f"LTM calculations completed: {successful_calculations} successful, "
                        f"{failed_calculations} failed, {len(calculated_ltm_outputs)} total records")

            return calculated_ltm_outputs

        except Exception as e:
            logger.error(f"Critical error in _calculate_ltm_outputs: {str(e)}")
            raise ServiceError(f"Error calculating LTM outputs: {str(e)}")

    def _build_ltm_datapoints_structure(
            self,
            ltm_composition: List[Dict],
            datapoints_by_period: Dict[str, List],
            ltm_title: str
    ) -> Dict[str, List]:
        """
        Construye la estructura de datapoints que el calculador LTM necesita.
        """
        return build_ltm_structure(ltm_composition, datapoints_by_period, ltm_title)

    def _build_ltm_pl_datapoints(
            self,
            ltm_composition: List[Dict],
            datapoints_by_period: Dict[str, List]
    ) -> List:
        """Construye los datapoints P&L aplicando la fórmula LTM."""
        return build_ltm_pl_datapoints(ltm_composition, datapoints_by_period)

    def _is_pl_datapoint(self, datapoint) -> bool:
        """Determina si un datapoint pertenece al P&L (Income Statement)."""
        return is_pl_datapoint(datapoint)

    def _is_bs_datapoint(self, datapoint) -> bool:
        """Determina si un datapoint pertenece al BS (Balance Sheet)."""
        return is_bs_datapoint(datapoint)

    def _create_negative_datapoints(self, datapoints: List) -> List:
        """Crea copias de datapoints con valores negativos para restar en LTM."""
        return create_negative_datapoints(datapoints)

    def _filter_ltm_applicable_outputs(self, all_outputs: List) -> List:
        """
        Filtra outputs que son aplicables para cálculos LTM
        Excluye métricas que no funcionan bien con LTM
        """
        ltm_applicable = []
        excluded_keywords = ['days', 'turnover', 'rotation', 'cycle']

        for output in all_outputs:
            try:
                output_name = getattr(output, 'name', '').lower()
                output_category = getattr(output, 'category', '').lower()

                # Excluir métricas de días de rotación
                if any(keyword in output_name for keyword in excluded_keywords):
                    logger.debug(f"Excluding output {output.name} - contains excluded keyword")
                    continue

                # Excluir categorías específicas
                if 'working_capital_days' in output_category:
                    logger.debug(f"Excluding output {output.name} - excluded category")
                    continue

                # Excluir scripts que usan offset (comparaciones período anterior)
                script = getattr(output, 'script', '')
                if 'offset=' in script:
                    logger.debug(f"Excluding output {output.name} - uses offset comparison")
                    continue

                ltm_applicable.append(output)

            except Exception as e:
                logger.warning(f"Error filtering output {getattr(output, 'id', 'unknown')}: {str(e)}")
                continue

        logger.info(f"Filtered {len(ltm_applicable)} LTM-applicable outputs from {len(all_outputs)} total")
        return ltm_applicable

    def _is_covenant_output(self, output) -> bool:
        """
        Determina si un output es una métrica de covenant importante
        """
        covenant_keywords = [
            'ebitda', 'debt', 'margin', 'ratio', 'coverage',
            'leverage', 'liquidity', 'current_ratio', 'roe', 'roa'
        ]

        try:
            output_name = getattr(output, 'name', '').lower()
            for keyword in covenant_keywords:
                if keyword in output_name:
                    return True
            return False
        except:
            return False

    def calculate_ltm_outputs(self, statement_id: str) -> bool:
        """
        Método principal para calcular outputs LTM (VERSION ACTUALIZADA)
        """
        try:
            logger.info(f"Starting LTM output calculation process for statement_id: {statement_id}")

            if not statement_id:
                raise ServiceError("statement_id is required and cannot be empty")

            # Calcular outputs LTM
            ltm_calculated_outputs = self._calculate_ltm_outputs(statement_id)

            if not ltm_calculated_outputs:
                logger.warning(f"No LTM outputs calculated for statement_id {statement_id}")
                return False

            # Guardar resultados LTM con nuevo constraint
            logger.info(f"Saving {len(ltm_calculated_outputs)} LTM outputs to database")

            try:
                with self.calculated_output_repository.transaction() as tx:
                    count = tx.upsert_many(
                        ltm_calculated_outputs,
                        ["output_id", "financial_statement_id", "period_type", "period_identifier"]  # NUEVO CONSTRAINT
                    )

                    logger.info(f"Successfully upserted {count} LTM calculated outputs")

            except Exception as e:
                logger.error(f"Database transaction failed for LTM outputs: {str(e)}")
                raise ServiceError(f"Failed to save LTM calculated outputs: {str(e)}")

            logger.info(f"✅ LTM output calculation completed successfully for statement_id: {statement_id}")

            return True

        except ServiceError:
            raise
        except Exception as e:
            logger.error(f"❌ Critical error in calculate_ltm_outputs: {str(e)}")
            raise ServiceError(f"Unexpected error during LTM calculation: {str(e)}")



    #get nuevo
    def get_calculated_outputs(self,
                               user: dict,
                               business_id: str,
                               output_names: Optional[List[str]] = None,
                               output_categories: Optional[List[str]] = None,
                               years: Optional[List[int]] = None,
                               period_types: Optional[List[str]] = None,
                               period_identifiers: Optional[List[str]] = None,
                               covenant_metrics_only: bool = False,
                               evaluator_id: Optional[str] = None,
                               page: int = 0,
                               size: int = 100,
                               required_all: bool = False
                               ) -> Dict[str, Any]:
        """
        Obtiene calculated outputs con información del output asociado (ACTUALIZADO PARA LTM)

        Args:
            user: Usuario que realiza la consulta
            business_id: ID del business
            output_names: Lista de nombres de output a filtrar
            output_categories: Lista de categorías de output a filtrar
            years: Lista de años (backward compatibility)
            period_types: Lista de tipos de período ['annual', 'quarterly', 'ltm']
            period_identifiers: Lista de identificadores ['2024', 'LTM_2024Q1']
            covenant_metrics_only: Si True, solo métricas de covenant
            page: Número de página (empezando en 0)
            size: Tamaño de página (máximo 1000)
            required_all: Si True, obtiene todos los resultados ignorando paginación

        Returns:
            Dict con calculated_outputs (lista) y type_currency del business
        """
        user_id = user.get('sub', 'unknown')
        logger.info(f"get_calculated_outputs called by user {user_id} for business {business_id}")

        if not business_id:
            logger.error("business_id is required")
            raise ServiceError("business_id is required")

        if not self.business_repository:
            raise ServiceError("business_repository is required")

        business = self.business_repository.find_by_id(business_id)
        if not business:
            logger.error(f"No se encontro business con id {business_id}")
            raise NotFoundError(f"No se encontro business con id {business_id}")

        type_currency = business.currency or "PEN"

        filters = {
            "business_id": business_id,
            "type": "OFFICIAL"
        }

        statement_official = self.financial_statement_repository.find_one_by_attributes(filters=filters)

        if not statement_official:
            logger.error(f"No se encontro financial statement oficial para business_id {business_id}")
            raise NotFoundError(f"No se encontro financial statement oficial para business_id {business_id}")

        statement_id = str(statement_official.id)

        size = max(1, min(size, 1000))
        page = max(0, page)

        # Logging de filtros aplicados
        filters_applied = []
        if output_names:
            filters_applied.append(f"output_names({len(output_names)})")
        if output_categories:
            filters_applied.append(f"output_categories({len(output_categories)})")
        if years:
            filters_applied.append(f"years({len(years)})")
        if period_types:
            filters_applied.append(f"period_types({','.join(period_types)})")
        if period_identifiers:
            filters_applied.append(f"period_identifiers({len(period_identifiers)})")
        if covenant_metrics_only:
            filters_applied.append("covenant_only")

        if filters_applied:
            logger.info(f"Applied filters: {', '.join(filters_applied)}")

        try:
            if required_all:
                logger.info("Fetching ALL calculated outputs (ignoring pagination)")
                all_calculated_outputs = self._fetch_all_calculated_outputs(
                    statement_id, output_names, output_categories, years,
                    period_types, period_identifiers, covenant_metrics_only,
                    evaluator_id=evaluator_id
                )
                calculated_outputs = [co.model_dump() for co in all_calculated_outputs]
            else:
                # Paginación normal
                offset = page * size
                logger.debug(f"Fetching page {page} with size {size} (offset: {offset})")

                calculated_outputs = self.calculated_output_repository.find_with_output_info_arrays(
                    statement_id=statement_id,
                    output_names=output_names,
                    output_categories=output_categories,
                    years=years,
                    period_types=period_types,
                    period_identifiers=period_identifiers,
                    covenant_metrics_only=covenant_metrics_only,
                    evaluator_id=evaluator_id,
                    limit=size,
                    offset=offset
                )

                logger.info(f"Retrieved {len(calculated_outputs)} calculated outputs for page {page}")
                calculated_outputs = [co.model_dump() for co in calculated_outputs]

            return {
                "calculated_outputs": calculated_outputs,
                "type_currency": type_currency,
            }

        except Exception as e:
            logger.error(f"Error fetching calculated outputs: {str(e)}", exc_info=True)
            raise ServiceError(f"Error fetching calculated outputs: {str(e)}")

    def _fetch_all_calculated_outputs(self,
                                      statement_id: str,
                                      output_names: Optional[List[str]] = None,
                                      output_categories: Optional[List[str]] = None,
                                      years: Optional[List[int]] = None,
                                      period_types: Optional[List[str]] = None,
                                      period_identifiers: Optional[List[str]] = None,
                                      covenant_metrics_only: bool = False,
                                      evaluator_id: Optional[str] = None
                                      ):
        """
        Función auxiliar para obtener todos los calculated outputs con paginación interna (ACTUALIZADA)
        """
        batch_size = 1000
        offset = 0
        all_calculated_outputs = []
        batch_count = 0

        logger.debug(f"Starting batch retrieval of calculated outputs for statement_id: {statement_id}")

        while True:
            try:
                batch_count += 1

                batch = self.calculated_output_repository.find_with_output_info_arrays(
                    statement_id=statement_id,
                    output_names=output_names,
                    output_categories=output_categories,
                    years=years,
                    period_types=period_types,
                    period_identifiers=period_identifiers,
                    covenant_metrics_only=covenant_metrics_only,
                    evaluator_id=evaluator_id,
                    limit=batch_size,
                    offset=offset
                )

                if not batch:
                    logger.debug(f"No data found in batch {batch_count}. Complete.")
                    break

                all_calculated_outputs.extend(batch)

                if len(batch) < batch_size:
                    logger.debug(f"Last batch: {len(batch)} items (< {batch_size})")
                    break

                if len(all_calculated_outputs) >= 50000:
                    logger.warning(f"Safety limit reached: {len(all_calculated_outputs)} items")
                    break

                offset += batch_size
                logger.debug(f"Batch {batch_count}: +{len(batch)} items. Total: {len(all_calculated_outputs)}")

            except Exception as e:
                logger.error(f"Error in batch {batch_count} for statement_id {statement_id}: {str(e)}")
                raise

        logger.info(
            f"Retrieved ALL calculated outputs: {len(all_calculated_outputs)} items in {batch_count} batch(es) for statement_id: {statement_id}")
        return all_calculated_outputs

    # -------------------------------------------------------------------------
    # MONTHLY ANNUALIZED OUTPUTS (independent from LTM — do not modify above)
    # -------------------------------------------------------------------------

    def _get_monthly_annualized(
        self,
        statement_id: str,
        ma_composition: Optional[List[Dict]] = None,
        ma_title: Optional[str] = None,
    ) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Obtiene MA composition/title; usa valores precalculados si se proveen."""
        if ma_composition is not None or ma_title is not None:
            return ma_composition, ma_title
        try:
            _, _, ma_composition, ma_title = self._resolve_trailing_from_statement(statement_id)
            if ma_composition and ma_title:
                logger.info(f"Monthly annualized found: title={ma_title}, periods={len(ma_composition)}")
            else:
                logger.info(f"No monthly annualized data for statement {statement_id}")
            return ma_composition, ma_title
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting monthly annualized data: {str(e)}")
            raise ServiceError(f"Error retrieving monthly annualized data: {str(e)}")

    def _count_months_in_composition(self, ma_composition: List[Dict]) -> int:
        """Cuenta cuántos meses distintos cubre la composición."""
        return count_months_in_composition(ma_composition)

    def _build_monthly_pl_datapoints(
            self,
            ma_composition: List[Dict],
            datapoints_by_period: Dict[str, List],
            annualization_factor: float
    ) -> List:
        """Construye datapoints P&L para el período mensual anualizado."""
        return build_monthly_pl_datapoints(ma_composition, datapoints_by_period, annualization_factor)

    def _find_latest_composition_period(self, ma_composition: List[Dict]) -> Optional[str]:
        """Retorna el período de la composición que tiene el mes más reciente."""
        return find_latest_composition_period(ma_composition)

    def _build_monthly_annualized_structure(
            self,
            ma_composition: List[Dict],
            datapoints_by_period: Dict[str, List],
            ma_title: str,
            annualization_factor: float
    ) -> Dict[str, List]:
        """Construye la estructura de datapoints para el calculador MA."""
        return build_monthly_annualized_structure(
            ma_composition, datapoints_by_period, ma_title, annualization_factor
        )

    def _calculate_monthly_annualized_outputs_internal(
        self,
        statement_id: str,
        ma_composition: Optional[List[Dict]] = None,
        ma_title: Optional[str] = None,
    ) -> List[Dict]:
        """Calcula outputs para el período mensual anualizado."""
        try:
            logger.info(f"Starting monthly annualized output calculation for statement_id: {statement_id}")

            ma_composition, ma_title = self._get_monthly_annualized(
                statement_id, ma_composition=ma_composition, ma_title=ma_title
            )
            if not ma_composition:
                logger.info(
                    f"Sin tramo parcial para anualizar en statement {statement_id} "
                    "(solo años cerrados o sin monthly_annualized_composition); se omite MA outputs"
                )
                return []

            logger.info(f"MA composition: {ma_composition}, title: {ma_title}")

            # Factor de anualización: 12 / n_meses
            n_months = self._count_months_in_composition(ma_composition)
            annualization_factor = 12.0 / n_months if n_months > 0 else 1.0
            logger.info(f"Annualization factor: 12/{n_months} = {annualization_factor:.4f}")

            datapoints_by_period = self._datapoints_by_period(statement_id)
            if not datapoints_by_period:
                logger.warning(f"No datapoints found for MA calculation: {statement_id}")
                return []

            ma_structure = self._build_monthly_annualized_structure(
                ma_composition, datapoints_by_period, ma_title, annualization_factor
            )

            _stmt_ma  = self.financial_statement_repository.find_by_id(statement_id)
            _biz_ma   = self.business_repository.find_by_id(str(_stmt_ma.business_id)) if _stmt_ma else None
            _eval_ma  = str(_biz_ma.evaluator_id) if _biz_ma else None
            all_outputs = self._fetch_all_outputs(evaluator_id=_eval_ma)
            if not all_outputs:
                logger.warning("No outputs found for MA calculation")
                return []

            ma_period_identifier = f"MA_{ma_title}"
            calculated_ma_outputs = []
            successful = 0
            failed = 0

            logger.info(f"Calculating {len(all_outputs)} MA outputs using period: {ma_period_identifier}")

            for output_idx, output in enumerate(all_outputs):
                try:
                    if not self._validate_output(output, output_idx):
                        failed += 1
                        continue

                    script = output.script
                    output_id = output.id

                    result = self.calculator.calculate(
                        expression=script,
                        current_period=ma_period_identifier,
                        datapoints_period=ma_structure
                    )

                    if result is not None:
                        successful += 1
                    else:
                        logger.warning(f"MA calculation returned None for {output.name}")
                        failed += 1

                    calculated_ma_outputs.append({
                        "output_id": output_id,
                        "financial_statement_id": statement_id,
                        "value": result,
                        "year": None,
                        "period_type": "monthly_annualized",
                        "period_identifier": ma_period_identifier,
                        "is_covenant_metric": self._is_covenant_output(output),
                    })

                except Exception as e:
                    logger.error(f"Error calculating MA output {getattr(output, 'name', 'unknown')}: {str(e)}")
                    failed += 1
                    calculated_ma_outputs.append({
                        "output_id": getattr(output, 'id', None),
                        "financial_statement_id": statement_id,
                        "value": None,
                        "year": None,
                        "period_type": "monthly_annualized",
                        "period_identifier": ma_period_identifier,
                        "is_covenant_metric": False,
                    })

            logger.info(
                f"MA calculations completed: {successful} successful, "
                f"{failed} failed, {len(calculated_ma_outputs)} total records"
            )
            return calculated_ma_outputs

        except Exception as e:
            logger.error(f"Critical error in _calculate_monthly_annualized_outputs_internal: {str(e)}")
            raise ServiceError(f"Error calculating monthly annualized outputs: {str(e)}")

    def calculate_monthly_annualized_outputs(
        self,
        statement_id: str,
        ma_composition: Optional[List[Dict]] = None,
        ma_title: Optional[str] = None,
    ) -> bool:
        """
        Método principal para calcular outputs de anualización mensual.
        Completamente independiente del flujo LTM.
        """
        try:
            logger.info(f"Starting monthly annualized output calculation for statement_id: {statement_id}")

            if not statement_id:
                raise ServiceError("statement_id is required and cannot be empty")

            ma_calculated_outputs = self._calculate_monthly_annualized_outputs_internal(
                statement_id,
                ma_composition=ma_composition,
                ma_title=ma_title,
            )

            if not ma_calculated_outputs:
                logger.warning(f"No monthly annualized outputs calculated for statement_id {statement_id}")
                return False

            logger.info(f"Saving {len(ma_calculated_outputs)} monthly annualized outputs to database")

            try:
                with self.calculated_output_repository.transaction() as tx:
                    count = tx.upsert_many(
                        ma_calculated_outputs,
                        ["output_id", "financial_statement_id", "period_type", "period_identifier"]
                    )
                    logger.info(f"Successfully upserted {count} monthly annualized outputs")

            except Exception as e:
                logger.error(f"Database transaction failed for MA outputs: {str(e)}")
                raise ServiceError(f"Failed to save monthly annualized outputs: {str(e)}")

            logger.info(f"✅ Monthly annualized output calculation completed for statement_id: {statement_id}")
            return True

        except ServiceError:
            raise
        except Exception as e:
            logger.error(f"❌ Critical error in calculate_monthly_annualized_outputs: {str(e)}")
            raise ServiceError(f"Unexpected error during monthly annualized calculation: {str(e)}")

    def _get_evaluator_id_for_statement(self, statement_id: str) -> Optional[str]:
        statement = self.financial_statement_repository.find_by_id(statement_id)
        if not statement or not self.business_repository:
            return None
        business = self.business_repository.find_by_id(str(statement.business_id))
        if not business:
            return None
        return str(business.evaluator_id)

    def _get_fs_config(self, evaluator_id: Optional[str]) -> Tuple[bool, bool]:
        """Retorna (show_ltm, show_annualized); defaults True, True si no hay config."""
        if not evaluator_id or not self.fs_config_repository:
            return True, True
        config = self.fs_config_repository.find_one_by_attributes(
            {"evaluator_id": evaluator_id}
        )
        if not config:
            return True, True
        return bool(getattr(config, "show_ltm", True)), bool(getattr(config, "show_annualized", True))

    def calculate_trailing_outputs(self, statement_id: str) -> Dict[str, Any]:
        """
        Orquesta LTM y anualizado según financial_statement_configs y períodos vivos.
        """
        if not statement_id:
            raise ServiceError("statement_id is required")

        evaluator_id = self._get_evaluator_id_for_statement(statement_id)
        show_ltm, show_annualized = self._get_fs_config(evaluator_id)

        ltm_composition, ltm_title, ma_composition, ma_title = (
            self._resolve_trailing_from_statement(statement_id)
        )

        result: Dict[str, Any] = {
            "ltm": {"success": False},
            "monthly_annualized": {"success": False},
            "skipped": {},
        }

        if not show_ltm:
            result["skipped"]["ltm"] = "show_ltm=False en financial_statement_configs"
            logger.info(f"LTM omitido para {statement_id}: show_ltm=False")
        elif not ltm_composition or not ltm_title:
            result["skipped"]["ltm"] = "LTM omitido: datos insuficientes"
            logger.info(f"LTM omitido para {statement_id}: sin composición válida")
        else:
            try:
                result["ltm"] = {"success": self.calculate_ltm_outputs(statement_id=statement_id)}
            except Exception as e:
                logger.error(f"Error en cálculo LTM outputs: {e}")
                result["ltm"] = {"success": False, "error": str(e)}

        if not show_annualized:
            result["skipped"]["monthly_annualized"] = "show_annualized=False en financial_statement_configs"
            logger.info(f"MA omitido para {statement_id}: show_annualized=False")
        elif not ma_composition or not ma_title:
            result["skipped"]["monthly_annualized"] = "Sin tramo parcial para anualizar"
            logger.info(f"MA omitido para {statement_id}: sin tramo parcial")
        else:
            try:
                result["monthly_annualized"] = {
                    "success": self.calculate_monthly_annualized_outputs(
                        statement_id=statement_id,
                        ma_composition=ma_composition,
                        ma_title=ma_title,
                    )
                }
            except Exception as e:
                logger.warning(f"Error en cálculo MA outputs: {e}")
                result["monthly_annualized"] = {"success": False, "error": str(e)}

        return result

    def recalculate_all(self, business_id: str) -> Dict[str, Any]:
        """
        Recalcula todos los outputs (annual + LTM + MA) para un business.
        Busca el financial statement OFFICIAL y ejecuta los 3 tipos de cálculo.
        """
        if not business_id:
            raise ServiceError("business_id es requerido")

        statement = self.financial_statement_repository.find_one_by_attributes(
            filters={"business_id": business_id, "type": "OFFICIAL"}
        )
        if not statement:
            raise NotFoundError(f"No existe financial statement OFFICIAL para business {business_id}")

        statement_id = str(statement.id)
        results: Dict[str, Any] = {}

        try:
            results["annual"] = {"success": self.calculate_outputs(statement_id=statement_id)}
        except Exception as e:
            logger.error(f"Error en cálculo anual outputs: {e}")
            results["annual"] = {"success": False, "error": str(e)}

        trailing = self.calculate_trailing_outputs(statement_id=statement_id)
        results["ltm"] = trailing.get("ltm", {"success": False})
        results["monthly_annualized"] = trailing.get("monthly_annualized", {"success": False})
        if trailing.get("skipped"):
            results["skipped"] = trailing["skipped"]

        return {"statement_id": statement_id, "results": results}
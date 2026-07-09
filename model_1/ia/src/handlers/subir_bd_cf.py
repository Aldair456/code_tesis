import logging
import json

from models.model_1.ia.src.config.dependencies_single import create_service_financial_datapoints

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

service = create_service_financial_datapoints()

def lambda_handler(event, context):
    """
    Handler para Lambda que procesa datos de Cash Flow (CF).
    Soporta:
    - Dict con 'data', 'statement_id', 'request_id' (formato estándar de extract_cf)
    """
    try:
        # Validar que el evento sea un dict
        if not isinstance(event, dict):
            logger.error(f"Formato inválido de event: {event}")
            return {
                "status": "FAIL",
                "statusCode": 400,
                "body": json.dumps({"error": "El evento debe ser un diccionario"})
            }

        # Extraer datos del evento
        data = event.get("data")
        statement_id = event.get("statement_id")
        request_id = event.get("request_id")

        # Validar campos requeridos
        if not data or not isinstance(data, list):
            logger.error(f"Campo 'data' inválido o faltante: {data}")
            return {
                "status": "FAIL",
                "statusCode": 400,
                "body": json.dumps({"error": "El campo 'data' debe ser una lista no vacía"})
            }

        if not statement_id:
            logger.error(f"Campo 'statement_id' faltante")
            return {
                "status": "FAIL",
                "statusCode": 400,
                "body": json.dumps({"error": "El campo 'statement_id' es requerido"})
            }

        # Construir el evento completo para el servicio
        cf_event = {
            "data": data,
            "statement_id": statement_id,
            "request_id": request_id
        }

        # Procesar datos de CF
        result = service.process_cashflow_data(cf_event)

        # Si process_cashflow_data retorna error
        if result.get("statusCode") != 200:
            return {
                "status": "FAIL",
                **result
            }

        return {
            "status": "SUCCESS",
            **result
        }

    except Exception as e:
        logger.exception("Error inesperado en handler")
        return {
            "status": "FAIL",
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


if __name__ == '__main__':
    # Evento de prueba con datos de CF
    event = {
        "statusCode": 200,
        "status": "ok",
        "request_id": "ffc5c903-3423-470b-892c-f25c76852954",
        "data": [
            {
                "name": "Flujo de caja de operación",
                "value": 43827,
                "year": 2024,
                "period": "2024Q2",
                "details": [
                    {
                        "name": "Flujos de Efectivo y Equivalente al Efectivo procedente de (utilizados en) Actividades de Operación",
                        "value": 43827
                    }
                ]
            },
            {
                "name": "Flujo de caja de inversión",
                "value": -5772,
                "year": 2024,
                "period": "2024Q2",
                "details": [
                    {
                        "name": "Flujos de Efectivo y Equivalente al Efectivo procedente de (utilizados en) Actividades de Inversión",
                        "value": -5772
                    }
                ]
            },
            {
                "name": "Flujo de caja de financiación",
                "value": -17425,
                "year": 2024,
                "period": "2024Q2",
                "details": [
                    {
                        "name": "Flujos de Efectivo y Equivalente al Efectivo procedente de (utilizados en) Actividades de Financiación",
                        "value": -17425
                    }
                ]
            }
        ],
        "statement_id": "853b5040-cbee-49ba-810a-d31952bdd9d8"
    }

    result = lambda_handler(event, None)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


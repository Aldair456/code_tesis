import json
import logging

import time
MAX_RETRIES = 3

from models.model_1.ia.src.config.dependencies import create_service_financial_statement_ia

# Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#Constante de reintentos
_MAX_RETRIES = MAX_RETRIES

service = create_service_financial_statement_ia()

def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio de procesamiento")

    try:
        # 1. Verificar BatchSize = 1
        records = event.get("Records", [])
        if len(records) != 1:
            msg = f"BatchSize debe ser 1, pero llegaron {len(records)} mensajes"
            logger.error(msg)
            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": msg
            }

        # 2. Parsear el mensaje
        try:
            body = json.loads(records[0]["body"])
        except (KeyError, json.JSONDecodeError) as e:
            msg = f"JSON inválido en body: {e}"
            logger.error(msg)
            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": msg,

            }
        # valores utiles para comunicar posibles fallos


        # 3. Extraer tablas y años para 'pl'
        tables = body.get("tables", {}).get("pl", "")
        years = body.get("years", {}).get("pl", [])
        object_key_json_output = body.get("object_key_json_output")
        _type = body.get("type")
        periodicity = body.get("periodicity")
        job_id = body.get("job_id")

        # Sin datos: OK pero sin procesamiento
        if not tables and not years:
            msg = "No había datos de tablas ni de años para 'pl'; se omitió el procesamiento."
            logger.warning(msg)



            return {
                "statusCode": 200,
                "status": "ok",
                "request_id": request_id,
                "message": msg,
                "object_key_json_output": object_key_json_output,
                "type": _type,
                "periodicity": periodicity,
                "job_id": job_id
            }


        # Sin tablas: error crítico
        if not tables:
            msg = "No se encontraron tablas para 'pl'; no se puede generar JSON."
            logger.error(msg)

            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": msg,
                "object_key_json_output": object_key_json_output,
                "type": _type,
                "periodicity": periodicity,
                "job_id": job_id
            }

        # Sin años: advertencia pero continúa
        if not years:
            msg = "No se encontraron años para 'pl'; el JSON puede estar incompleto."
            logger.warning(msg)






        # 4. Reintentos en generación de JSON

        try:
            result = service.generate_accounts_pl_with_retries(tables_text=tables, year_list=years)
            logger.info(f"JSON generado correctamente")
            return {
                "statusCode": 200,
                "status": "ok",
                "request_id": request_id,
                "data": result,
                "object_key_json_output": object_key_json_output,
                "type": _type,
                "periodicity": periodicity,
                "job_id": job_id
            }
        except Exception as err:
            logger.error("error al tartar de extraer la cuenta con reintentos")

            msg = f"Agotados {_MAX_RETRIES} intentos: {err}"


            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": msg,
            }




    except Exception as e:
        # Captura cualquier otro error no previsto
        msg = f"Excepción no controlada: {e}"
        logger.exception(msg)
        return {
            "statusCode": 200,
            "status": "error",
            "request_id": request_id,
            "error": msg
        }

# Si lo ejecutamos localmente para probar (solo con un evento de prueba)
if __name__ == '__main__':
    event = {
        "Records": [
            {
                "body": json.dumps({
                    "tables": {
                        "pl": """=== Resultados de Análisis de Textract ===

--- Tabla #1 ---
--- Tabla #1 ---
N/A | Nota | 2022 | 2021
N/A | N/A  | US$000 | US$000
Ventas | 1 | 50,000 | 45,000
Costo de ventas | 2 | (30,000) | (27,000)
Gastos administrativos | 3 | (5,000) | (4,800)


----------------------------------------"""
                    },
                    "years": {
                        "pl": [2022, 2021]
                    },
                    "statement_id": "64f1c9dc6c3a5b001fbadcde",
                    "user_id": "64f1c9dc6c3a5b001fbadcde"
                })
            }
        ]
    }

    print(lambda_handler(event, None))


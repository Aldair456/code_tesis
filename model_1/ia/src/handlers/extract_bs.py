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
        tables = body.get("tables", {}).get("bs", "")
        years = body.get("years", {}).get("bs", [])
        object_key_json_output = body.get("object_key_json_output")
        _type = body.get("type")
        periodicity = body.get("periodicity")
        job_id = body.get("job_id")

        # Sin datos: OK pero sin procesamiento
        if not tables and not years:
            msg = "No había datos de tablas ni de años para 'bs'; se omitió el procesamiento."
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
            msg = "No se encontraron tablas para 'bs'; no se puede generar JSON."
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
            msg = "No se encontraron años para 'bs'; el JSON puede estar incompleto."
            logger.warning(msg)

        # 4. Reintentos en generación de JSON

        try:
            result = service.generate_accounts_bs_with_retries(tables_text=tables, year_list=years)
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
    event2= {
  "Records": [
    {
      "body": "{\"periodicity_type\": \"trimestral\", \"statement_type\": \"all\", \"pages\": {\"bs\": [1, 1], \"pl\": [2, 2]}, \"tables\": {\"bs\": \"=== Resultados de Análisis de Textract ===\\n\\n\\n--- Tabla #1 ---\\nN/A | NOTA | N/A\\nPasivo | N/A | N/A\\nPasivo Corriente | N/A | N/A\\nAnticipos recibidos de Clientes | N/A | 5,741,021\\nTributos y aportes al sistema de pensiones | 7 | 1,697,682\\nCuentas por pagar diversas - asociada | 8 | 38,876\\nRemuneraciones y participaciones por pagar | 9 | 10,077,331\\nProvisiones | N/A | 2,919,992\\nCuentas por pagar comerciales - terceros | 10 | 53,284,955\\nObligaciones financieras a corto plazo | 11 | 129,663,656\\nPasivos por arrendamiento | 12 | 5,136,241\\nCuentas por pagar diversas - terceros | 13 | 10,036\\nTotal Pasivo Corriente | N/A | 208,569,790\\nPasivo no Corriente | N/A | N/A\\nObligaciones financieras a largo plazo | 11 | 201,457,724\\nImpuesto a la renta diferido | N/A | 37,076,938\\nPasivos por arrendamiento | 12 | 37,671,348\\nTributos y aportes al sistema de pensiones | 7 | 65,766\\nN/A | N/A | N/A\\nTotal Pasivo no Corriente | N/A | 276,271,776\\nPatrimonio | N/A | N/A\\nCapital | N/A | 357,217,447\\nExcedente de Revaluación | N/A | 144,159,041\\nResultados acumulados | N/A | (94,597,603)\\nResultados del ejercicio | N/A | (11,102,813)\\nTotal Patrimonio | N/A | 395,676,071\\nTotal Pasivo y Patrimonio | N/A | 880,517,638\\n\\n--- Tabla #2 ---\\nN/A | NOTA | N/A\\nActivo | N/A | N/A\\nActivo Corriente | N/A | N/A\\nEfectivo y equivalente de efectivo | 1 | 17,226,987\\nCuentas por cobrar comerciales - terceros | 2 | 22,278,480\\nCuentas por cobrar diversas - asociada | 3 | 2,922,540\\nCuentas por cobrar diversas - terceros | 4 | 5,262,449\\nServicios y otros contratados por anticipado | 5 | 1,265,947\\nSuministros Diversos | N/A | 152,374\\nTotal Activo Corriente | N/A | 49,108,777\\nActivo no Corriente | N/A | N/A\\nCuentas por cobrar diversas - terceros | 4 | 2,765,753\\nInversiones en asociada | N/A | 12,928,087\\nActivos por derecho de uso (neto) | 6 | 69,441,214\\nInmueble, maquinaria y equipo (neto) | 6 | 429,240,646\\nIntangible (neto) | 6 | 317,033,161\\nTotal Activo no Corriente | N/A | 831,408,861\\nTotal Activo | N/A | 880,517,638\\n\"}, \"years\": {\"bs\": [{\"year\": null, \"quarter\": null}]}, \"object_key_json_output\": \"FinancialStatementJson/cd1dc684-7ed6-42ab-a316-11e33772b78f.json\", \"type\": \"PB\", \"periodicity\": \"trimestral\", \"job_id\": \"e5ccf443-8c92-4d72-bfb2-c63209ce02f0\"}"
    }
  ]
}
    event = {
        'Records': [
            {
                'body': json.dumps(
                    {
                        'tables': {
                            'bs': '=== Resultados de Análisis de Textract ===\n\n...Tabla #1...'
                        },
                        'years': {
                            'bs': [{'year': 2023, 'quarter': 'Q1'}, {'year': 2024, 'quarter': 'Q1'}]
                        }
                    }
                )
            }
        ]
    }

    print(lambda_handler(event2, None))
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
    logger.info(f"Inicio de procesamiento CF")

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


        # 3. Extraer tablas y años para 'cf'
        tables = body.get("tables", {}).get("CF", "")
        years_dict = body.get("years", {})
        object_key_json_output = body.get("object_key_json_output")
        _type = body.get("type")
        periodicity = body.get("periodicity")
        job_id = body.get("job_id")

        # Obtener años de cualquier tipo disponible (BS, PL, etc.)
        years = []
        if years_dict:
            # Agarrar el primero que encuentre (BS, PL, o el que sea)
            for key in years_dict:
                years = years_dict[key]
                logger.info(f"Usando años de '{key}' para CF: {years}")
                break

        # Sin datos: OK pero sin procesamiento
        if not tables and not years:
            msg = "No había datos de tablas ni de años para 'CF'; se omitió el procesamiento."
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
            msg = "No se encontraron tablas para 'CF'; no se puede generar JSON."
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
            msg = "No se encontraron años para 'CF'; el JSON puede estar incompleto."
            logger.warning(msg)

        # 4. Extraer flujos principales con todas sus partidas en details
        try:
            result = service.generate_accounts_cf_main_with_retries(
                tables_text=tables, 
                year_list=years
            )
            logger.info(f"JSON de CF generado correctamente. Total de elementos: {len(result)}")
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
            logger.error(f"Error al extraer flujos de CF: {err}")
            msg = f"Error al extraer flujos de CF: {err}"
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
                "messageId": "b2fffb36-f3e5-4012-bc69-3bfdddf20937",
                "receiptHandle": "AQEBYvxtSGNLYGo+Eyyu5kmmM/q/5cpQh65jFiU8+QypOhb72AEy64jIgWfrGc2x4tJAWAa9C5CaKBRj8IgMbXy7UmzDdHMZeJXxW3ksKKNNDCIEzgBAAD8KWKOe7ehRMmUCOK3E0f8M7tL6rRvPFd/OX4h3XkRJ8K5NgJoA4txSC+zmwfPfvOuCpr91mdNqPI5c70btOdTFCRoZbGb8cj+5gePWnT/hlxvbPV9dBAZaBAqH0dcFHNgTr9UVWfStUrIry3z2/cPZqOo4nT6bTCxI0g==",
                "body": "{\"statement_id\": \"01565407-868b-4d4c-b76e-0f1e941a125e\", \"periodicity_type\": \"anual\", \"statement_type\": \"all\", \"pages\": {\"bs\": [9, 9], \"pl\": [10, 10], \"CF\": [2, 3, 11, 13, 14]}, \"tables\": {\"bs\": \"=== Resultados de Análisis de Textract ===\\n\\n\\n--- Tabla #1 ---\\nN/A | Nota | 2023 S/(000) | 2022 S/(000)\\nActivos | N/A | N/A | N/A\\nActivos corrientes | N/A | N/A | N/A\\nEfectivo y equivalentes de efectivo | 6 | 26,973 | 56,926\\nOtros instrumentos financieros | 27 | - | 86,893\\nCuentas por cobrar comerciales y diversas, neto | 7 | 17,682 | 57,669\\nInventarios | 8 | 706,427 | 799,468\\nGastos pagados por adelantado | N/A | 3,030 | 20,881\\nTotal activos corrientes | N/A | 754,112 | 1,021,837\\nActivos no corrientes | N/A | N/A | N/A\\nCuentas por cobrar diversas, neto | 7 | 40,569 | 40,034\\nInversión financiera al valor razonable con cambios en otros resultados integrales | N/A | 249 | 274\\nInversiones en subsidiarias | 9 | 569,675 | 492,492\\nPropiedad, planta y equipo, neto | 10 | 1,793,711 | 1,680,556\\nIntangibles, neto | 11 | 26,713 | 27,939\\nActivos por derecho de uso, neto | N/A | 781 | 1,507\\nTotal activos no corrientes | N/A | 2,431,698 | 2,242,802\\nTotal activos | N/A | 3,185,810 | 3,264,639\\nPasivos y patrimonio neto | N/A | N/A | N/A\\nPasivos corrientes | N/A | N/A | N/A\\nCuentas por pagar comerciales y diversas | 12 | 227,552 | 262,118\\nObligaciones financieras | 14 | 383,146 | 618,907\\nPasivos por arrendamientos | N/A | 865 | 854\\nProvisiones | 13 | 45,146 | 19,813\\nImpuesto a la renta por pagar | N/A | 13,787 | 16,215\\nTotal pasivos corrientes | N/A | 670,496 | 917,907\\nPasivos no corrientes | N/A | N/A | N/A\\nObligaciones financieras | 14 | 1,189,880 | 974,264\\nPasivos por arrendamientos | N/A | 60 | 967\\nProvisiones | 13 | 25,191 | 45,337\\nPasivo por impuesto a la renta diferido | 15 | 110,175 | 131,029\\nTotal pasivos no corrientes | N/A | 1,325,306 | 1,151,597\\nTotal pasivos | N/A | 1,995,802 | 2,069,504\\nPatrimonio neto | 16 | N/A | N/A\\nCapital | N/A | 423,868 | 423,868\\nAcciones de inversión | N/A | 40,279 | 40,279\\nAcciones de inversión en tesorería | N/A | (121,258) | (121,258)\\nCapital adicional | N/A | 432,779 | 432,779\\nReserva legal | N/A | 168,636 | 168,636\\nOtros resultados integrales acumulados | N/A | (16,290) | (17,787)\\nResultados acumulados | N/A | 261,994 | 268,618\\nTotal patrimonio neto | N/A | 1,190,008 | 1,195,135\\nTotal pasivos y patrimonio neto | N/A | 3,185,810 | 3,264,639\\n\\n----------------------------------------\\n\\n--- Tabla #2 ---\\nN/A | Nota | 2023 S/(000) | 2022 S/(000)\\nActivos | N/A | N/A | N/A\\nActivos corrientes | N/A | N/A | N/A\\nEfectivo y equivalentes de efectivo | 6 | 26,973 | 56,926\\nOtros instrumentos financieros | 27 | - | 86,893\\nCuentas por cobrar comerciales y diversas, neto | 7 | 17,682 | 57,669\\nInventarios | 8 | 706,427 | 799,468\\nGastos pagados por adelantado | N/A | 3,030 | 20,881\\nTotal activos corrientes | N/A | 754,112 | 1,021,837\\nActivos no corrientes | N/A | N/A | N/A\\nCuentas por cobrar diversas, neto | 7 | 40,569 | 40,034\\nInversión financiera al valor razonable con cambios en otros resultados integrales | N/A | 249 | 274\\nInversiones en subsidiarias | 9 | 569,675 | 492,492\\nPropiedad, planta y equipo, neto | 10 | 1,793,711 | 1,680,556\\nIntangibles, neto | 11 | 26,713 | 27,939\\nActivos por derecho de uso, neto | N/A | 781 | 1,507\\nTotal activos no corrientes | N/A | 2,431,698 | 2,242,802\\nTotal activos | N/A | 3,185,810 | 3,264,639\\nPasivos y patrimonio neto | N/A | N/A | N/A\\nPasivos corrientes | N/A | N/A | N/A\\nCuentas por pagar comerciales y diversas | 12 | 227,552 | 262,118\\nObligaciones financieras | 14 | 383,146 | 618,907\\nPasivos por arrendamientos | N/A | 865 | 854\\nProvisiones | 13 | 45,146 | 19,813\\nImpuesto a la renta por pagar | N/A | 13,787 | 16,215\\nTotal pasivos corrientes | N/A | 670,496 | 917,907\\nPasivos no corrientes | N/A | N/A | N/A\\nObligaciones financieras | 14 | 1,189,880 | 974,264\\nPasivos por arrendamientos | N/A | 60 | 967\\nProvisiones | 13 | 25,191 | 45,337\\nPasivo por impuesto a la renta diferido | 15 | 110,175 | 131,029\\nTotal pasivos no corrientes | N/A | 1,325,306 | 1,151,597\\nTotal pasivos | N/A | 1,995,802 | 2,069,504\\nPatrimonio neto | 16 | N/A | N/A\\nCapital | N/A | 423,868 | 423,868\\nAcciones de inversión | N/A | 40,279 | 40,279\\nAcciones de inversión en tesorería | N/A | (121,258) | (121,258)\\nCapital adicional | N/A | 432,779 | 432,779\\nReserva legal | N/A | 168,636 | 168,636\\nOtros resultados integrales acumulados | N/A | (16,290) | (17,787)\\nResultados acumulados | N/A | 261,994 | 268,618\\nTotal patrimonio neto | N/A | 1,190,008 | 1,195,135\\nTotal pasivos y patrimonio neto | N/A | 3,185,810 | 3,264,639\\n\\n----------------------------------------\\n\", \"pl\": \"=== Resultados de Análisis de Textract ===\\n\\n\\n--- Tabla #1 ---\\nN/A | Nota | 2023 S/(000) | 2022 S/(000)\\nVentas netas | 17 | 1,275,355 | 1,365,057\\nCosto de ventas | 18 | (797,078) | (929,479)\\nUtilidad bruta | N/A | 478,277 | 435,578\\nIngresos (gastos) operativos | N/A | N/A | N/A\\nGastos administrativos | 19 | (196,366) | (189,665)\\nGastos de ventas y distribución | 20 | (14,139) | (11,416)\\nOtros ingresos operativos, neto | N/A | 1,543 | 6,882\\nDeterioro por baja de propiedad, planta y equipo | 10(b) | (36,551) | -\\nTotal gastos operativos, neto | N/A | (245,513) | (194,199)\\nUtilidad operativa | N/A | 232,764 | 241,379\\nOtros ingresos (gastos) | N/A | N/A | N/A\\nIngresos financieros | N/A | 4,339 | 1,472\\nCostos financieros | 22 | (107,555) | (95,651)\\nGanancia (pérdida) neta por instrumentos financieros derivados a valor razonable con cambios en resultados | 27(a) | 19 | (59)\\nParticipación en resultados de las subsidiarias | 9(c) | 75,016 | 79,441\\nGanancia (pérdida) neta por diferencia en cambio | 5 | 5,684 | (1,269)\\nTotal otros gastos, neto | N/A | (22,497) | (16,066)\\nUtilidad antes del impuesto a la renta | N/A | 210,267 | 225,313\\nImpuesto a la renta | 15 | (41,367) | (48,485)\\nUtilidad neta del año | N/A | 168,900 | 176,828\\nUtilidad por acción | N/A | N/A | N/A\\nUtilidad básica y diluida del año atribuible a los tenedores de acciones comunes y de inversión (S/ por acción) | 24 | 0.39 | 0.41\\n\\n----------------------------------------\\n\\n--- Tabla #2 ---\\nN/A | Nota | 2023 S/(000) | 2022 S/(000)\\nVentas netas | 17 | 1,275,355 | 1,365,057\\nCosto de ventas | 18 | (797,078) | (929,479)\\nUtilidad bruta | N/A | 478,277 | 435,578\\nIngresos (gastos) operativos | N/A | N/A | N/A\\nGastos administrativos | 19 | (196,366) | (189,665)\\nGastos de ventas y distribución | 20 | (14,139) | (11,416)\\nOtros ingresos operativos, neto | N/A | 1,543 | 6,882\\nDeterioro por baja de propiedad, planta y equipo | 10(b) | (36,551) | -\\nTotal gastos operativos, neto | N/A | (245,513) | (194,199)\\nUtilidad operativa | N/A | 232,764 | 241,379\\nOtros ingresos (gastos) | N/A | N/A | N/A\\nIngresos financieros | N/A | 4,339 | 1,472\\nCostos financieros | 22 | (107,555) | (95,651)\\nGanancia (pérdida) neta por instrumentos financieros derivados a valor razonable con cambios en resultados | 27(a) | 19 | (59)\\nParticipación en resultados de las subsidiarias | 9(c) | 75,016 | 79,441\\nGanancia (pérdida) neta por diferencia en cambio | 5 | 5,684 | (1,269)\\nTotal otros gastos, neto | N/A | (22,497) | (16,066)\\nUtilidad antes del impuesto a la renta | N/A | 210,267 | 225,313\\nImpuesto a la renta | 15 | (41,367) | (48,485)\\nUtilidad neta del año | N/A | 168,900 | 176,828\\nUtilidad por acción | N/A | N/A | N/A\\nUtilidad básica y diluida del año atribuible a los tenedores de acciones comunes y de inversión (S/ por acción) | 24 | 0.39 | 0.41\\n\\n----------------------------------------\\n\", \"CF\": \"=== Resultados de Análisis de Textract ===\\n\\n\\n--- Tabla #1 ---\\nLima | Lima Il | Arequipa | Trujillo\\nAv. Víctor Andrés Belaunde 171 | Av. Jorge Basadre 330 San Isidro | Av. Bolognesi 407 Yanahuara | Av. El Golf 591 Urb. Del Golf III Víctor Larco Herrera 13009,\\nSan Isidro Tel: +51(1)411 44444 | Tel: +51(1)411 44444 | Tel: +51 (54) 484 470 | Sede Miguel Ángel Quijano Doig La Libertad Tel: +51(44)608830\\n\\n----------------------------------------\\n\\n--- Tabla #2 ---\\nN/A | Nota | 2023 S/(000) | 2022 S/(000)\\nUtilidad neta del año | N/A | 168,900 | 176,828\\nOtros resultados integrales | N/A | N/A | N/A\\nOtros resultados integrales que no se reclasificarán a resultados en periodos posteriores: | N/A | N/A | N/A\\nActualización en el valor razonable de instrumentos financieros al valor razonable con cambios en otros resultados integrales | N/A | (25) | (565)\\nImpuesto a la renta diferido | 15 | 7 | 167\\nOtros resultados integrales que se reclasificarán a resultados en periodos posteriores: | N/A | N/A | N/A\\nGanancia neta por instrumentos de cobertura de flujos de efectivo | 27(a) | 2,154 | 3,838\\nImpuesto a la renta diferido | 15 | (634) | (1,133)\\nOtros resultados integrales del año, neto de impuesto a la renta | N/A | 1,502 | 2,307\\nTotal otros resultados integrales del año, neto de impuesto a la renta | N/A | 170,402 | 179,135\\n\\n----------------------------------------\\n\\n--- Tabla #3 ---\\nN/A | Nota | 2023 S/(000) | 2022 S/(000)\\nActividades de operación | N/A | N/A | N/A\\nUtilidad antes del impuesto a la renta | N/A | 210,267 | 225,313\\nAjustes para conciliar la utilidad antes del impuesto a la renta con los flujos netos de efectivo: | N/A | N/A | N/A\\nDepreciación y amortización | N/A | 105,816 | 98,874\\nCostos financieros | 22 | 107,555 | 95,651\\nDeterioro por baja de propiedad, planta y equipo | 10 (b) | 36,551 | N/A\\nProvisión para compensación a funcionarios a largo plazo | 13(c) y 21 | 7,632 | 8,272\\nEstimación de provisión por obsolescencia de inventarios, neto | 8(b) | 1,589 | 641\\nDiferencia en cambio relacionada a transacciones monetarias | N/A | 40 | 3,775\\nParticipación en los resultados de las subsidiarias | 9(c) | (75,016) | (79,441)\\nIngresos financieros | N/A | (4,339) | (1,472)\\nGanancia neta en enajenación de propiedad, planta y equipo e intangible | N/A | (293) | (269)\\n(Ganancia) pérdida por instrumentos financieros derivados a valor razonable con cambios en resultados | 27(a) | (19) | 59\\nOtras partidas que no generan flujos operativos, neto | N/A | 16,543 | 7,902\\nCambios en los activos y pasivos operativos: | N/A | N/A | N/A\\nDisminución en cuentas por cobrar comerciales y diversas | N/A | 37,618 | 58,781\\nDisminución (aumento) de inventarios | N/A | 90,751 | (284,976)\\nDisminución (aumento) en gastos pagados por adelantado | N/A | 14,219 | (8,854)\\n(Disminución) aumento en cuentas por pagar comerciales y diversas | N/A | (32,616) | 57,242\\nN/A | N/A | 516,298 | 181,498\\nCobro de intereses | N/A | 4,596 | 1,987\\nPago de intereses | N/A | (100,927) | (81,333)\\nPago de impuesto a la renta | N/A | (69,426) | (56,462)\\nEfectivo neto proveniente de las actividades de operación | N/A | 350,541 | 45,690\\n\\n----------------------------------------\\n\\n--- Tabla #4 ---\\nN/A | Nota | 2023 S/(000) | 2022 S/(000)\\nActividades de inversión | N/A | N/A | N/A\\nApertura de depósitos a plazo con vencimiento | N/A | (10,000) | N/A\\noriginal mayor a 90 días | N/A | N/A | N/A\\nRedención de depósitos a plazo con vencimiento original mayor a 90 días | N/A | 10,000 | N/A\\nCompra de propiedad, planta y equipo | 10(a) | (261,173) | (148,498)\\nCompra de intangibles | 11(a) | (7,441) | (5,858)\\nPréstamos otorgados a subsidiarias | 23 | (7,116) | N/A\\nAportes a subsidiarias | 9(d) | (1,745) | (917)\\nCompra de inversiones disponible de venta | N/A | N/A | (363)\\nPréstamos otorgados a terceros | N/A | (1,529) | (141)\\nDividendos recibidos de subsidiarias | 9(d) | N/A | 4,989\\nInversión en nuevos negocios | 9(d) | (321) | N/A\\nCobro de préstamos a subsidiarias | 23 | 7,116 | N/A\\nFlujos procedentes de la venta de intangible | N/A | 2,018 | N/A\\nFlujos procedentes de la venta de propiedad, planta y equipo | N/A | 705 | 829\\nDevolución de capital Calizas | 9(d) | N/A | 679\\nEfectivo neto utilizado en las actividades de inversión | N/A | (269,486) | (149,280)\\nActividades de financiamiento | N/A | N/A | N/A\\nObtención de sobregiro bancario | N/A | 85,333 | N/A\\nPago de sobregiro bancario | N/A | (85,333) | N/A\\nPréstamos bancarios pagados | 26 | (661,520) | (448,984)\\nDividendos pagados | 26 | (175,431) | (179,820)\\nPago de costo financiero de instrumentos de cobertura | 26 | (7,708) | (15,390)\\nPago por arrendamientos | N/A | (1,097) | (1,104)\\nPréstamos bancarios recibidos | 26 | 639,000 | 525,000\\nFlujo por liquidación de instrumentos financieros derivados | N/A | 93,323 | N/A\\nObtención de préstamos de subsidiarias | 23 | 2,000 | 105,710\\nDevolución de dividendos | 26 | 465 | 229\\nPago de préstamos obtenidos de subsidiarias | 23 | N/A | (57,000)\\nEfectivo neto utilizado en las actividades de financiamiento | N/A | (110,968) | (71,359)\\nDisminución neta de efectivo y equivalentes de efectivo | N/A | (29,913) | (174,949)\\nDiferencia de cambio neta | N/A | (40) | (5,755)\\nEfectivo y equivalentes de efectivo al 1 de enero | 6 | 56,926 | 237,630\\nEfectivo y equivalentes de efectivo al 31 de diciembre | 6 | 26,973 | 56,926\\nTransacciones sin efecto en los flujos de caja | N/A | N/A | N/A\\nDiferencia en cambio no liquidada relacionada a transacciones monetarias | N/A | 40 | 3,775\\nCompra de propiedad, planta y equipo, pendientes de pago | 10(e) | 6,214 | 10,804\\nAdiciones de activos por cierre de cantera | 13 | 4,494 | 3,481\\nVenta de propiedad, planta y equipo, pendiente de cobro | 7 | 78 | 112\\n\\n----------------------------------------\\n\"}, \"years\": {\"bs\": [2023, 2022], \"pl\": [2023, 2022]}, \"processing_metadata\": {\"processed_at\": 1762225903.7159684, \"bucket_name\": \"mi-bucket-financiero-dev2\", \"object_key\": \"FinancialStatements/01565407-868b-4d4c-b76e-0f1e941a125e.pdf\"}}",
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1762225939925",
                    "SequenceNumber": "37344617988039903232",
                    "MessageGroupId": "financial_statements",
                    "SenderId": "AIDAQYEI45KJOALLFMJAI",
                    "MessageDeduplicationId": "4e405d6a-6cee-42d9-998e-3b78d2cf49fd",
                    "ApproximateFirstReceiveTimestamp": "1762225939925"
                },
                "messageAttributes": {},
                "md5OfBody": "1b409580e04e294f0728909382928582",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-1:051826715282:cola_2_de_ia.fifo",
                "awsRegion": "us-east-1"
            }
        ]
    }

    print(lambda_handler(event, None))


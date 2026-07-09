import logging
import json

from models.model_1.ia.src.config.dependencies import create_service_financial_statement_ia
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

service = create_service_financial_statement_ia()
def lambda_handler(event, context):
    """
    Handler para Lambda que procesa datos financieros.
    """
    try:
        if not isinstance(event, list):
            logger.error(f"Formato inválido de event: {event}")
            return {
                "status": "FAIL",
                "statusCode": 400,
                "body": json.dumps({"error": "El evento debe ser una lista"})
            }

        result = service.process_financial_data(event)

        # Si process_financial_data retorna error
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


event=[
  {
    "statusCode": 200,
    "status": "ok",
    "request_id": "4d01bcf0-4f92-43ff-abab-df344ad5f583",
    "object_key_json_output": "trimestrales/test1.json",
    "type": "PB",
    "periodicity": "anual",
    "data": [
      {
        "name": "SALES",
        "value": 1232589,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Ventas netas",
            "value": 1232589
          }
        ],
        "tags": [
          "gm"
        ],
        "value_type": "positive",
        "priority": 10000,
        "display_name": "Ventas"
      },
      {
        "name": "COGS",
        "value": -721363,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Costo de ventas",
            "value": 721363
          }
        ],
        "tags": [
          "gm",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Costo de Ventas"
      },
      {
        "name": "ADMIN_EXPENSES",
        "value": -209490,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Gastos administrativos",
            "value": 209490
          }
        ],
        "tags": [
          "om",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Gastos administrativos"
      },
      {
        "name": "SALES_EXPENSES",
        "value": -17731,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Gastos de ventas y distribución",
            "value": 17731
          }
        ],
        "tags": [
          "om",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Gastos de ventas"
      },
      {
        "name": "OTHER_OPERATING_INCOME",
        "value": 17881,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Otros ingresos operativos, neto",
            "value": 17881
          }
        ],
        "tags": [
          "om"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Otros ingresos operativos"
      },
      {
        "name": "FINANCIAL_INCOME",
        "value": 3341,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Ingresos financieros",
            "value": 3341
          }
        ],
        "tags": [
          "ebt"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Ingresos financieros"
      },
      {
        "name": "INTEREST_EXPENSES",
        "value": -101473,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Costos financieros",
            "value": 101473
          }
        ],
        "tags": [
          "ebt",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Gastos financieros por intereses"
      },
      {
        "name": "PARTICIPATION_IN_RELATED_COMPANIES",
        "value": 59318,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Participación en resultados de las subsidiarias",
            "value": 59318
          }
        ],
        "tags": [
          "ebt"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Participación en relacionadas"
      },
      {
        "name": "EXCHANGE_RATE_EXPENSES",
        "value": -142,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Pérdida neta por diferencia en cambio",
            "value": 142
          }
        ],
        "tags": [
          "ebt",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Gastos por tipo de cambio"
      },
      {
        "name": "TAXES",
        "value": -64055,
        "year": 2024,
        "period": "2024",
        "details": [
          {
            "name": "Impuesto a la renta",
            "value": -64055
          }
        ],
        "tags": [
          "nm"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Impuestos"
      },
      {
        "name": "SALES",
        "value": 1275355,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Ventas netas",
            "value": 1275355
          }
        ],
        "tags": [
          "gm"
        ],
        "value_type": "positive",
        "priority": 10000,
        "display_name": "Ventas"
      },
      {
        "name": "COGS",
        "value": -797078,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Costo de ventas",
            "value": 797078
          }
        ],
        "tags": [
          "gm",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Costo de Ventas"
      },
      {
        "name": "ADMIN_EXPENSES",
        "value": -194907,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Gastos administrativos",
            "value": 194907
          }
        ],
        "tags": [
          "om",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Gastos administrativos"
      },
      {
        "name": "SALES_EXPENSES",
        "value": -15598,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Gastos de ventas y distribución",
            "value": 15598
          }
        ],
        "tags": [
          "om",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Gastos de ventas"
      },
      {
        "name": "OTHER_OPERATING_INCOME",
        "value": 1543,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Otros ingresos operativos, neto",
            "value": 1543
          }
        ],
        "tags": [
          "om"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Otros ingresos operativos"
      },
      {
        "name": "OTHER_OPERATING_EXPENSES",
        "value": -36551,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Deterioro por baja de propiedad, planta y equipo",
            "value": -36551
          }
        ],
        "tags": [
          "om"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Otros egresos operativos"
      },
      {
        "name": "FINANCIAL_INCOME",
        "value": 4358,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Ingresos financieros",
            "value": 4339
          },
          {
            "name": "Ganancia neta por instrumentos financieros derivados",
            "value": 19
          }
        ],
        "tags": [
          "ebt"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Ingresos financieros"
      },
      {
        "name": "INTEREST_EXPENSES",
        "value": -107555,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Costos financieros",
            "value": 107555
          }
        ],
        "tags": [
          "ebt",
          "expense"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Gastos financieros por intereses"
      },
      {
        "name": "PARTICIPATION_IN_RELATED_COMPANIES",
        "value": 75016,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Participación en resultados de las subsidiarias",
            "value": 75016
          }
        ],
        "tags": [
          "ebt"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Participación en relacionadas"
      },
      {
        "name": "EXCHANGE_RATE_INCOME",
        "value": 5684,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Ganancia neta por diferencia en cambio",
            "value": 5684
          }
        ],
        "tags": [
          "ebt"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Ingresos por tipo de cambio"
      },
      {
        "name": "TAXES",
        "value": -41367,
        "year": 2023,
        "period": "2023",
        "details": [
          {
            "name": "Impuesto a la renta",
            "value": -41367
          }
        ],
        "tags": [
          "nm"
        ],
        "value_type": "positive",
        "priority": 0,
        "display_name": "Impuestos"
      }
    ],
    "statement_id": "9bac3281-254f-4af8-884a-a1d71108e57f"
  },
  {
    "statusCode": 200,
    "status": "ok",
    "request_id": "f74d7c0d-7a24-4f9c-af62-ae8bfd3debcc",
    "data": [
      {
        "name": "CASH",
        "value": 25019,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Efectivo y equivalentes de efectivo",
            "value": 25019
          }
        ]
      },
      {
        "name": "CASH",
        "value": 26973,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Efectivo y equivalentes de efectivo",
            "value": 26973
          }
        ]
      },
      {
        "name": "ACCOUNTS_RECEIVABLE",
        "value": 74372,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Cuentas por cobrar comerciales y diversas, neto",
            "value": 74372
          }
        ]
      },
      {
        "name": "ACCOUNTS_RECEIVABLE",
        "value": 17682,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Cuentas por cobrar comerciales y diversas, neto",
            "value": 17682
          }
        ]
      },
      {
        "name": "INVENTORY",
        "value": 680316,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Inventarios",
            "value": 680316
          }
        ]
      },
      {
        "name": "INVENTORY",
        "value": 706427,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Inventarios",
            "value": 706427
          }
        ]
      },
      {
        "name": "PRE_PAID_EXPENSES",
        "value": 3934,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Gastos pagados por adelantado",
            "value": 3934
          }
        ]
      },
      {
        "name": "PRE_PAID_EXPENSES",
        "value": 3030,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Gastos pagados por adelantado",
            "value": 3030
          }
        ]
      },
      {
        "name": "OTHER_ACCOUNTS_RECEIVABLE_LT",
        "value": 40945,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Cuentas por cobrar diversas, neto",
            "value": 40945
          }
        ]
      },
      {
        "name": "OTHER_ACCOUNTS_RECEIVABLE_LT",
        "value": 40569,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Cuentas por cobrar diversas, neto",
            "value": 40569
          }
        ]
      },
      {
        "name": "INVESTMENTS_IN_MARKETABLE_SECURITIES",
        "value": 239,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Inversión financiera al valor razonable con cambios en otros resultados integrales",
            "value": 239
          }
        ]
      },
      {
        "name": "INVESTMENTS_IN_MARKETABLE_SECURITIES",
        "value": 249,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Inversión financiera al valor razonable con cambios en otros resultados integrales",
            "value": 249
          }
        ]
      },
      {
        "name": "INVESTMENTS_IN_SUBSIDIARIES",
        "value": 498934,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Inversiones en subsidiarias",
            "value": 498934
          }
        ]
      },
      {
        "name": "INVESTMENTS_IN_SUBSIDIARIES",
        "value": 569675,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Inversiones en subsidiarias",
            "value": 569675
          }
        ]
      },
      {
        "name": "PROPERTY_PLANT_EQUIPMENT",
        "value": 1718519,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Propiedad, planta y equipo, neto",
            "value": 1718519
          }
        ]
      },
      {
        "name": "PROPERTY_PLANT_EQUIPMENT",
        "value": 1793711,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Propiedad, planta y equipo, neto",
            "value": 1793711
          }
        ]
      },
      {
        "name": "INTANGIBLES",
        "value": 26117,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Intangibles, neto",
            "value": 26117
          }
        ]
      },
      {
        "name": "INTANGIBLES",
        "value": 26713,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Intangibles, neto",
            "value": 26713
          }
        ]
      },
      {
        "name": "RIGHT_OF_USE_ASSET",
        "value": 3617,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Activos por derecho de uso, neto",
            "value": 3617
          }
        ]
      },
      {
        "name": "RIGHT_OF_USE_ASSET",
        "value": 781,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Activos por derecho de uso, neto",
            "value": 781
          }
        ]
      },
      {
        "name": "ACCOUNTS_PAYABLE",
        "value": 189655,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Cuentas por pagar comerciales y diversas",
            "value": 189655
          }
        ]
      },
      {
        "name": "ACCOUNTS_PAYABLE",
        "value": 227552,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Cuentas por pagar comerciales y diversas",
            "value": 227552
          }
        ]
      },
      {
        "name": "SHORT_TERM_LOANS",
        "value": 458346,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Obligaciones financieras",
            "value": 458346
          }
        ]
      },
      {
        "name": "SHORT_TERM_LOANS",
        "value": 383146,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Obligaciones financieras",
            "value": 383146
          }
        ]
      },
      {
        "name": "RIGHT_OF_USE_LIABILITY",
        "value": 741,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Pasivos por arrendamientos",
            "value": 741
          }
        ]
      },
      {
        "name": "RIGHT_OF_USE_LIABILITY",
        "value": 865,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Pasivos por arrendamientos",
            "value": 865
          }
        ]
      },
      {
        "name": "EXPENSE_PROVISIONS",
        "value": 30006,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Provisiones",
            "value": 30006
          }
        ]
      },
      {
        "name": "EXPENSE_PROVISIONS",
        "value": 45146,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Provisiones",
            "value": 45146
          }
        ]
      },
      {
        "name": "TAX_PAYABLES",
        "value": 8119,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Impuesto a la renta por pagar",
            "value": 8119
          }
        ]
      },
      {
        "name": "TAX_PAYABLES",
        "value": 13787,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Impuesto a la renta por pagar",
            "value": 13787
          }
        ]
      },
      {
        "name": "LONG_TERM_LOANS",
        "value": 1034845,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Obligaciones financieras",
            "value": 1034845
          }
        ]
      },
      {
        "name": "LONG_TERM_LOANS",
        "value": 1189880,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Obligaciones financieras",
            "value": 1189880
          }
        ]
      },
      {
        "name": "NC_RIGHT_OF_USE_LIABILITY",
        "value": 2997,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Pasivos por arrendamientos",
            "value": 2997
          }
        ]
      },
      {
        "name": "NC_RIGHT_OF_USE_LIABILITY",
        "value": 60,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Pasivos por arrendamientos",
            "value": 60
          }
        ]
      },
      {
        "name": "NON_CURRENT_EXPENSE_PROVISIONS",
        "value": 26591,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Provisiones",
            "value": 26591
          }
        ]
      },
      {
        "name": "NON_CURRENT_EXPENSE_PROVISIONS",
        "value": 25191,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Provisiones",
            "value": 25191
          }
        ]
      },
      {
        "name": "DEFERRED_TAX_LIABILITY",
        "value": 107614,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Pasivo por impuesto a la renta diferido",
            "value": 107614
          }
        ]
      },
      {
        "name": "DEFERRED_TAX_LIABILITY",
        "value": 110175,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Pasivo por impuesto a la renta diferido",
            "value": 110175
          }
        ]
      },
      {
        "name": "CAPITAL",
        "value": 342889,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Capital",
            "value": 423868
          },
          {
            "name": "Acciones de inversión",
            "value": 40279
          },
          {
            "name": "Acciones de inversión en tesorería",
            "value": -121258
          }
        ]
      },
      {
        "name": "CAPITAL",
        "value": 342889,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Capital",
            "value": 423868
          },
          {
            "name": "Acciones de inversión",
            "value": 40279
          },
          {
            "name": "Acciones de inversión en tesorería",
            "value": -121258
          }
        ]
      },
      {
        "name": "ADDITIONAL_CAPITAL",
        "value": 432779,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Capital adicional",
            "value": 432779
          }
        ]
      },
      {
        "name": "ADDITIONAL_CAPITAL",
        "value": 432779,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Capital adicional",
            "value": 432779
          }
        ]
      },
      {
        "name": "RESERVES",
        "value": 168636,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Reserva legal",
            "value": 168636
          }
        ]
      },
      {
        "name": "RESERVES",
        "value": 168636,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Reserva legal",
            "value": 168636
          }
        ]
      },
      {
        "name": "OTHER_EQUITY_ACCOUNTS",
        "value": -16551,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Otros resultados integrales acumulados",
            "value": -16551
          }
        ]
      },
      {
        "name": "OTHER_EQUITY_ACCOUNTS",
        "value": -16290,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Otros resultados integrales acumulados",
            "value": -16290
          }
        ]
      },
      {
        "name": "ACCUMULATED_RESULTS",
        "value": 285345,
        "year": "2024",
        "period": "2024",
        "details": [
          {
            "name": "Resultados acumulados",
            "value": 285345
          }
        ]
      },
      {
        "name": "ACCUMULATED_RESULTS",
        "value": 261994,
        "year": "2023",
        "period": "2023",
        "details": [
          {
            "name": "Resultados acumulados",
            "value": 261994
          }
        ]
      }
    ],
    "statement_id": "9bac3281-254f-4af8-884a-a1d71108e57f"
  }
]
    
result = lambda_handler(event, None)
print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
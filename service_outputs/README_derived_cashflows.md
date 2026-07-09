# Derived Cashflows — API Reference

Derived cashflows son métricas de flujo de caja definidas **por evaluador** usando el mismo lenguaje DSL de outputs. Los resultados calculados se almacenan por financial statement.

---

## Endpoints

### 1. GET Definiciones del evaluador autenticado

```
GET /derived-cashflows
Authorization: Bearer <token>
```

Retorna la lista de derived cashflows definidos para el evaluador del usuario autenticado.
El `evaluator_id` se extrae automáticamente del JWT — no hace falta enviarlo.

**Response 200**
```json
{
  "success": true,
  "code": "FETCH_DERIVED_CASHFLOWS_SUCCESS",
  "data": [
    {
      "id": "uuid",
      "evaluator_id": "uuid",
      "name": "FCO Ajustado",
      "script": "SUM(tag='operating') - SUM(tag='capex')",
      "format": "currency",
      "category": "Flujo Operativo",
      "priority": 1,
      "description": "Flujo de caja operativo ajustado por capex",
      "created_at": "2025-01-01T00:00:00",
      "updated_at": "2025-01-01T00:00:00"
    }
  ],
  "count": 1
}
```

---

### 2. GET Resultados calculados por business

```
GET /businesses/{business_id}/derived-cashflows
Authorization: Bearer <token>
```

Retorna los resultados calculados para el financial statement OFICIAL del business.
El `evaluator_id` se extrae del JWT — no hace falta enviarlo.

**Path params**

| Param | Tipo | Descripción |
|---|---|---|
| `business_id` | UUID | ID del business |

**Query params**

| Param | Tipo | Requerido | Descripción |
|---|---|---|---|
| `category` | string | No | Filtrar por categoría (ej: `"Flujo Operativo"`) |
| `categories` | string[] | No | Múltiples categorías (repetir param) |
| `name` | string | No | Filtrar por nombre exacto |
| `names` | string[] | No | Múltiples nombres |
| `period_type` | string | No | `annual` \| `ltm` \| `monthly_annualized` |
| `period_types` | string[] | No | Múltiples tipos de período |
| `period_identifier` | string | No | Ej: `"2024"`, `"LTM_2024Q1"`, `"MA_2024Q1"` |
| `period_identifiers` | string[] | No | Múltiples identificadores |
| `page` | integer | No | Página (desde 0). Default: `0` |
| `size` | integer | No | Registros por página (1–1000). Default: `100` |

**Response 200**
```json
{
  "success": true,
  "code": "FETCH_CALCULATED_DERIVED_CASHFLOWS_SUCCESS",
  "data": [
    {
      "id": "uuid",
      "derived_cashflow_id": "uuid",
      "financial_statement_id": "uuid",
      "value": 1234567.89,
      "year": 2024,
      "period_type": "annual",
      "period_identifier": "2024",
      "dcf_name": "FCO Ajustado",
      "dcf_format": "currency",
      "dcf_category": "Flujo Operativo",
      "dcf_description": "Flujo de caja operativo ajustado por capex",
      "dcf_priority": 1,
      "created_at": "2025-01-01T00:00:00",
      "updated_at": "2025-01-01T00:00:00"
    }
  ],
  "count": 1
}
```

---

### 3. POST Recalcular derived cashflows de un business

```
POST /businesses/{business_id}/derived-cashflows/recalculate
Authorization: Bearer <token>
```

Recalcula **manualmente** todos los derived cashflows (annual + LTM + monthly annualized) del financial statement OFICIAL del business. Útil cuando un trigger automático falla o se necesita forzar un recálculo.

El `evaluator_id` se extrae del JWT — no hace falta enviarlo.

**Path params**

| Param | Tipo | Descripción |
|---|---|---|
| `business_id` | UUID | ID del business |

**Request body**: No requiere body.

**Response 200**
```json
{
  "success": true,
  "code": "RECALCULATE_DERIVED_CASHFLOWS_COMPLETED",
  "message": "Recálculo de derived cashflows completado para business 4effc18a-...",
  "statement_id": "0d4634c3-3eda-4e64-bdf0-6584316ddf3a",
  "results": {
    "annual": { "success": true },
    "ltm": { "success": true },
    "monthly_annualized": { "success": false, "error": "Sin monthly_annualized_composition..." }
  }
}
```

> **Nota**: `success` a nivel raíz es `true` solo si **todos** los tipos de cálculo fueron exitosos. Si alguno falla (ej. no hay datos LTM), se reporta el error en `results` pero no se interrumpe el resto.

---

## Trigger de cálculo (backend — SQS)

El cálculo se dispara enviando un mensaje a la cola SQS `SQS_SERVICE_OUTPUTS_CALCULATE_DERIVED_CASHFLOWS_NAME`.

**Payload del mensaje SQS**
```json
{
  "statement_id": "uuid-del-financial-statement",
  "evaluator_id": "uuid-del-evaluador"
}
```

Se recalculan **todos los períodos** del statement para todas las definiciones del evaluador:
- **Annual**: todos los años presentes en los datapoints
- **LTM**: si el statement tiene `ltm_composition` configurado
- **Monthly annualized**: si el statement tiene `monthly_annualized_composition` configurado

Los registros se guardan con upsert (no duplica, actualiza si ya existe). LTM y monthly annualized son non-blocking — si no hay datos suficientes, se omiten sin fallar.

---

## Campos de respuesta — detalle

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | ID del resultado calculado |
| `derived_cashflow_id` | UUID | ID de la definición |
| `financial_statement_id` | UUID | Statement del que provienen los datos |
| `value` | float \| null | Resultado numérico. `null` si el script no pudo calcularse |
| `year` | integer | Año del período |
| `period_type` | string | Tipo de período: `annual` \| `ltm` \| `monthly_annualized` |
| `period_identifier` | string | Identificador textual del período (ej: `"2024"`) |
| `dcf_name` | string | Nombre de la definición (del join con `derived_cashflows`) |
| `dcf_format` | string | Formato (`currency`, `percentage`, etc.) |
| `dcf_category` | string | Categoría de la definición |
| `dcf_description` | string \| null | Descripción opcional |
| `dcf_priority` | integer \| null | Prioridad de orden |

---

## Ordenamiento de resultados

Los resultados vienen ordenados por:
1. `period_type`: ltm → annual → monthly_annualized
2. `period_identifier` DESC
3. `year` DESC
4. `dcf_priority` ASC
5. `dcf_category` ASC
6. `dcf_name` ASC

# service_outputs — API Reference

Servicio de cálculo y consulta de **outputs financieros** calculados a partir de los datapoints de un financial statement.

---

## Índice

1. [Conceptos clave](#1-conceptos-clave)
2. [Endpoints HTTP](#2-endpoints-http)
   - [GET /businesses/{business_id}/outputs](#get-businessesbusiness_idoutputs)
   - [GET /outputs](#get-outputs)
   - [POST /businesses/{business_id}/outputs/recalculate](#post-businessesbusiness_idoutputsrecalculate)
3. [Tipos de período (`period_type`)](#3-tipos-de-período-period_type)
4. [Lógica LTM](#4-lógica-ltm)
5. [Lógica Monthly Annualized](#5-lógica-monthly-annualized)
6. [Formato de respuesta](#6-formato-de-respuesta)
7. [Códigos de error](#7-códigos-de-error)

---

## 1. Conceptos clave

| Término | Descripción |
|---|---|
| **Output** | Métrica financiera definida con un nombre, categoría, formato y fórmula (`script`). Ejemplos: `ebitda_margin`, `debt_to_ebitda`. |
| **Calculated Output** | Resultado de aplicar la fórmula de un Output a los datapoints de un financial statement, para un período específico. |
| **period_type** | Tipo de período del calculated output: `annual`, `quarterly`, `ltm`, `monthly_annualized`. |
| **period_identifier** | Identificador único del período calculado. Ver tabla en sección 3. |
| **is_covenant_metric** | `true` si el output es una métrica clave de covenant (ej. EBITDA, deuda, márgenes). |
| **evaluator_id** | UUID del evaluador propietario del output. `null` = output global (legacy). Los outputs se filtran automáticamente por el evaluador del usuario autenticado. |

---

## 2. Endpoints HTTP

### GET /businesses/{business_id}/outputs

Retorna los **calculated outputs** del financial statement OFICIAL del negocio.

**Autenticación:** Bearer token Cognito (rol mínimo: `ANALYST`)

**Multi-tenancy:** Los calculated outputs se filtran automáticamente por el evaluador del business (vía JOIN `outputs.evaluator_id`). El evaluador del usuario autenticado también se aplica al catálogo que se usa en los cálculos asíncronos.

#### Path parameters

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `business_id` | UUID | Sí | ID del negocio |

#### Query parameters

| Parámetro | Tipo | Descripción |
|---|---|---|
| `period_type` | string | Filtrar por un tipo de período: `annual`, `quarterly`, `ltm`, `monthly_annualized` |
| `period_types` | string[] | Filtrar por múltiples tipos de período (multi-value) |
| `period_identifier` | string | Filtrar por un identificador específico, ej: `LTM_2024Q4`, `MA_2025M9`, `2024` |
| `period_identifiers` | string[] | Filtrar por múltiples identificadores (multi-value) |
| `output_name` | string | Filtrar por nombre de output, ej: `ebitda_margin` |
| `output_names` | string[] | Filtrar por múltiples nombres (multi-value) |
| `output_category` | string | Filtrar por categoría de output |
| `output_categories` | string[] | Filtrar por múltiples categorías (multi-value) |
| `year` | integer | Filtrar por año (solo aplica a `period_type=annual`) |
| `years` | integer[] | Filtrar por múltiples años (multi-value) |
| `covenant_only` | boolean | Si `true`, retorna solo métricas de covenant (`is_covenant_metric=true`) |
| `page` | integer | Página (desde 0). Default: `0` |
| `size` | integer | Tamaño de página (1–1000). Default: `100` |
| `all` | boolean | Si `true`, ignora paginación y retorna todos los resultados |

#### Ejemplos de request

```
# Todos los outputs del negocio (paginado)
GET /businesses/4effc18a-8f29-4cc5-8539-c9f993dbefcb/outputs

# Solo outputs LTM
GET /businesses/4effc18a.../outputs?period_type=ltm

# Solo outputs Monthly Annualized
GET /businesses/4effc18a.../outputs?period_type=monthly_annualized

# LTM + Annual juntos
GET /businesses/4effc18a.../outputs?period_types=ltm&period_types=annual

# Un período LTM específico
GET /businesses/4effc18a.../outputs?period_identifier=LTM_2024Q4

# Solo métricas covenant, todos los tipos de período
GET /businesses/4effc18a.../outputs?covenant_only=true&all=true

# Outputs anuales de 2023 y 2024
GET /businesses/4effc18a.../outputs?years=2023&years=2024&period_type=annual
```

#### Respuesta exitosa `200`

```json
{
  "success": true,
  "code": "FETCH_CALCULATED_OUTPUTS_SUCCESS",
  "message": "Calculated outputs del Business {business_id} obtenidos correctamente",
  "data": [ /* array de CalculatedOutput */ ],
  "count": 42,
  "filters": { /* filtros aplicados */ }
}
```

---

### GET /outputs

Retorna el catálogo de **outputs disponibles** (definiciones de métricas).

**Autenticación:** Bearer token Cognito (rol mínimo: `ANALYST`)

**Multi-tenancy:** Los outputs se filtran automáticamente por el evaluador del usuario autenticado (claim `custom:evaluator_id` o `evaluator_id` del JWT). No se requiere pasar ningún parámetro adicional.

#### Query parameters

| Parámetro | Tipo | Descripción |
|---|---|---|
| `category` | string | Filtrar por categoría |

#### Respuesta exitosa `200`

```json
{
  "success": true,
  "code": "FETCH_OUTPUTS_SUCCESS",
  "message": "Outputs obtenidos correctamente. Con 35 outputs totales",
  "data": [ /* array de Output */ ],
  "count": 35
}
```

---

### POST /businesses/{business_id}/outputs/recalculate

Recalcula **manualmente** todos los outputs (annual + LTM + monthly annualized) del financial statement OFICIAL del negocio. Útil cuando un trigger automático falla o se necesita forzar un recálculo.

**Autenticación:** Bearer token Cognito (rol mínimo: `ANALYST`)

#### Path parameters

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `business_id` | UUID | Sí | ID del negocio |

#### Request body

No requiere body. Solo el path parameter.

#### Ejemplo de request

```
POST /businesses/4effc18a-8f29-4cc5-8539-c9f993dbefcb/outputs/recalculate
Authorization: Bearer <token>
```

#### Respuesta exitosa `200`

```json
{
  "success": true,
  "code": "RECALCULATE_OUTPUTS_COMPLETED",
  "message": "Recálculo de outputs completado para business 4effc18a-...",
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

## 3. Tipos de período (`period_type`)

| `period_type` | Descripción | Ejemplo `period_identifier` |
|---|---|---|
| `annual` | Año completo | `"2023"`, `"2024"` |
| `quarterly` | Trimestre | `"2024Q1"`, `"2024Q3"` |
| `ltm` | Last Twelve Months | `"LTM_2024Q4"`, `"LTM_2024Q3"` |
| `monthly_annualized` | Mejor período mensual anualizado | `"MA_2025M9"`, `"MA_2025M6"` |

### Cómo interpretar `period_identifier`

- **Annual**: el año como string → `"2024"`
- **Quarterly**: año + Q + número → `"2024Q2"`
- **LTM**: prefijo `LTM_` + título del período → `"LTM_2024Q4"` (4 trimestres consecutivos terminando en Q4 2024)
- **Monthly Annualized**: prefijo `MA_` + título del período → `"MA_2025M9"` (12 meses consecutivos terminando en septiembre 2025; o la mejor secuencia disponible si no hay 12 meses completos)

---

## 4. Lógica LTM

El LTM (*Last Twelve Months*) se calcula automáticamente cuando el financial statement OFICIAL tiene `ltm_composition` definido.

- **Trigger**: al confirmar un draft con datos trimestrales, el backend calcula la mejor composición de 4 trimestres consecutivos.
- **Composición**: array de `{ period, positive }` — cada período se suma (`positive: true`) o resta (`positive: false`) según la fórmula.
- **P&L**: se aplica la composición (suma/resta de períodos).
- **BS (Balance Sheet)**: se usa solo el período más reciente de la composición (snapshot, no flujo).
- **`year`**: siempre `null` en LTM (no tiene un año único).

**Ejemplo de `ltm_composition`**:
```json
[
  { "period": "2024Q1", "positive": true },
  { "period": "2024Q2", "positive": true },
  { "period": "2024Q3", "positive": true },
  { "period": "2024Q4", "positive": true }
]
```
→ `period_identifier = "LTM_2024Q4"`, `ltm_title = "2024Q4"`

**Ejemplo con sustitución anual**:
```json
[
  { "period": "2023",   "positive": true },
  { "period": "2024Q1", "positive": false },
  { "period": "2024Q2", "positive": false },
  { "period": "2024Q3", "positive": false },
  { "period": "2024Q4", "positive": true }
]
```
→ Año 2023 completo, minus los 3 primeros trimestres, plus Q4.

---

## 5. Lógica Monthly Annualized

El Monthly Annualized se calcula automáticamente cuando el financial statement OFICIAL tiene `monthly_annualized_composition` definido.

- **Trigger**: al confirmar un draft con datos mensuales, el backend calcula la mejor secuencia de meses consecutivos (objetivo: 12 meses).
- **Factor de anualización**: `12 / n_meses`. Si hay 9 meses disponibles, `factor = 12/9 ≈ 1.333`.
- **P&L**: se aplica la composición + el factor de anualización a cada datapoint de flujo.
- **BS**: se usa solo el período más reciente de la composición (sin factor de anualización).
- **`year`**: siempre `null` (no tiene un año único).

**Ejemplo de `monthly_annualized_composition`** (9 meses acumulados):
```json
[
  { "period": "2025M9A", "positive": true }
]
```
→ Cubre meses 1–9 de 2025. Factor = `12/9 ≈ 1.333`. `period_identifier = "MA_2025M9"`.

**Ejemplo con combinación**:
```json
[
  { "period": "2025Q3A", "positive": true },
  { "period": "2025Q4",  "positive": true }
]
```
→ Q3A = meses 1–9, Q4 = meses 10–12 → 12 meses completos. Factor = `12/12 = 1.0`. `period_identifier = "MA_2025M12"`.

> **Nota**: el título `monthly_annualized_title` no lleva sufijo "A". Siempre tiene el formato `{año}M{mes}`, ej. `"2025M9"`.

---

## 6. Formato de respuesta

### CalculatedOutput (objeto en `data[]`)

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | ID del calculated output |
| `output_id` | UUID | ID del output (métrica) asociado |
| `output_name` | string | Nombre de la métrica, ej. `"ebitda_margin"` |
| `output_category` | string | Categoría, ej. `"profitability"` |
| `output_format` | string | Formato de visualización, ej. `"percentage"`, `"currency"` |
| `output_description` | string | Descripción de la métrica |
| `value` | float \| null | Valor calculado. `null` si el cálculo falló |
| `year` | integer \| null | Año (solo para `annual` y `quarterly`). `null` para `ltm` y `monthly_annualized` |
| `period_type` | string | `"annual"` \| `"quarterly"` \| `"ltm"` \| `"monthly_annualized"` |
| `period_identifier` | string | Identificador del período, ej. `"LTM_2024Q4"`, `"MA_2025M9"`, `"2024"` |
| `is_covenant_metric` | boolean | `true` si es métrica clave de covenant |
| `financial_statement_id` | UUID | ID del financial statement OFICIAL |
| `created_at` | datetime | Fecha de creación |
| `updated_at` | datetime | Fecha de última actualización |

### Output (objeto en `data[]` del catálogo)

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | ID del output |
| `name` | string | Nombre único de la métrica |
| `script` | string | Fórmula DSL para calcular el valor |
| `format` | string | Formato de visualización |
| `category` | string | Categoría de la métrica |
| `description` | string | Descripción |
| `evaluator_id` | UUID \| null | Evaluador propietario del output. `null` = output global (legacy) |
| `created_at` | datetime | Fecha de creación |
| `updated_at` | datetime | Fecha de actualización |

---

## 7. Códigos de error

| HTTP | `code` | Causa |
|---|---|---|
| `400` | `BAD_REQUEST` | Falta `business_id`, parámetro inválido |
| `401` | `UNAUTHORIZED` | Token ausente o inválido |
| `403` | `FORBIDDEN` | Rol insuficiente (requiere mínimo `ANALYST`) |
| `404` | `NOT_FOUND` | No existe financial statement OFICIAL para ese `business_id` |
| `500` | `INTERNAL_SERVER_ERROR` | Error inesperado del servidor |

---

## Notas de integración

### Multi-tenancy por evaluador

- Los outputs son **propiedad de un evaluador** (`evaluator_id` en la tabla `outputs`). Cada evaluador define su propio catálogo de métricas.
- **`GET /outputs`**: devuelve solo los outputs del evaluador del usuario autenticado (claim `custom:evaluator_id` o `evaluator_id` del JWT). Si el usuario no tiene evaluador, devuelve todos.
- **`GET /businesses/{id}/outputs`**: filtra los calculated outputs via JOIN (`outputs.evaluator_id`), usando el evaluador del usuario del JWT.
- **Cálculos asíncronos** (`calculate_outputs`, `calculate_ltm_outputs`, `calculate_monthly_annualized_outputs`): solo calculan con los outputs del evaluador asociado al business (lookup `business.evaluator_id`).
- **Outputs con `evaluator_id = null`**: son outputs globales legacy y **no** se retornan cuando hay un filtro por evaluador activo.
- **Migration**: `002_outputs_per_evaluator.sql` — agrega columna `evaluator_id UUID REFERENCES evaluators(id)` (nullable) a la tabla `outputs`.

### Cuentas y catálogo (`account_extracts`)

- Los **cálculos** (fórmulas DSL) usan metadata del **catálogo maestro** `account_extracts`: `name`, `type`, `tags`, `value_type`. Es el mismo vocabulario que la extracción por IA y `subir_bd`.
- En `financial_datapoints` se guardan `account_extract_id` (identidad del catálogo / upsert) y `account_id` (cuenta del evaluador vía `match_account_extracts`).
- El JOIN de lectura usa `COALESCE(account_extract_id, account_id)` para filas legacy.

### Configuración del evaluador (`financial_statement_configs`)

- `show_ltm`: si es `false`, no se calculan outputs LTM.
- `show_annualized`: si es `false`, no se calculan outputs `monthly_annualized`.
- Si `show_ltm=true` pero no hay 4 trimestres consecutivos (o datos LTM insuficientes), LTM se omite con log explícito.
- Si `show_annualized=true` y existe un tramo parcial al final (ej. un solo trimestre), se anualiza ese tramo y se calculan outputs `MA_*`.
- LTM y anualizado se recomputan desde los **períodos reales** en el statement OFICIAL (no solo metadata guardada al confirmar).

### Tipos de período en cálculos asíncronos

| `period_type` | Cuándo se calcula |
|---|---|
| `annual` | Períodos puros `YYYY` en datapoints (ej. `2024`). Si no hay, el lambda anual termina sin error. |
| `ltm` | `show_ltm=true` y composición LTM válida (4 trimestres consecutivos). |
| `monthly_annualized` | `show_annualized=true` y tramo parcial anualizable (último período incompleto). |

### ¿Cuándo aparecen outputs de tipo `ltm` o `monthly_annualized`?

- Aparecen según datos del OFFICIAL **y** la config del evaluador (`show_ltm`, `show_annualized`). Si el negocio solo tiene años completos (`2023`, `2024`), solo habrá `period_type=annual` además de LTM/MA si aplican.
- El cálculo es **asíncrono**: se dispara automáticamente al confirmar un draft. No se deben pedir outputs LTM/monthly inmediatamente después de una confirmación — esperar la notificación de procesamiento o hacer polling.

### Flujo típico en el frontend

1. Obtener todos los outputs del negocio: `GET /businesses/{id}/outputs?all=true`
2. Agrupar por `period_type` para mostrar secciones (Anual / LTM / Monthly Annualized).
3. Para el dashboard de covenants: `?covenant_only=true&period_type=ltm`
4. Para comparar períodos: `?period_identifiers=LTM_2024Q4&period_identifiers=2024&period_identifiers=2023`

### Multi-value query strings

Para enviar arrays usar el mismo parámetro varias veces:
```
?period_types=annual&period_types=ltm&years=2023&years=2024
```

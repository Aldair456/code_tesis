-- =============================================================================
-- Migration: Derived Cashflows
-- Tabla de resultados calculados para derived_cashflows (por evaluador)
-- =============================================================================


CREATE TABLE IF NOT EXISTS derived_cashflows
(
    id            uuid      default uuid_generate_v4() not null primary key,
    evaluator_id  uuid      not null references evaluators,
    name          varchar   not null,
    script        varchar   not null,
    format        varchar   not null,
    category      varchar   not null,
    priority      integer   not null default 0,
    created_at    timestamp default CURRENT_TIMESTAMP,
    updated_at    timestamp default CURRENT_TIMESTAMP,
    description   text
);


CREATE TABLE IF NOT EXISTS calculated_derived_cashflows
(
    id                      uuid        DEFAULT uuid_generate_v4() NOT NULL PRIMARY KEY,
    derived_cashflow_id     uuid        NOT NULL REFERENCES derived_cashflows (id),
    financial_statement_id  uuid        NOT NULL REFERENCES financial_statements (id),
    value                   float,
    year                    integer,
    period_type             varchar     NOT NULL DEFAULT 'annual',
    period_identifier       varchar,
    created_at              timestamp   DEFAULT CURRENT_TIMESTAMP,
    updated_at              timestamp   DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_calculated_derived_cashflow
        UNIQUE (derived_cashflow_id, financial_statement_id, period_type, period_identifier)
);

CREATE INDEX IF NOT EXISTS idx_calc_dcf_statement
    ON calculated_derived_cashflows (financial_statement_id);

CREATE INDEX IF NOT EXISTS idx_calc_dcf_derived
    ON calculated_derived_cashflows (derived_cashflow_id);

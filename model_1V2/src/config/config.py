import os


# S3
S3_BUCKET = os.environ.get("S3_BUCKET")
FINANCIAL_STATEMENTS_PREFIX = os.environ.get(
    "FINANCIAL_STATEMENTS_PREFIX", "FinancialStatements/"
)
FINANCIAL_STATEMENT_JSON_PREFIX = os.environ.get(
    "FINANCIAL_STATEMENT_JSON_PREFIX", "FinancialStatementsReducto/"
)

# Reducto
REDUCTO_API_KEY = os.environ.get("REDUCTO_API_KEY")
REDUCTO_PIPELINE_ID = os.environ.get("REDUCTO_PIPELINE_ID")


SQS_INIT_JOB_FIFO_URL = os.environ.get("SQS_INIT_JOB_FIFO_URL", "")


# MessageGroupId obligatorio en FIFO; mismo criterio que otros flujos (ej. financial_statements)
SQS_INIT_JOB_MESSAGE_GROUP_ID = os.environ.get(
    "SQS_INIT_JOB_MESSAGE_GROUP_ID", "financial_statements_reducto"
)

# Step Functions (model_1V2 extractor orchestration)
# `.strip()` evita que un ARN con whitespace (por ejemplo al pegarlo) haga que falle el check de "no configurado".
MODEL2_IA_DEV_EXTRACTOR_STATE_MACHINE_ARN = os.environ.get("MODEL2_IA_DEV_EXTRACTOR_STATE_MACHINE_ARN")

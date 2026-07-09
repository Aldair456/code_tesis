import os

# --- Análisis IA (negocio, sector, financiero, etc.) ---
ANALYZE_CORIL_API_KEY = os.getenv("ANALYZE_CORIL_API_KEY")
ANALYZE_CORIL_MODEL = os.getenv("ANALYZE_CORIL_MODEL")
ANALYZE_CORIL_MAX_TOKENS = int(os.getenv("ANALYZE_CORIL_MAX_TOKENS", "4000"))
ANALYZE_CORIL_TEMPERATURE = float(os.getenv("ANALYZE_CORIL_TEMPERATURE", "0.3"))

# --- AWS / S3 ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET")

QUEUE_URL_CREDIT_MEMO_ANALYSIS_CM = os.getenv("QUEUE_URL_CREDIT_MEMO_ANALYSIS_CM")
QUEUE_URL_INTERBANK_COMPANY_PROFILE_MEMO = os.getenv("QUEUE_URL_INTERBANK_COMPANY_PROFILE_MEMO")
# --- AppSync (notificaciones de estado) ---
APPSYNC_ENDPOINT = os.getenv("APPSYNC_ENDPOINT")
APPSYNC_API_KEY = os.getenv("APPSYNC_API_KEY")

# Mutaciones GraphQL usadas por appsync_statu
APPSYNC_MUTATION_PUBLISH_STATUS = """
    mutation PublishStatus($status: String!, $message: String, $credit_memo_id: String, $deleted_ids: [String], $created_proposal: String) {
        publishStatus(status: $status, message: $message, credit_memo_id: $credit_memo_id, deleted_ids: $deleted_ids, created_proposal: $created_proposal) {
            status
            message
            credit_memo_id
            deleted_ids
            created_proposal
        }
    }
"""

APPSYNC_MUTATION_PUBLISH_FINANCIAL_ANALYSIS = """
    mutation PublishFinancialAnalysis($business_id: String!, $result: FinancialAnalysisResponseInput!) {
        publishFinancialAnalysis(business_id: $business_id, result: $result) {
            success
            message
            request_id
            data {
                business_id
                analysis {
                    rentabilidad {
                        contenido
                        caracteres
                    }
                    generacion_caja {
                        contenido
                        caracteres
                    }
                }
                metadata {
                    analizado_por
                    request_id
                    servicio {
                        model
                        max_tokens
                        temperature
                        is_available
                        repository_available
                    }
                }
            }
        }
    }
"""

# --- SQS / Step Functions (análisis financiero asíncrono) ---
FINANCIAL_ANALYSIS_QUEUE_URL = os.getenv("FINANCIAL_ANALYSIS_QUEUE_URL")
# Cola GC (CreditProposalAnalysisOrchestration). Sin default: debe estar en env (dev/prod) para que GC no use dev por defecto.
CREDIT_PROPOSAL_ANALYSIS_QUEUE_URL = os.getenv("CREDIT_PROPOSAL_ANALYSIS_QUEUE_URL")
BUSINESS_MEMO_STATE_MACHINE_ARN = os.getenv("BUSINESS_MEMO_STATE_MACHINE_ARN")
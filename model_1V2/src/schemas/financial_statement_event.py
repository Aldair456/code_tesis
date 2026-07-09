from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class FinancialStatementIdEvent:
    financial_statement_id: str


def parse_financial_statement_id_sqs_event(event: Dict[str, Any]) -> List[FinancialStatementIdEvent]:
    records = event.get("Records") or []
    if not records:
        raise ValueError("No se recibieron Records (SQS)")

    parsed: List[FinancialStatementIdEvent] = []
    for r in records:
        body = r.get("body")
        if body is None:
            raise ValueError("Record SQS sin body")
        # body puede ser str JSON o dict (en tests)
        if isinstance(body, str):
            import json

            payload = json.loads(body)
        elif isinstance(body, dict):
            payload = body
        else:
            raise ValueError(f"body inválido en SQS: {type(body)}")

        fsid = (
            (payload.get("financial_statement_id") or payload.get("statement_id") or payload.get("id") or "")
            .strip()
        )
        if not fsid:
            raise ValueError("Falta financial_statement_id en body SQS")
        parsed.append(FinancialStatementIdEvent(financial_statement_id=fsid))

    return parsed


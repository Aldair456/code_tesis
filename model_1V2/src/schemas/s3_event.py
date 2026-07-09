import json
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class S3PdfRecord:
    bucket: str
    key: str
    statement_id: str
    output_key: str


def _extract_statement_id_from_key(key: str) -> str:
    filename = key.split("/")[-1]
    return filename.rsplit(".", 1)[0]


def _normalize_s3_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza el evento para soportar triggers directos S3 y via SNS.
    - S3 directo:  record.eventSource = "aws:s3"  (minúscula)
    - Via SNS:     record.EventSource = "aws:sns"  (mayúscula)
                   El evento S3 real viene serializado en record["Sns"]["Message"]
    
    Returns:
        Evento normalizado con Records S3 directos.
    """
    records = event.get("Records", [])
    if not records:
        return event

    if records[0].get("EventSource") == "aws:sns":
        s3_records = []
        for record in records:
            sns_message = json.loads(record["Sns"]["Message"])
            s3_records.extend(sns_message.get("Records", []))
        return {"Records": s3_records}

    return event


def parse_s3_pdf_records(
    event: Dict[str, Any],
    *,
    input_prefix: str,
    output_prefix: str,
) -> List[S3PdfRecord]:
    """
    Parsea records S3 de un evento, soportando tanto S3 directo como via SNS.
    
    Args:
        event: Evento Lambda (puede ser S3 directo o SNS wrapping S3)
        input_prefix: Prefijo para filtrar keys de entrada
        output_prefix: Prefijo para construir keys de salida
    
    Returns:
        Lista de S3PdfRecord parseados
    """
    normalized_event = _normalize_s3_event(event)
    records: List[Dict[str, Any]] = normalized_event.get("Records") or []
    if not records:
        raise ValueError("No se recibieron Records en el evento S3")

    input_prefix = (input_prefix or "").strip()
    output_prefix = (output_prefix or "").strip()
    if output_prefix and not output_prefix.endswith("/"):
        output_prefix = f"{output_prefix}/"

    parsed: List[S3PdfRecord] = []
    for record in records:
        if record.get("eventSource") != "aws:s3":
            continue

        s3_info = record.get("s3") or {}
        bucket = (s3_info.get("bucket") or {}).get("name") or ""
        key = (s3_info.get("object") or {}).get("key") or ""
        key = urllib.parse.unquote_plus(key)

        if not bucket or not key:
            raise ValueError("No se pudo extraer bucket o key del evento S3")

        if input_prefix and not key.startswith(input_prefix):
            continue

        statement_id = _extract_statement_id_from_key(key)
        if not statement_id:
            raise ValueError(f"No se pudo extraer statement_id de key: {key}")

        output_key = f"{output_prefix}{statement_id}.json"
        parsed.append(
            S3PdfRecord(
                bucket=bucket,
                key=key,
                statement_id=statement_id,
                output_key=output_key,
            )
        )

    return parsed


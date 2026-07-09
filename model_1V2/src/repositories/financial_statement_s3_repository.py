import json
import os
from typing import Any, Dict, Optional

import boto3


class FinancialStatementS3Repository:
    def __init__(self, bucket: str = "") -> None:
        self._bucket = bucket or os.environ.get("S3_BUCKET", "")
        self._region = os.environ.get("AWS_REGION", "us-east-1")

    def _client(self):
        return boto3.client("s3", region_name=self._region)

    def get_pdf_bytes(self, key: str, bucket: Optional[str] = None) -> bytes:
        b = bucket or self._bucket
        if not b:
            raise ValueError("S3_BUCKET no configurado")
        obj = self._client().get_object(Bucket=b, Key=key)
        return obj["Body"].read()

    def put_json(self, key: str, data: dict, bucket: Optional[str] = None) -> None:
        b = bucket or self._bucket
        if not b:
            raise ValueError("S3_BUCKET no configurado")
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self._client().put_object(
            Bucket=b,
            Key=key,
            Body=body,
            ContentType="application/json; charset=utf-8",
        )

    def get_json(self, key: str, bucket: Optional[str] = None) -> Dict[str, Any]:
        b = bucket or self._bucket
        if not b:
            raise ValueError("S3_BUCKET no configurado")
        obj = self._client().get_object(Bucket=b, Key=key)
        raw = obj["Body"].read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"JSON en s3://{b}/{key} no es un objeto dict")
        return data


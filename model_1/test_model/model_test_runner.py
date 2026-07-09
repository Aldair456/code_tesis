"""
Model Test Runner - Framework de testing para modelos de procesamiento de documentos
"""

import json
import time
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


@dataclass
class TestCase:
    name: str
    input_s3_key: str
    expected_output_path: str
    output_s3_key_txt: Optional[str] = None
    output_s3_key_json: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.output_s3_key_txt or not self.output_s3_key_json:
            base_name = self.input_s3_key.rsplit('.', 1)[0]
            if not self.output_s3_key_txt:
                self.output_s3_key_txt = f"{base_name}_output.txt"
            if not self.output_s3_key_json:
                self.output_s3_key_json = f"{base_name}_output.json"


@dataclass
class ComparisonResult:
    field_name: str
    expected_value: Any
    actual_value: Any
    match: bool
    difference_type: Optional[str] = None
    difference: Optional[Any] = None
    difference_percent: Optional[float] = None


@dataclass
class TestResult:
    test_case: TestCase
    job_id: str
    status: JobStatus
    duration_seconds: float
    started_at: datetime
    completed_at: Optional[datetime]
    comparison_results: List[ComparisonResult] = field(default_factory=list)
    actual_output: Optional[Dict] = None
    expected_output: Optional[Dict] = None
    error_message: Optional[str] = None
    job_response: Optional[Dict] = None

    @property
    def passed(self) -> bool:
        if self.status != JobStatus.COMPLETED:
            return False
        if not self.comparison_results:
            return True
        return all(r.match for r in self.comparison_results)

    @property
    def match_percentage(self) -> float:
        if not self.comparison_results:
            return 100.0
        matches = sum(1 for r in self.comparison_results if r.match)
        return (matches / len(self.comparison_results)) * 100


class ModelTestRunner:

    def __init__(
            self,
            s3_client: Any,
            sqs_client: Any,
            job_api_base_url: str,
            user_config: Dict[str, Any],
            input_bucket: Optional[str] = None,
            output_bucket: Optional[str] = None,
            poll_interval_seconds: int = 5,
            max_wait_seconds: int = 300,
            comparison_fields: Optional[List[str]] = None,
            auth_token: Optional[str] = None
    ):
        self.s3 = s3_client
        self.sqs = sqs_client
        self.job_api_base_url = job_api_base_url.rstrip('/')
        self.user_config = user_config
        self.input_bucket = input_bucket
        self.output_bucket = output_bucket
        self.poll_interval = poll_interval_seconds
        self.max_wait = max_wait_seconds
        self.auth_token = auth_token
        self.comparison_fields = comparison_fields or ["name", "value", "period"]

        logger.info(f"ModelTestRunner inicializado")
        logger.info(f"  - API Base URL: {self.job_api_base_url}")
        logger.info(f"  - Campos de comparación: {self.comparison_fields}")

    def add_comparison_field(self, field_name: str) -> None:
        if field_name not in self.comparison_fields:
            self.comparison_fields.append(field_name)
            logger.info(f"Campo '{field_name}' añadido a comparación")

    def remove_comparison_field(self, field_name: str) -> None:
        if field_name in self.comparison_fields:
            self.comparison_fields.remove(field_name)
            logger.info(f"Campo '{field_name}' removido de comparación")

    def send_to_queue(self, test_case: TestCase) -> str:
        job_id = str(uuid.uuid4())

        message = {
            "object_key": test_case.input_s3_key,
            "object_key_txt_output": test_case.output_s3_key_txt,
            "object_key_json_output": test_case.output_s3_key_json,
            "job_id": job_id,
            "is_not_created": True,
            **test_case.metadata
        }

        logger.info(f"Enviando a cola: {test_case.name} (job_id: {job_id})")

        response = self.sqs.send_json_message(
            data=message,
            message_group_id=f"test-{job_id}" if self.sqs.is_fifo else None
        )

        logger.info(f"Mensaje enviado. MessageId: {response.get('MessageId')}")
        return job_id

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        url = f"{self.job_api_base_url}/jobs/{job_id}"

        headers = {"Content-Type": "application/json"}

        if self.auth_token:
            headers["x-api-key"] = f"{self.auth_token}"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error consultando job {job_id}: {e}")
            raise

    def wait_for_job_completion(
            self,
            job_id: str,
            callback: Optional[Callable[[str, Dict], None]] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        last_status = None

        while True:
            elapsed = time.time() - start_time

            if elapsed > self.max_wait:
                logger.warning(f"Timeout esperando job {job_id}")
                return {
                    "status": "TIMEOUT",
                    "error_message": f"Timeout después de {self.max_wait}s"
                }

            try:
                response = self.get_job_status(job_id)
                data = response.get("data", {})
                status = data.get("status", "UNKNOWN")

                if status != last_status:
                    logger.info(f"Job {job_id}: {status} (elapsed: {elapsed:.1f}s)")
                    last_status = status

                if callback:
                    callback(job_id, response)

                if status in ["COMPLETED", "FAILED"]:
                    return response

            except Exception as e:
                logger.warning(f"Error en polling (reintentando): {e}")

            time.sleep(self.poll_interval)

    def download_result(self, s3_key: str) -> Optional[Dict]:
        try:
            content = self.s3.get_json(s3_key, bucket=self.output_bucket)
            logger.info(f"Resultado descargado: {s3_key}")
            return content
        except Exception as e:
            logger.error(f"Error descargando {s3_key}: {e}")
            return None

    def load_expected_output(self, path: str) -> Optional[Dict]:
        try:
            if path.startswith("s3://"):
                parts = path[5:].split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
                return self.s3.get_json(key, bucket=bucket)
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando expected output {path}: {e}")
            return None

    def compare_results(
            self,
            expected: List[Dict],
            actual: List[Dict],
            fields: Optional[List[str]] = None
    ) -> List[ComparisonResult]:
        fields = fields or self.comparison_fields
        results = []

        expected_index = {}
        for item in expected:
            key = (item.get("name"), item.get("period"))
            expected_index[key] = item

        actual_index = {}
        for item in actual:
            key = (item.get("name"), item.get("period"))
            actual_index[key] = item

        all_keys = set(expected_index.keys()) | set(actual_index.keys())

        for key in all_keys:
            exp_item = expected_index.get(key)
            act_item = actual_index.get(key)

            name, period = key

            if not exp_item:
                results.append(ComparisonResult(
                    field_name=f"{name}|{period}",
                    expected_value=None,
                    actual_value=act_item,
                    match=False,
                    difference_type="EXTRA_IN_ACTUAL",
                    difference=None
                ))
                continue

            if not act_item:
                results.append(ComparisonResult(
                    field_name=f"{name}|{period}",
                    expected_value=exp_item,
                    actual_value=None,
                    match=False,
                    difference_type="MISSING_IN_ACTUAL",
                    difference=None
                ))
                continue

            for field in fields:
                exp_val = exp_item.get(field)
                act_val = act_item.get(field)

                match = exp_val == act_val
                diff = None
                diff_percent = None
                diff_type = None

                if not match:
                    diff_type = "VALUE_MISMATCH"
                    if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
                        diff = act_val - exp_val
                        if exp_val != 0:
                            diff_percent = (diff / abs(exp_val)) * 100
                    else:
                        diff = f"expected: {exp_val}, actual: {act_val}"

                results.append(ComparisonResult(
                    field_name=f"{name}|{period}|{field}",
                    expected_value=exp_val,
                    actual_value=act_val,
                    match=match,
                    difference_type=diff_type,
                    difference=diff,
                    difference_percent=diff_percent
                ))

        return results

    def run_single_test(self, test_case: TestCase) -> TestResult:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Ejecutando test: {test_case.name}")
        logger.info(f"{'=' * 60}")

        started_at = datetime.now()

        try:
            job_id = self.send_to_queue(test_case)
            job_response = self.wait_for_job_completion(job_id)
            completed_at = datetime.now()

            job_data = job_response.get("data", {})
            status_str = job_data.get("status", "UNKNOWN")

            try:
                status = JobStatus(status_str)
            except ValueError:
                status = JobStatus.FAILED

            duration = (completed_at - started_at).total_seconds()

            comparison_results = []
            actual_output = None
            expected_output = None

            if status == JobStatus.COMPLETED:
                output_key = test_case.output_s3_key_json
                actual_data = self.download_result(output_key)

                if actual_data:
                    actual_output = actual_data
                    actual_items = actual_data.get("data", actual_data)
                    if isinstance(actual_items, dict):
                        actual_items = actual_items.get("data", [])

                    expected_data = self.load_expected_output(test_case.expected_output_path)
                    if expected_data:
                        expected_output = expected_data
                        expected_items = expected_data if isinstance(expected_data, list) else expected_data.get("data",
                                                                                                                 [])
                        comparison_results = self.compare_results(expected_items, actual_items)

            return TestResult(
                test_case=test_case,
                job_id=job_id,
                status=status,
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at,
                comparison_results=comparison_results,
                actual_output=actual_output,
                expected_output=expected_output,
                error_message=job_data.get("error_message"),
                job_response=job_response
            )

        except Exception as e:
            logger.error(f"Error ejecutando test {test_case.name}: {e}")
            return TestResult(
                test_case=test_case,
                job_id="",
                status=JobStatus.FAILED,
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(),
                error_message=str(e)
            )

    def run_tests(self, test_cases: List[TestCase], parallel: bool = False) -> List[TestResult]:
        logger.info(f"\n{'#' * 60}")
        logger.info(f"Iniciando suite de tests: {len(test_cases)} casos")
        logger.info(f"{'#' * 60}\n")

        results = []

        for i, tc in enumerate(test_cases, 1):
            logger.info(f"\n[{i}/{len(test_cases)}] {tc.name}")
            result = self.run_single_test(tc)
            results.append(result)

            status_emoji = "✅" if result.passed else "❌"
            logger.info(f"{status_emoji} {tc.name}: {result.status.value} ({result.match_percentage:.1f}% match)")

        return results

    def generate_report(self, results: List[TestResult], output_path: str, format: str = "json") -> str:
        if format == "markdown":
            return self._generate_markdown_report(results, output_path)
        else:
            return self._generate_json_report(results, output_path)

    def _generate_json_report(self, results: List[TestResult], output_path: str) -> str:
        report = {
            "summary": {
                "total_tests": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
                "pass_rate": f"{(sum(1 for r in results if r.passed) / len(results) * 100):.1f}%" if results else "N/A",
                "total_duration_seconds": sum(r.duration_seconds for r in results),
                "generated_at": datetime.now().isoformat(),
                "comparison_fields": self.comparison_fields
            },
            "tests": []
        }

        for result in results:
            test_report = {
                "name": result.test_case.name,
                "job_id": result.job_id,
                "status": result.status.value,
                "passed": result.passed,
                "match_percentage": result.match_percentage,
                "duration_seconds": result.duration_seconds,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "error_message": result.error_message,
                "input_file": result.test_case.input_s3_key,
                "output_file": result.test_case.output_s3_key_json,
                "comparison_summary": {
                    "total_comparisons": len(result.comparison_results),
                    "matches": sum(1 for c in result.comparison_results if c.match),
                    "mismatches": sum(1 for c in result.comparison_results if not c.match)
                },
                "mismatches": [
                    {
                        "field": c.field_name,
                        "expected": c.expected_value,
                        "actual": c.actual_value,
                        "difference_type": c.difference_type,
                        "difference": c.difference,
                        "difference_percent": c.difference_percent
                    }
                    for c in result.comparison_results if not c.match
                ]
            }
            report["tests"].append(test_report)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Reporte JSON generado: {output_path}")
        return output_path

    def _generate_markdown_report(self, results: List[TestResult], output_path: str) -> str:
        lines = [
            "# Reporte de Tests - Model Processing",
            "",
            f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Resumen",
            "",
            "| Métrica | Valor |",
            "|---------|-------|",
            f"| Total Tests | {len(results)} |",
            f"| Pasados | {sum(1 for r in results if r.passed)} |",
            f"| Fallados | {sum(1 for r in results if not r.passed)} |",
            f"| Tasa de éxito | {(sum(1 for r in results if r.passed) / len(results) * 100):.1f}% |" if results else "| Tasa de éxito | N/A |",
            f"| Duración total | {sum(r.duration_seconds for r in results):.1f}s |",
            f"| Campos comparados | {', '.join(self.comparison_fields)} |",
            "",
            "---",
            "",
            "## Detalle por Test",
            ""
        ]

        for i, result in enumerate(results, 1):
            status_emoji = "PASS" if result.passed else "FAIL"

            lines.extend([
                f"### {i}. [{status_emoji}] {result.test_case.name}",
                "",
                f"- **Job ID:** `{result.job_id}`",
                f"- **Estado:** {result.status.value}",
                f"- **Duración:** {result.duration_seconds:.1f}s",
                f"- **Match:** {result.match_percentage:.1f}%",
                f"- **Input:** `{result.test_case.input_s3_key}`",
                f"- **Output:** `{result.test_case.output_s3_key_json}`",
                ""
            ])

            if result.error_message:
                lines.extend([
                    "**Error:**",
                    "```",
                    result.error_message,
                    "```",
                    ""
                ])

            mismatches = [c for c in result.comparison_results if not c.match]
            if mismatches:
                lines.extend([
                    "**Diferencias encontradas:**",
                    "",
                    "| Campo | Esperado | Actual | Tipo de Diferencia |Diferencia |",
                    "|-------|----------|--------|--------------------|-----------|"
                ])

                for m in mismatches[:20]:
                    diff_str = ""
                    if m.difference_percent is not None:
                        diff_str = f"{m.difference:+.2f} ({m.difference_percent:+.1f}%)"
                    elif m.difference:
                        diff_str = str(m.difference)[:50]

                    lines.append(f"| {m.field_name} | {m.expected_value} | {m.actual_value} | {m.difference_type} | {diff_str} |")

                if len(mismatches) > 20:
                    lines.append(f"| ... | {len(mismatches) - 20} más | ... | ... |")

                lines.append("")

            lines.extend(["---", ""])

        content = "\n".join(lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Reporte Markdown generado: {output_path}")
        return output_path


def create_test_case(name: str, input_key: str, expected_file: str, **kwargs) -> TestCase:
    return TestCase(
        name=name,
        input_s3_key=input_key,
        expected_output_path=expected_file,
        **kwargs
    )


def load_test_cases_from_json(config_path: str) -> List[TestCase]:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return [TestCase(**tc) for tc in config.get("tests", [])]


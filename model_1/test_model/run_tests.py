#!/usr/bin/env python3
"""
Script de Ejecución de Tests
Uso:
    python run_tests.py
    python run_tests.py --config test_config.json
    python run_tests.py --dry-run
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from common_aws_clients.sqs_client import SQSClient
from common_aws_clients.s3_client import S3Client

from model_test_runner import (
    ModelTestRunner,
    TestCase,
    create_test_case,
    load_test_cases_from_json
)


# Importar tus clientes
# from s3_client import S3Client
# from sqs_client import SQSClient


class Config:
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    INPUT_BUCKET = os.environ.get("INPUT_BUCKET", "mi-bucket-financiero-dev2")
    OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "mi-bucket-financiero-dev2")
    SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/051826715282/model1_init_job.fifo")
    JOB_API_BASE_URL = os.environ.get("JOB_API_BASE_URL", "https://r0zevnf2j8.execute-api.us-east-1.amazonaws.com/dev/api/v1/models")
    AUTH_TOKEN = os.environ.get("API_AUTH_TOKEN", "QCwLdSfyHO2R1TyOZtPEHaRJDMvT8bXS9tXFpdkx")

    USER_CONFIG = {
        "roles": ["ADMIN"],
        "evaluator_id": os.environ.get("EVALUATOR_ID", "9ca49e78-dec4-4046-a48a-8fc661110b28")
    }

    POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
    MAX_WAIT = int(os.environ.get("MAX_WAIT", "300"))
    COMPARISON_FIELDS = ["name", "value", "period"]

    REPORTS_DIR = Path("./reports")
    EXPECTED_DIR = Path("./expected_outputs")


def get_default_test_cases() -> list:
    return [
        TestCase(
            name="Test Trimestral - test4.png",
            input_s3_key="trimestrales/test4.png",
            expected_output_path=str(Config.EXPECTED_DIR / "test4_expected.json"),
            output_s3_key_txt="trimestrales/test4_output.txt",
            output_s3_key_json="trimestrales/test4_output.json",
            metadata={"type": "BS", "periodicity_type": "anual"}
        ),
        # TestCase(
        #     name="Test Trimestral - test4.png",
        #     input_s3_key="trimestrales/test4.png",
        #     expected_output_path=str(Config.EXPECTED_DIR / "test4_expected.json"),
        #     output_s3_key_txt="trimestrales/test4_output.txt",
        #     output_s3_key_json="trimestrales/test4_output.json",
        #     metadata={"type": "BS", "periodicity_type": "anual"}
        # )

    ]


def create_runner():
    # Descomentar e importar tus clientes
    # from s3_client import S3Client
    # from sqs_client import SQSClient

    s3_client = S3Client(bucket_name=Config.INPUT_BUCKET, region_name=Config.AWS_REGION)
    sqs_client = SQSClient(queue_url=Config.SQS_QUEUE_URL, region_name=Config.AWS_REGION)

    return ModelTestRunner(
        s3_client=s3_client,
        sqs_client=sqs_client,
        job_api_base_url=Config.JOB_API_BASE_URL,
        user_config=Config.USER_CONFIG,
        input_bucket=Config.INPUT_BUCKET,
        output_bucket=Config.OUTPUT_BUCKET,
        poll_interval_seconds=Config.POLL_INTERVAL,
        max_wait_seconds=Config.MAX_WAIT,
        comparison_fields=Config.COMPARISON_FIELDS,
        auth_token=Config.AUTH_TOKEN
    )

    raise NotImplementedError("Descomentar código y configurar clientes S3/SQS")


def run_tests(runner, test_cases, output_prefix="test_run"):
    print(f"\nEjecutando {len(test_cases)} test(s)...\n")

    results = runner.run_tests(test_cases)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    Config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_json = Config.REPORTS_DIR / f"{output_prefix}_{timestamp}.json"
    report_md = Config.REPORTS_DIR / f"{output_prefix}_{timestamp}.md"

    runner.generate_report(results, str(report_json), format="json")
    runner.generate_report(results, str(report_md), format="markdown")

    return results, {"json": report_json, "markdown": report_md}


def print_summary(results, report_paths):
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    total_duration = sum(r.duration_seconds for r in results)

    print("\n" + "=" * 70)
    print("RESUMEN DE EJECUCIÓN")
    print("=" * 70)
    print(f"\n  Total tests:     {len(results)}")
    print(f"  Pasados:         {passed}")
    print(f"  Fallados:        {failed}")
    print(f"  Tasa de éxito:   {(passed / len(results) * 100):.1f}%")
    print(f"  Duración total:  {total_duration:.1f}s")

    print(f"\nReportes generados:")
    print(f"  JSON:     {report_paths['json']}")
    print(f"  Markdown: {report_paths['markdown']}")

    if failed > 0:
        print(f"\nTests fallidos:")
        for r in results:
            if not r.passed:
                print(f"  - {r.test_case.name}")
                if r.error_message:
                    print(f"    Error: {r.error_message}")

    print("\n" + "=" * 70)
    return 0 if failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Ejecutar tests del modelo")
    parser.add_argument("--config", "-c", help="Archivo JSON de configuración")
    parser.add_argument("--test-name", "-t", help="Ejecutar solo este test")
    parser.add_argument("--output-prefix", "-o", default="test_run", help="Prefijo para reportes")
    parser.add_argument("--add-field", "-f", action="append", help="Agregar campo de comparación")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar tests")

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("MODEL TEST RUNNER")
    print("=" * 70)

    Config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    Config.EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    if args.config:
        print(f"\nCargando tests desde: {args.config}")
        test_cases = load_test_cases_from_json(args.config)
    else:
        print("\nUsando tests por defecto")
        test_cases = get_default_test_cases()

    if args.test_name:
        test_cases = [tc for tc in test_cases if args.test_name in tc.name]
        if not test_cases:
            print(f"No se encontró test: {args.test_name}")
            return 1

    print(f"   Encontrados {len(test_cases)} test(s)")

    if args.dry_run:
        print("\nDRY RUN - Tests que se ejecutarían:")
        for i, tc in enumerate(test_cases, 1):
            print(f"   {i}. {tc.name}")
            print(f"      Input:    {tc.input_s3_key}")
            print(f"      Expected: {tc.expected_output_path}")
        return 0

    try:
        runner = create_runner()
    except NotImplementedError as e:
        print(f"\nError: {e}")
        print("Configura los clientes S3/SQS en la función create_runner()")
        return 1

    if args.add_field:
        for field in args.add_field:
            runner.add_comparison_field(field)
            print(f"   + Campo agregado: {field}")

    results, report_paths = run_tests(runner, test_cases, args.output_prefix)
    return print_summary(results, report_paths)


if __name__ == "__main__":
    sys.exit(main())
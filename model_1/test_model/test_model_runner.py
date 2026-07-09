"""
Test Unitarios para ModelTestRunner
Ejecutar con: pytest test_model_runner.py -v
"""

import pytest
import json
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

from model_test_runner import (
    ModelTestRunner,
    TestCase,
    TestResult,
    ComparisonResult,
    JobStatus,
    create_test_case,
    load_test_cases_from_json
)


@pytest.fixture
def mock_s3_client():
    client = Mock()
    client.get_json = Mock(return_value=None)
    client.get_text = Mock(return_value="")
    return client


@pytest.fixture
def mock_sqs_client():
    client = Mock()
    client.is_fifo = False
    client.send_json_message = Mock(return_value={"MessageId": "test-msg-123"})
    return client


@pytest.fixture
def runner(mock_s3_client, mock_sqs_client):
    return ModelTestRunner(
        s3_client=mock_s3_client,
        sqs_client=mock_sqs_client,
        job_api_base_url="https://api.test.com",
        user_config={"roles": ["ADMIN"], "evaluator_id": "test-123"},
        poll_interval_seconds=1,
        max_wait_seconds=10
    )


@pytest.fixture
def sample_expected_data():
    return [
        {"name": "SALES", "value": 1275355, "period": "2023", "year": 2023},
        {"name": "SALES", "value": 1365057, "period": "2022", "year": 2022},
        {"name": "COGS", "value": -797078, "period": "2023", "year": 2023},
        {"name": "COGS", "value": -929479, "period": "2022", "year": 2022},
    ]


@pytest.fixture
def sample_actual_data():
    return [
        {"name": "SALES", "value": 1275355, "period": "2023", "year": 2023},
        {"name": "SALES", "value": 1365000, "period": "2022", "year": 2022},
        {"name": "COGS", "value": -797078, "period": "2023", "year": 2023},
        {"name": "COGS", "value": -929479, "period": "2022", "year": 2022},
    ]


@pytest.fixture
def sample_test_case():
    return TestCase(
        name="Test SALES",
        input_s3_key="test/input.pdf",
        expected_output_path="./expected/test.json"
    )


class TestComparison:

    def test_compare_exact_match(self, runner, sample_expected_data):
        results = runner.compare_results(sample_expected_data, sample_expected_data.copy())
        assert all(r.match for r in results)
        assert len(results) > 0

    def test_compare_with_differences(self, runner, sample_expected_data, sample_actual_data):
        results = runner.compare_results(sample_expected_data, sample_actual_data)
        mismatches = [r for r in results if not r.match]
        assert len(mismatches) > 0

        sales_2022_mismatch = next(
            (r for r in mismatches if "SALES|2022|value" in r.field_name), None
        )
        assert sales_2022_mismatch is not None
        assert sales_2022_mismatch.expected_value == 1365057
        assert sales_2022_mismatch.actual_value == 1365000

    def test_compare_missing_item(self, runner, sample_expected_data):
        actual = sample_expected_data[:-1]
        results = runner.compare_results(sample_expected_data, actual)
        missing = [r for r in results if r.difference == "MISSING_IN_ACTUAL"]
        assert len(missing) > 0

    def test_compare_extra_item(self, runner, sample_expected_data):
        actual = sample_expected_data + [{"name": "EXTRA", "value": 999, "period": "2023"}]
        results = runner.compare_results(sample_expected_data, actual)
        extra = [r for r in results if r.difference == "EXTRA_IN_ACTUAL"]
        assert len(extra) > 0

    def test_compare_with_custom_fields(self, runner, sample_expected_data):
        runner.add_comparison_field("year")
        results = runner.compare_results(sample_expected_data, sample_expected_data.copy())
        year_comparisons = [r for r in results if "year" in r.field_name]
        assert len(year_comparisons) > 0


class TestReports:

    def test_generate_json_report(self, runner, sample_test_case):
        result = TestResult(
            test_case=sample_test_case,
            job_id="test-job-123",
            status=JobStatus.COMPLETED,
            duration_seconds=10.5,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            comparison_results=[
                ComparisonResult("SALES|2023|value", 100, 100, True),
                ComparisonResult("SALES|2022|value", 200, 190, False, -10, -5.0),
            ]
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        runner.generate_report([result], output_path, format="json")

        with open(output_path, 'r') as f:
            report = json.load(f)

        assert "summary" in report
        assert "tests" in report
        assert report["summary"]["total_tests"] == 1
        assert report["tests"][0]["job_id"] == "test-job-123"

    def test_generate_markdown_report(self, runner, sample_test_case):
        result = TestResult(
            test_case=sample_test_case,
            job_id="test-job-456",
            status=JobStatus.COMPLETED,
            duration_seconds=15.0,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            comparison_results=[]
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_path = f.name

        runner.generate_report([result], output_path, format="markdown")

        with open(output_path, 'r') as f:
            content = f.read()

        assert "Reporte de Tests" in content
        assert "test-job-456" in content


class TestUtilities:

    def test_create_test_case(self):
        tc = create_test_case(
            name="My Test",
            input_key="folder/file.pdf",
            expected_file="./expected.json"
        )

        assert tc.name == "My Test"
        assert tc.input_s3_key == "folder/file.pdf"
        assert tc.expected_output_path == "./expected.json"
        assert tc.output_s3_key_txt == "folder/file_output.txt"
        assert tc.output_s3_key_json == "folder/file_output.json"

    def test_load_test_cases_from_json(self):
        config = {
            "tests": [
                {"name": "Test 1", "input_s3_key": "test1.pdf", "expected_output_path": "./expected1.json"},
                {"name": "Test 2", "input_s3_key": "test2.pdf", "expected_output_path": "./expected2.json"}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            config_path = f.name

        test_cases = load_test_cases_from_json(config_path)

        assert len(test_cases) == 2
        assert test_cases[0].name == "Test 1"
        assert test_cases[1].name == "Test 2"

    def test_add_remove_comparison_field(self, runner):
        runner.add_comparison_field("year")
        assert "year" in runner.comparison_fields

        runner.add_comparison_field("year")
        assert runner.comparison_fields.count("year") == 1

        runner.remove_comparison_field("year")
        assert "year" not in runner.comparison_fields


class TestIntegration:

    def test_send_to_queue(self, runner, sample_test_case):
        job_id = runner.send_to_queue(sample_test_case)
        runner.sqs.send_json_message.assert_called_once()
        assert len(job_id) == 36

    @patch('requests.get')
    def test_get_job_status(self, mock_get, runner):
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "data": {"id": "test-123", "status": "COMPLETED"}
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = runner.get_job_status("test-123")
        assert result["data"]["status"] == "COMPLETED"

    @patch('requests.get')
    def test_wait_for_job_completion_success(self, mock_get, runner):
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "data": {"status": "COMPLETED"}}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = runner.wait_for_job_completion("test-123")
        assert result["data"]["status"] == "COMPLETED"

    @patch('requests.get')
    def test_wait_for_job_timeout(self, mock_get, runner):
        runner.max_wait = 2
        runner.poll_interval = 1

        mock_response = Mock()
        mock_response.json.return_value = {"data": {"status": "PROCESSING"}}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = runner.wait_for_job_completion("test-123")
        assert result["status"] == "TIMEOUT"


class TestTestResult:

    def test_passed_when_all_match(self, sample_test_case):
        result = TestResult(
            test_case=sample_test_case,
            job_id="test-123",
            status=JobStatus.COMPLETED,
            duration_seconds=10,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            comparison_results=[
                ComparisonResult("f1", 1, 1, True),
                ComparisonResult("f2", 2, 2, True),
            ]
        )
        assert result.passed is True
        assert result.match_percentage == 100.0

    def test_failed_when_mismatch(self, sample_test_case):
        result = TestResult(
            test_case=sample_test_case,
            job_id="test-123",
            status=JobStatus.COMPLETED,
            duration_seconds=10,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            comparison_results=[
                ComparisonResult("f1", 1, 1, True),
                ComparisonResult("f2", 2, 3, False),
            ]
        )
        assert result.passed is False
        assert result.match_percentage == 50.0

    def test_failed_when_job_failed(self, sample_test_case):
        result = TestResult(
            test_case=sample_test_case,
            job_id="test-123",
            status=JobStatus.FAILED,
            duration_seconds=10,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            comparison_results=[],
            error_message="Job failed"
        )
        assert result.passed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
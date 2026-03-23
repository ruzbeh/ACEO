"""FastAPI application for the testing framework with bug detection capabilities."""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import time
import asyncio
import logging
import os
from uuid import uuid4

from models import (
    RunTestRequest, RunTestResponse, TestResults, TestDiscoveryResult,
    TestConfig, OutputFormat
)
from test_runner import TestRunner
from config_manager import ConfigManager
from test_reporter import TestReporter

# Bug detection imports
from bug_detection.bug_detector import BugDetector, create_default_detector, create_detector_with_config
from bug_detection.models import DetectorConfig, BugFinding, BugReport, FixSuggestion, Severity
from bug_detection.fix_suggestion_engine import FixSuggestionEngine
from bug_detection.api_models import (
    AnalysisRequest, AnalysisResponse, FileAnalysisRequest, FileAnalysisResponse,
    AnalysisResultsResponse, DetectorsResponse, FixSuggestionRequest, FixSuggestionResponse,
    ProgressResponse, ErrorResponse, HealthResponse, AnalysisStatus,
    convert_detector_config_from_dict, convert_bug_report_to_response,
    create_detector_info_list, estimate_analysis_time, create_error_response
)

# Persistence imports
import db
import analysis_store

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the FastAPI app
app = FastAPI(
    title="Testing Framework API with Bug Detection",
    description="A comprehensive testing framework with integrated bug detection capabilities",
    version="1.0.0"
)

# Initialize core components
config_manager = ConfigManager()
test_runner = TestRunner(config_manager)

# Initialize bug detection components
bug_detector = create_default_detector()
fix_suggestion_engine = FixSuggestionEngine()

# In-memory task tracking for transient run state (started/processing only)
analysis_tasks: Dict[str, Dict[str, Any]] = {}

# Prompt injection markers that must be rejected in user-supplied context
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "forget previous instructions",
    "you are now",
    "override instructions",
]


def _check_api_key(x_api_key: Optional[str]) -> None:
    """Validate X-API-Key header against API_KEY env var. Raises 401 if invalid."""
    expected = os.environ.get("API_KEY", "")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing API key")


def _sanitize_context(context: Optional[str]) -> Optional[str]:
    """Sanitize optional context: strip whitespace, truncate to 500 chars, reject injection attempts.

    Raises:
        HTTPException 422: if context contains a prompt injection marker.
    """
    if context is None:
        return None
    ctx = context.strip()[:500]
    if any(pat in ctx.lower() for pat in _INJECTION_PATTERNS):
        raise HTTPException(status_code=422, detail="Context contains disallowed content")
    return ctx


def _confidence_label(confidence) -> str:
    """Map a Confidence enum value (or string) to a lowercase response label."""
    val = confidence if isinstance(confidence, str) else confidence.value
    if val == "HIGH":
        return "high"
    if val == "MEDIUM":
        return "medium"
    return "low"


# Background task for running analysis
async def run_analysis_task(
    analysis_id: str,
    directory: str,
    analysis_types: List[str],
    detector_config: Optional[DetectorConfig] = None
):
    """Background task to run bug analysis."""
    try:
        logger.info(f"Starting background analysis {analysis_id}")

        # Update task status
        analysis_tasks[analysis_id] = {
            "status": AnalysisStatus.PROCESSING,
            "start_time": time.time()
        }

        # Configure detector if config provided
        if detector_config:
            bug_detector.configure_detectors(detector_config)

        # Run analysis
        report = bug_detector.analyze_codebase(directory, analysis_types)

        # Persist to DB
        analysis_store.save_run(report, directory, analysis_types)

        analysis_tasks[analysis_id]["status"] = AnalysisStatus.COMPLETED
        analysis_tasks[analysis_id]["end_time"] = time.time()
        # Keep the analysis_id in analysis_tasks so progress/results endpoints
        # can detect it was completed; DB is the source of truth for the report.

        logger.info(f"Completed background analysis {analysis_id}")

    except Exception as e:
        logger.error(f"Error in background analysis {analysis_id}: {str(e)}")
        analysis_tasks[analysis_id]["status"] = AnalysisStatus.FAILED
        analysis_tasks[analysis_id]["error"] = str(e)
        analysis_tasks[analysis_id]["end_time"] = time.time()


# Testing Framework Endpoints (existing)

@app.post("/api/tests/run", response_model=RunTestResponse)
async def run_tests(request: RunTestRequest) -> RunTestResponse:
    """Execute tests based on provided criteria."""
    try:
        start_time = time.time()

        # Update configuration if provided
        if request.config:
            config_manager.set_config(request.config)

        # Run tests
        results = test_runner.run_tests(request.pattern)

        execution_time = time.time() - start_time

        # Determine overall status
        status = "success" if results.failed == 0 and results.errors == 0 else "failure"

        return RunTestResponse(
            status=status,
            results=results,
            execution_time=f"{execution_time:.2f}s"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")


@app.get("/api/tests/discover")
async def discover_tests() -> Dict[str, List[TestDiscoveryResult]]:
    """Discover available tests in the workspace."""
    try:
        test_cases = test_runner.discover_tests()

        tests = []
        for test_case in test_cases:
            # Extract file name from test name (format: file.py::test_name)
            test_name = test_case.get_name()
            if "::" in test_name:
                file_part, name_part = test_name.split("::", 1)
            else:
                file_part = "unknown"
                name_part = test_name

            tests.append(TestDiscoveryResult(
                name=name_part,
                file=file_part,
                description=getattr(test_case, 'description', '') or ""
            ))

        return {"tests": tests}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test discovery failed: {str(e)}")


@app.get("/api/tests/results/{run_id}")
async def get_test_results(run_id: str) -> Dict[str, Any]:
    """Retrieve results from a previous test run."""
    try:
        results = test_runner.get_test_results(run_id)

        return {
            "run_id": run_id,
            "results": results,
            "timestamp": results.timestamp.isoformat() if results.timestamp else None
        }

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Test results not found for run ID: {run_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve test results: {str(e)}")


@app.get("/api/config")
async def get_config() -> TestConfig:
    """Get current test configuration."""
    return config_manager.get_config()


@app.post("/api/config")
async def update_config(config: TestConfig) -> Dict[str, str]:
    """Update test configuration."""
    try:
        config_manager.set_config(config)
        if config_manager.validate_config():
            return {"status": "success", "message": "Configuration updated"}
        else:
            raise HTTPException(status_code=400, detail="Invalid configuration")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


# Bug Detection Endpoints (new)

@app.post("/api/bugs/analyze", response_model=AnalysisResponse)
async def start_bug_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks) -> AnalysisResponse:
    """Start comprehensive bug analysis of the codebase."""
    try:
        # Generate analysis ID
        analysis_id = str(uuid4())

        # Validate directory exists
        if not os.path.exists(request.directory):
            raise HTTPException(status_code=400, detail=f"Directory not found: {request.directory}")

        # Count Python files for time estimation
        python_files = []
        for root, dirs, files in os.walk(request.directory):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__']]
            python_files.extend([f for f in files if f.endswith('.py')])

        # Estimate completion time
        estimated_time = estimate_analysis_time(len(python_files), request.analysis_types)

        # Parse configuration if provided
        detector_config = None
        if request.config:
            try:
                detector_config = convert_detector_config_from_dict(request.config)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")

        # Initialize task tracking
        analysis_tasks[analysis_id] = {
            "status": AnalysisStatus.STARTED,
            "start_time": time.time(),
            "directory": request.directory,
            "analysis_types": request.analysis_types,
            "total_files": len(python_files)
        }

        # Start background analysis
        background_tasks.add_task(
            run_analysis_task,
            analysis_id,
            request.directory,
            request.analysis_types,
            detector_config
        )

        logger.info(f"Started bug analysis {analysis_id} for directory: {request.directory}")

        return AnalysisResponse(
            analysis_id=analysis_id,
            status="started",
            estimated_time=estimated_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting bug analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@app.get("/api/bugs/results/{analysis_id}", response_model=AnalysisResultsResponse)
async def get_bug_analysis_results(analysis_id: str) -> AnalysisResultsResponse:
    """Get bug analysis results."""
    try:
        task_info = analysis_tasks.get(analysis_id)

        # If we have an in-flight task entry, use it to determine status
        if task_info is not None:
            status = task_info["status"]

            if status == AnalysisStatus.FAILED:
                error_msg = task_info.get("error", "Analysis failed with unknown error")
                raise HTTPException(status_code=500, detail=f"Analysis failed: {error_msg}")

            if status == AnalysisStatus.COMPLETED:
                # Fall through to DB lookup below
                pass
            else:
                # Still in progress — return status without report
                from datetime import datetime
                return AnalysisResultsResponse(
                    analysis_id=analysis_id,
                    status=status.value,
                    report=None,
                    timestamp=datetime.now().isoformat()
                )

        # Try to load the completed report from the DB
        report = analysis_store.get_run(analysis_id)
        if report is not None:
            return convert_bug_report_to_response(report, "completed")

        # Not found anywhere
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving analysis results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve results: {str(e)}")


@app.post("/api/bugs/analyze/file", response_model=FileAnalysisResponse)
async def analyze_file(request: FileAnalysisRequest) -> FileAnalysisResponse:
    """Analyze a specific file for bugs."""
    try:
        start_time = time.time()

        # Validate file exists
        if not os.path.isfile(request.file_path):
            raise HTTPException(status_code=400, detail=f"File not found: {request.file_path}")

        # Analyze file
        findings = bug_detector.analyze_file(request.file_path)

        analysis_time = time.time() - start_time

        logger.info(f"Analyzed file {request.file_path} in {analysis_time:.2f}s, found {len(findings)} issues")

        return FileAnalysisResponse(
            file_path=request.file_path,
            findings=findings,
            analysis_time=f"{analysis_time:.2f}s"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing file {request.file_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File analysis failed: {str(e)}")


@app.get("/api/bugs/detectors", response_model=DetectorsResponse)
async def get_available_detectors() -> DetectorsResponse:
    """Get available bug detector configurations."""
    try:
        detectors = create_detector_info_list()
        return DetectorsResponse(detectors=detectors)

    except Exception as e:
        logger.error(f"Error retrieving detector information: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve detectors: {str(e)}")


@app.post("/api/bugs/fix-suggestions", response_model=FixSuggestionResponse)
async def get_fix_suggestions(
    request: FixSuggestionRequest,
    x_api_key: Optional[str] = Header(default=None),
) -> FixSuggestionResponse:
    """Get fix suggestions for specific bug findings."""
    _check_api_key(x_api_key)

    if not bug_detector.config.include_suggestions:
        raise HTTPException(status_code=403, detail="Fix suggestions are disabled by configuration")

    try:
        # Look up the finding directly from the DB
        finding = analysis_store.find_finding(request.finding_id)

        if not finding:
            raise HTTPException(status_code=404, detail=f"Bug finding not found: {request.finding_id}")

        # Sanitize context: strip whitespace, truncate, reject injection attempts
        sanitized_context = _sanitize_context(request.context)

        # Generate fix suggestion using FixSuggestionEngine
        suggestion = fix_suggestion_engine.generate(finding, sanitized_context)

        overall_confidence = _confidence_label(suggestion.confidence)

        logger.info(f"Generated fix suggestion for finding {request.finding_id}")

        return FixSuggestionResponse(
            suggestions=[suggestion],
            confidence=overall_confidence
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Fix suggestion service unavailable: {str(e)}")
        raise HTTPException(status_code=503, detail="Fix suggestion service unavailable: missing API key")
    except Exception as e:
        logger.error(f"Error generating fix suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")


@app.post("/api/findings/{id}/fix-suggestions", response_model=FixSuggestionResponse)
async def get_fix_suggestions_by_finding_id(
    id: str,
    request: Optional[FixSuggestionRequest] = None,
    x_api_key: Optional[str] = Header(default=None),
) -> FixSuggestionResponse:
    """Get fix suggestions for a finding by path parameter (RESTful alias)."""
    _check_api_key(x_api_key)

    if not bug_detector.config.include_suggestions:
        raise HTTPException(status_code=403, detail="Fix suggestions are disabled by configuration")

    try:
        finding = analysis_store.find_finding(id)

        if not finding:
            raise HTTPException(status_code=404, detail=f"Bug finding not found: {id}")

        context = request.context if request else None
        sanitized_context = _sanitize_context(context)

        suggestion = fix_suggestion_engine.generate(finding, sanitized_context)

        overall_confidence = _confidence_label(suggestion.confidence)

        logger.info(f"Generated fix suggestion for finding {id}")

        return FixSuggestionResponse(
            suggestions=[suggestion],
            confidence=overall_confidence
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Fix suggestion service unavailable: {str(e)}")
        raise HTTPException(status_code=503, detail="Fix suggestion service unavailable: missing API key")
    except Exception as e:
        logger.error(f"Error generating fix suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")


@app.get("/api/bugs/history")
async def get_bug_history(
    file_path: Optional[str] = None,
    limit: int = 50,
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Return a paginated list of past analysis runs, newest first.

    Requires a valid X-API-Key header matching the API_KEY environment variable.
    """
    _check_api_key(x_api_key)
    try:
        runs = analysis_store.list_runs(file_path=file_path, limit=limit)
        return {"runs": runs, "total": len(runs)}
    except Exception as e:
        logger.error(f"Error retrieving bug history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")


@app.get("/api/bugs/trends")
async def get_bug_trends(
    file_path: Optional[str] = None,
    category: Optional[str] = None,
    days: int = 30,
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Return bug counts grouped by date and category for trend charts.

    Requires a valid X-API-Key header matching the API_KEY environment variable.
    """
    _check_api_key(x_api_key)
    try:
        trends = analysis_store.get_trends(file_path=file_path, category=category, days=days)
        return {
            "trends": trends,
            "file_path": file_path,
            "category": category,
            "days": days,
        }
    except Exception as e:
        logger.error(f"Error retrieving bug trends: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve trends: {str(e)}")


@app.get("/api/bugs/progress/{analysis_id}", response_model=ProgressResponse)
async def get_analysis_progress(analysis_id: str) -> ProgressResponse:
    """Get progress information for an ongoing analysis."""
    try:
        # Check if analysis exists
        if analysis_id not in analysis_tasks:
            raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")

        # Get progress from bug detector
        progress_info = bug_detector.get_progress(analysis_id)

        if progress_info:
            return ProgressResponse(**progress_info)
        else:
            # Fallback to task info
            task_info = analysis_tasks[analysis_id]
            elapsed_time = time.time() - task_info["start_time"]

            return ProgressResponse(
                analysis_id=analysis_id,
                status=task_info["status"],
                progress_percentage=100.0 if task_info["status"] == AnalysisStatus.COMPLETED else 0.0,
                current_file="",
                total_files=task_info.get("total_files", 0),
                processed_files=task_info.get("total_files", 0) if task_info["status"] == AnalysisStatus.COMPLETED else 0,
                elapsed_time=elapsed_time,
                estimated_remaining_time=0.0,
                errors=[]
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving progress: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve progress: {str(e)}")


# Health and Status Endpoints

@app.get("/api/health")
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    try:
        # Get available detectors
        detector_info = create_detector_info_list()
        available_detectors = [d.name for d in detector_info if d.enabled]

        return HealthResponse(
            status="healthy",
            service="testing-framework-with-bug-detection",
            version="1.0.0",
            detectors_available=available_detectors
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            service="testing-framework-with-bug-detection",
            version="1.0.0",
            detectors_available=[]
        )


@app.get("/api/bugs/health")
async def bug_detection_health() -> Dict[str, Any]:
    """Bug detection specific health check."""
    try:
        # Test basic functionality
        test_config = DetectorConfig()
        test_detector = BugDetector(test_config)

        return {
            "status": "healthy",
            "service": "bug-detection",
            "enabled_detectors": test_config.enabled_detectors,
            "active_analyses": len(analysis_tasks),
        }

    except Exception as e:
        logger.error(f"Bug detection health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "bug-detection",
            "error": str(e)
        }


# Error handlers

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=create_error_response(
            "internal_server_error",
            f"Internal server error: {str(exc)}"
        ).dict()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            "http_error",
            exc.detail
        ).dict()
    )


# Startup and cleanup

@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting Testing Framework API with Bug Detection")

    # Initialize DB schema
    db.init_schema()

    # Schedule cleanup task
    asyncio.create_task(cleanup_old_results())


async def cleanup_old_results():
    """Periodically clean up old in-memory task entries."""
    while True:
        try:
            current_time = time.time()
            cutoff_time = current_time - (24 * 60 * 60)  # 24 hours

            # Clean up old task tracking entries only (results live in DB now)
            expired_tasks = [
                task_id for task_id, task_info in analysis_tasks.items()
                if task_info.get("start_time", current_time) < cutoff_time
            ]

            for task_id in expired_tasks:
                del analysis_tasks[task_id]

            if expired_tasks:
                logger.info(f"Cleaned up {len(expired_tasks)} old task tracking entries")

            # Sleep for 1 hour before next cleanup
            await asyncio.sleep(3600)

        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
            await asyncio.sleep(3600)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

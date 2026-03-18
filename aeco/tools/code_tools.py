from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from aeco.config import settings


async def code_execute(
    code: str, timeout: int = 30, workspace_path: str | None = None
) -> dict:
    """Execute Python code in a subprocess. Used by QA for running tests."""
    ws = workspace_path or settings.workspace_path
    workspace = Path(ws).resolve()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", dir=workspace, delete=False
    ) as f:
        f.write(code)
        script_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "python",
            script_path,
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "status": "ok" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "stdout": stdout.decode()[:5000],
            "stderr": stderr.decode()[:5000],
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"status": "error", "error": f"Execution timed out after {timeout}s"}
    finally:
        Path(script_path).unlink(missing_ok=True)

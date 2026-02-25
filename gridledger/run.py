import subprocess
import sys
from pathlib import Path


def run_pipeline():
    """
    Runs main.py and returns stdout/stderr.
    Designed to be called by OpenClaw.
    """

    project_root = Path(__file__).resolve().parent.parent
    main_script = project_root / "main.py"

    try:
        result = subprocess.run(
            [sys.executable, str(main_script)],
            capture_output=True,
            text=True,
            cwd=project_root
        )

        if result.returncode == 0:
            return result.stdout or "Pipeline completed successfully."
        else:
            return f"Pipeline error:\n{result.stderr}"

    except Exception as e:
        return f"Execution failed: {e}"


if __name__ == "__main__":
    print(run_pipeline())

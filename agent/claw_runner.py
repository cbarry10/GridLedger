import subprocess

def run_pipeline():
    try:
        result = subprocess.run(
            ["python", "main.py"],
            capture_output=True,
            text=True,
            check=True
        )
        return {
            "status": "success",
            "output": result.stdout
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "output": e.stderr
        }

if __name__ == "__main__":
    print(run_pipeline())

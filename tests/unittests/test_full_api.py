import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

def test_imports():
    # Get the current working directory
    cwd = Path(os.getcwd())

    # Define the paths
    api_dir = cwd / "taiservice" / "api"
    LIST_MODULES_TO_COPY_TO_TEMP = [
        Path("/home/ec2-user/tai-service/taiservice/cdk/constructs/customresources/document_db/settings.py"),
        Path("/home/ec2-user/tai-service/taiservice/cdk/constructs/construct_config.py"),
    ]

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        temp_api_dir = temp_dir / "api"


        # Copy the api directory to the temp directory
        shutil.copytree(api_dir, temp_api_dir)
        for module in LIST_MODULES_TO_COPY_TO_TEMP:
            shutil.copy(module, temp_api_dir / module.name)
        # Create a venv in the temp directory
        subprocess.run([sys.executable, '-m', 'venv', str(temp_dir)], check=True)

        # Install the requirements
        subprocess.run([str(temp_dir / 'bin' / 'python'), '-m', 'pip', 'install', '-r', str(temp_api_dir / 'requirements.txt')], check=True)

        # Use subprocess to run each file in the api directory
        for module in temp_api_dir.glob("**/*.py"):
            subprocess.run([str(temp_dir / 'bin' / 'python'), str(module)], check=True)
"""Define tests for the full API."""""
import os
from pathlib import Path
import sys
import subprocess
import shutil
import tempfile
import pytest
from taiservice.cdk.stacks.tai_api_stack import MODULES_TO_COPY_INTO_API_DIR

def test_imports():
    """
    Test that the imports work.

    This is important because there is no way to test the imports in unit tests
    without fully deploying the stack. This test attempts to copy the api
    directory into a temporary directory, create a venv, install the
    requirements, and then execute the api to verify that the imports work.
    """
    cwd = Path(os.getcwd())
    api_dir = cwd / "taiservice" / "api"
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        temp_api_dir = temp_dir / "api"
        shutil.copytree(api_dir, temp_api_dir)
        for module in MODULES_TO_COPY_INTO_API_DIR:
            shutil.copy(module, temp_api_dir / module.name)
        # Create a venv in the temp directory
        subprocess.run([sys.executable, '-m', 'venv', str(temp_dir)], check=True)
        try:
            # Install the requirements
            subprocess.run([str(temp_dir / 'bin' / 'python'), '-m', 'pip', 'install', '-r', str(temp_api_dir / 'requirements.txt')], check=True)
        except subprocess.CalledProcessError:
            pytest.fail("Failed to install requirements in temporary venv.")
        try:
            # Use subprocess to run each file in the api directory
            # run the index.py file (which will subsequently import all the other files)
            subprocess.run([str(temp_dir / 'bin' / 'python'), str(temp_api_dir / 'index.py')], check=True)
        except subprocess.CalledProcessError:
            pytest.fail("Failed to execute index.py in temporary venv. Rerun test in debug mode ot pinpoint the issue.")

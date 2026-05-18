import os

# Required before app imports (main.py calls get_settings at module load).
os.environ.setdefault("API_KEY", "test-api-key-for-pytest-only")

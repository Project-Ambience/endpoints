# tests/conftest.py
import os
# Ensure consumer loops don't start during unit tests
os.environ.setdefault("DISABLE_MQ", "1")


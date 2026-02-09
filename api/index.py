"""Vercel serverless entry point for FastAPI."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fplan_v2.api.main import app

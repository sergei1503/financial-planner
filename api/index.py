"""Vercel serverless entry point wrapping the FastAPI app via Mangum."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mangum import Mangum
from fplan_v2.api.main import app

handler = Mangum(app, lifespan="off")

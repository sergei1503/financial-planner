"""
Error handling utilities for FPlan v2.

This module provides centralized error handling and logging for the financial
planning application. It includes custom exception classes and decorators for
consistent error reporting across the codebase.
"""

import os
import traceback
import logging
from functools import wraps
import sys
from datetime import datetime

# Configure logging — skip file handler on serverless (read-only filesystem)
_handlers = [logging.StreamHandler(sys.stdout)]
if not os.getenv("VERCEL"):
    _handlers.append(logging.FileHandler("financial_planner.log"))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=_handlers,
)

logger = logging.getLogger(__name__)


class FinancialPlannerError(Exception):
    """Base exception class for Financial Planner errors"""

    def __init__(self, message, details=None):
        self.message = message
        self.details = details
        self.timestamp = datetime.now()
        super().__init__(self.message)


def error_handler(func):
    """Decorator for handling errors and providing detailed information"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            exc_type, exc_value, exc_tb = sys.exc_info()
            tb = traceback.extract_tb(exc_tb)

            # Get the most relevant parts of the traceback
            error_location = f"{tb[-1].filename}:{tb[-1].lineno}"
            error_function = tb[-1].name

            # Create detailed error message
            error_details = {
                "error_type": exc_type.__name__,
                "location": error_location,
                "function": error_function,
                "arguments": {"args": str(args), "kwargs": str(kwargs)},
                "traceback": traceback.format_exc(),
            }

            logger.error(f"Error in {error_location} - {error_function}: {str(e)}")
            logger.debug(f"Detailed error information: {error_details}")

            raise FinancialPlannerError(
                f"Error in {error_function} at {error_location}: {str(e)}",
                error_details,
            )

    return wrapper


# Module metadata
__version__ = "2.0.0"
__author__ = "FPlan Development Team"
__description__ = "Error handling utilities for FPlan v2"

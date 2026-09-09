"""CYBERPULSE AI backend package.

Bootstraps the project root onto sys.path so the shared `ml` package
(feature engineering, inference, explainability) is importable.
"""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
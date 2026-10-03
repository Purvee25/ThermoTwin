"""Project data locations, resolved from THERMOTWIN_ROOT (defaults to the working directory).

The package is installed non-editable in Docker, so paths cannot be derived from __file__.
"""

import os
from pathlib import Path

ROOT = Path(os.environ.get("THERMOTWIN_ROOT", Path.cwd()))
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

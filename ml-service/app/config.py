"""
Central configuration for the AI Handwriting Recognition Platform – ML Service.
All parameters can be overridden via environment variables.
"""
import os

import torch

# ── Model (Stage 8) ──────────────────────────────────────────────────────────
# Default to trocr-base on CPU for fast execution (~2-5s), or trocr-large on CUDA GPU.
# Can be explicitly overridden via HTR_MODEL_NAME environment variable.
_default_model = "microsoft/trocr-large-handwritten" if torch.cuda.is_available() else "microsoft/trocr-base-handwritten"
HTR_MODEL_NAME = os.environ.get("HTR_MODEL_NAME", _default_model)

# Local disk cache directory
_folder_name = "trocr_large_handwritten_model" if "large" in HTR_MODEL_NAME.lower() else "trocr_handwritten_model"
LOCAL_MODEL_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", _folder_name)
)

# ── Beam Search Parameters (Stage 8 spec) ────────────────────────────────────
# Use 3 beams on CPU (2x faster than 5 with near-identical accuracy), 5 on GPU
BEAM_NUM_BEAMS            = int(os.environ.get("BEAM_NUM_BEAMS", "3" if not torch.cuda.is_available() else "5"))
BEAM_MAX_NEW_TOKENS       = int(os.environ.get("BEAM_MAX_NEW_TOKENS",       "128"))
BEAM_LENGTH_PENALTY       = float(os.environ.get("BEAM_LENGTH_PENALTY",     "0.8"))
BEAM_REPETITION_PENALTY   = float(os.environ.get("BEAM_REPETITION_PENALTY", "1.2"))
BEAM_NO_REPEAT_NGRAM_SIZE = int(os.environ.get("BEAM_NO_REPEAT_NGRAM_SIZE", "2"))
BEAM_EARLY_STOPPING       = True

# ── Confidence Thresholds (Stage 9) ─────────────────────────────────────────
CONF_ACCEPT      = float(os.environ.get("CONF_ACCEPT",      "0.90"))  # Accept immediately
CONF_RETRY_LIGHT = float(os.environ.get("CONF_RETRY_LIGHT", "0.70"))  # Light retry zone

# ── Quality Classification Thresholds (Stage 1) ──────────────────────────────
QUALITY_EXCELLENT  = 0.85
QUALITY_GOOD       = 0.65
QUALITY_ACCEPTABLE = 0.45
# Below ACCEPTABLE → "Poor"

# ── Detection / Deduplication (Stage 4) ─────────────────────────────────────
IOU_THRESHOLD = float(os.environ.get("IOU_THRESHOLD", "0.5"))

# ── Image Processing ─────────────────────────────────────────────────────────
WORKING_HEIGHT  = int(os.environ.get("WORKING_HEIGHT", "1600"))  # Target resize height
TROCR_TARGET_H  = 64   # Height TrOCR expects (processor resizes internally, but keep close)

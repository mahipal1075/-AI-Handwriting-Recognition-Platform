"""OCR pipeline package — 12-stage V2.0 architecture."""

from app.pipeline.quality_assessment  import assess_quality, QualityResult
from app.pipeline.preprocessing       import preprocess_image, preprocess_cv2_image
from app.pipeline.layout_analysis     import analyze_layout
from app.pipeline.detection           import detect_text_regions
from app.pipeline.region_optimizer    import optimize_region
from app.pipeline.line_segmentation   import segment_lines
from app.pipeline.recognition         import transcribe_patch, load_model
from app.pipeline.postprocessing      import correct_text, correct_spelling
from app.pipeline.text_reconstruction import reconstruct_text

__all__ = [
    "assess_quality", "QualityResult",
    "preprocess_image", "preprocess_cv2_image",
    "analyze_layout",
    "detect_text_regions",
    "optimize_region",
    "segment_lines",
    "transcribe_patch", "load_model",
    "correct_text", "correct_spelling",
    "reconstruct_text",
]

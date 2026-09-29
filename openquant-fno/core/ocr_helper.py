"""
OpenQuant-FNO: Native Apple Vision OCR Helper
==============================================
Fast, local sub-50ms OCR text recognition using macOS Apple Vision framework.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("openquant.ocr")

def extract_text_from_image(image_path: str) -> str:
    """
    Extracts text lines from an image file using native macOS Apple Vision API.
    Returns concatenated text string or empty string on failure.
    """
    if not image_path or not os.path.exists(image_path):
        return ""

    try:
        import Vision
        from Cocoa import NSURL

        url = NSURL.fileURLWithPath_(str(image_path))
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setUsesLanguageCorrection_(False)

        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
        success, error = handler.performRequests_error_([req], None)

        if success and req.results():
            lines = [obs.topCandidates_(1)[0].string() for obs in req.results()]
            extracted = " \n ".join(lines)
            logger.debug(f"[OCR] Extracted: {extracted}")
            return extracted
    except Exception as exc:
        logger.debug(f"[OCR] Vision extraction failed: {exc}")

    return ""

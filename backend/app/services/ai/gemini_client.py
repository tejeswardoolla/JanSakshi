import os
import logging
from typing import Optional, List, Union
from PIL import Image

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL, is_gemini_configured
from app.services.ai.prompt_templates import (
    COMPLAINT_ANALYSIS_SYSTEM_INSTRUCTION,
    build_complaint_analysis_prompt
)
from app.services.ai.response_parser import (
    parse_and_validate_ai_response,
    StructuredAnalysisResult
)

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Wrapper for Google Gen AI SDK for Python (google-genai v3.0+).
    Safely handles unconfigured keys, rate limits, timeouts, and network errors.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize google-genai Client: {str(e)}")
                self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self._client is not None)

    async def analyze_complaint(
        self,
        category: str,
        description: str,
        image_path: Optional[str] = None
    ) -> StructuredAnalysisResult:
        """
        Sends multimodal or text prompt to Gemini and parses the structured response.
        Raises RuntimeError or ValueError on API/parsing failures.
        """
        if not self.is_configured:
            raise RuntimeError("Gemini API key is not configured or client initialization failed.")

        prompt = build_complaint_analysis_prompt(
            category=category,
            description=description,
            has_image=bool(image_path and os.path.exists(image_path))
        )

        contents = []

        # If image evidence is present and valid, load it using PIL
        if image_path and os.path.exists(image_path):
            try:
                pil_image = Image.open(image_path)
                contents.append(pil_image)
            except Exception as img_err:
                logger.warning(f"Could not load image evidence at {image_path}: {img_err}")

        contents.append(prompt)

        try:
            from google.genai import types
            
            # Request explicit JSON output format using standard config
            config = types.GenerateContentConfig(
                system_instruction=COMPLAINT_ANALYSIS_SYSTEM_INSTRUCTION,
                temperature=0.2,
                response_mime_type="application/json"
            )

            # Note: client.models.generate_content is synchronous in the SDK, so call safely
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )

            raw_text = response.text or "{}"
            return parse_and_validate_ai_response(raw_text)

        except Exception as e:
            logger.error(f"Gemini API request failed for model '{self.model}': {str(e)}")
            raise e


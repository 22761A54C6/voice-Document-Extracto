import logging
import requests
from typing import Dict, Any

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


def translate_to_english(text: str) -> str:
    """
    Send text to Ollama LLM for multi-language to English translation.
    
    Args:
        text: Text in any language to be translated to English
        
    Returns:
        English translation from the LLM
    """
    try:
        url = f"{OLLAMA_BASE_URL}/api/generate"
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"Translate this to English if needed: {text}\n\nRules:\n1. If already in English, return it unchanged\n2. If in another language, translate to English\n3. Return ONLY the English text - no original text, no explanations, no extra formatting\n4. Use standard English alphabet only",
            "stream": False
        }
        
        logger.info(f"Sending text to Ollama for translation: {text[:100]}...")
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        translated_text = result.get("response", "").strip()
        
        logger.info(f"Received translated text from Ollama: {translated_text[:100]}...")
        
        return translated_text
        
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out")
        raise Exception("LLM translation request timed out")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        raise Exception(f"LLM translation request failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during LLM translation: {e}")
        raise Exception(f"LLM translation failed: {e}")


def correct_text(text: str) -> str:
    """
    Send text to Ollama LLM for grammar and spelling correction.
    
    Args:
        text: Text to be corrected
        
    Returns:
        Corrected text from the LLM
    """
    try:
        url = f"{OLLAMA_BASE_URL}/api/generate"
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"Correct the grammar, spelling, and punctuation of the following text. Return ONLY the corrected text without any explanations or additional formatting:\n\n{text}",
            "stream": False
        }
        
        logger.info(f"Sending text to Ollama for correction: {text[:100]}...")
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        corrected_text = result.get("response", "").strip()
        
        logger.info(f"Received corrected text from Ollama: {corrected_text[:100]}...")
        
        return corrected_text
        
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out")
        raise Exception("LLM correction request timed out")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        raise Exception(f"LLM correction request failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during LLM correction: {e}")
        raise Exception(f"LLM correction failed: {e}")


def generate_short_description(text: str) -> str:
    """
    Generate a 3-line description of the text using Ollama LLM.
    
    Args:
        text: Text to describe
        
    Returns:
        3-line description from the LLM
    """
    try:
        url = f"{OLLAMA_BASE_URL}/api/generate"
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"Generate a 3-line description of the following text. Return ONLY the description without any explanations:\n\n{text}",
            "stream": False
        }
        
        logger.info(f"Sending text to Ollama for description: {text[:100]}...")
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        description = result.get("response", "").strip()
        
        logger.info(f"Received description from Ollama: {description}")
        
        return description
        
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out")
        raise Exception("LLM description request timed out")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        raise Exception(f"LLM description request failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during LLM description: {e}")
        raise Exception(f"LLM description failed: {e}")

import os
import re
import logging
import time
from typing import Optional
from openai import OpenAI
from prometheus_client import Histogram, Counter

logger = logging.getLogger(__name__)

# Metric definition
AI_ESTIMATIONS = Counter('ai_estimations_total', 'Total AI price estimations')
AI_LATENCY = Histogram('ai_estimation_duration_seconds', 'AI estimation duration in seconds', ['status'])
AI_ERRORS = Counter('ai_errors_total', 'Total number of AI pricing errors')

_client = None

def get_openai_client():
    global _client
    if _client is None:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return None
        _client = OpenAI(api_key=api_key)
    return _client

def estimate_item_price(item_name: str, category: str) -> tuple[float, str]:
    """
    Estimate the average market price of an item in Israel (NIS) using OpenAI.
    Default to 15.0 if AI fails (as per PRD Section 3.3).
    """
    AI_ESTIMATIONS.inc()
    start_time = time.time()
    status = 'ERROR'

    try:
        if not os.environ.get('OPENAI_API_KEY'):
            logger.warning("OPENAI_API_KEY not set, using default price 0.0")
            AI_ERRORS.inc()
            return 0.0, 'ERROR'

        prompt = (
            f"Estimate the current average price in New Israeli Shekels (NIS) for the item: '{item_name}' "
            f"in the category '{category}' in Israel. "
            "Return ONLY the numeric value (as a float). No text, no currency symbols."
        )

        client = get_openai_client()
        if not client:
            logger.warning("OpenAI client not initialized, using default price 0.0")
            AI_ERRORS.inc()
            return 0.0, 'ERROR'

        model_name = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
            timeout=5.0
        )
        
        content = response.choices[0].message.content.strip()
        
        # Robust parsing using Regex to find the first number (integer or float)
        match = re.search(r'(-?\d+(?:\.\d+)?)', content)
        
        if not match:
            AI_ERRORS.inc()
            return 0.0, 'ERROR'
            
        price = float(match.group(1))
        
        # Ensure we don't return 0.0 or negative if AI is confused
        if price <= 0:
            AI_ERRORS.inc()
            return 0.0, 'ERROR'

        status = 'COMPLETED'
        return price, 'COMPLETED'
        
    except Exception as e:
        logger.error(f"AI Pricing failed for {item_name}: {str(e)}")
        AI_ERRORS.inc()
        return 0.0, 'ERROR' # Fallback
    finally:
        duration = time.time() - start_time
        AI_LATENCY.labels(status=status).observe(duration)
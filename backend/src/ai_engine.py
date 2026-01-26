import os
import logging
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

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
    if not os.environ.get('OPENAI_API_KEY'):
        logger.warning("OPENAI_API_KEY not set, using default price 15.0")
        return 15.0, 'ERROR'

    prompt = (
        f"Estimate the average price in New Israeli Shekels (NIS) for the item: '{item_name}' "
        f"in the category '{category}' in Israel. "
        "Return ONLY the numeric value (as a float). No text, no currency symbols."
    )

    client = get_openai_client()
    if not client:
        logger.warning("OpenAI client not initialized, using default price 15.0")
        return 15.0, 'ERROR'

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
            timeout=5.0
        )
        
        content = response.choices[0].message.content.strip()
        # Clean potential non-numeric junk
        price_str = ''.join(c for c in content if c.isdigit() or c == '.')
        
        if not price_str:
            return 15.0, 'ERROR'
            
        price = float(price_str)
        # Ensure we don't return 0.0 if AI is confused
        if price <= 0:
            return 15.0, 'ERROR'

        return price, 'COMPLETED'
    except Exception as e:
        logger.error(f"AI Pricing failed for {item_name}: {str(e)}")
        return 15.0, 'ERROR' # PRD Fallback

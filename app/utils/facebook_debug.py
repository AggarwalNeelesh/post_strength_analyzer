import aiohttp
from typing import Dict, Any, Optional
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

async def debug_facebook_token(token: str) -> Dict[str, Any]:
    """
    Debug a Facebook access token using the Graph API v22.0.
    
    Args:
        token: The Facebook access token to debug
        
    Returns:
        Dict containing the debug information or error details
    """
    debug_url = "https://graph.facebook.com/v22.0/debug_token"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(debug_url, params={
                "input_token": token,
                "access_token": token  # You might need an app access token here
            }) as response:
                response_data = await response.json()
                logger.info("Facebook token debug response received", 
                           status=response.status)
                return response_data
                
        except Exception as e:
            logger.error("Facebook token debug request failed", error=str(e))
            return {
                "error": {
                    "message": str(e),
                    "type": "RequestError",
                    "code": 500
                }
            } 
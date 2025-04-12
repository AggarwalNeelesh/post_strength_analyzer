from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq

from app.config.settings import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

def get_llm(temperature: float = 0, model: Optional[str] = None):
    """
    Factory function to get the appropriate LLM based on configuration.
    
    Args:
        temperature: The temperature setting for the LLM
        model: Optional model override. If None, uses the model from settings
        
    Returns:
        A configured LLM (either ChatOpenAI or ChatGroq)
    """
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "openai":
        model_name = model or settings.OPENAI_MODEL
        logger.info(f"Using OpenAI model: {model_name}")
        return ChatOpenAI(temperature=temperature, model=model_name)
    
    elif provider == "groq":
        if not settings.GROQ_API_KEY:
            logger.warning("No Groq API key found, falling back to OpenAI")
            model_name = settings.OPENAI_MODEL
            return ChatOpenAI(temperature=temperature, model=model_name)
        
        model_name = model or settings.GROQ_MODEL
        logger.info(f"Using Groq model: {model_name}")
        return ChatGroq(temperature=temperature, model=model_name, api_key=settings.GROQ_API_KEY)
    
    else:
        logger.warning(f"Unknown LLM provider '{provider}', falling back to OpenAI")
        model_name = settings.OPENAI_MODEL
        return ChatOpenAI(temperature=temperature, model=model_name) 
from typing import Dict, Any, Optional
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from app.utils.logging_config import get_logger
from app.utils.llm_factory import get_llm

logger = get_logger(__name__)

PREPROCESSING_PROMPT = """
You are an AI assistant that refines social media posts to be clear, compelling, and optimized for audience engagement.

Here are some rules learned from past successful posts:
{rules}

Original Post:
{post_text}

Instructions:
- Keep the post concise but emotionally engaging.
- Fix unclear or vague language.
- Maintain the intent and tone of the original.
- Improve grammar and structure.
- Add relevant hashtags, emojis, or call-to-actions if appropriate (based on rules).
- Do not include any headings, labels, or formatting in your response.
- Return **only** the improved version of the post — nothing else.

[Output below, without quotes or formatting]
[Output]
"""



class PreprocessingAgent:
    def __init__(self, temperature: float = 0):
        self.llm = get_llm(temperature=temperature)
        self.prompt = PromptTemplate(
            input_variables=["post_text", "rules"],
            template=PREPROCESSING_PROMPT
        )
        self.chain = {"post_text": RunnablePassthrough(), "rules": RunnablePassthrough()} | self.prompt | self.llm
        logger.info("Preprocessing agent initialized")

    async def process(self, post_text: str, rules: str) -> str:
        """Process and improve a social media post based on learned rules."""
        try:
            if "default rules" in rules.lower():
                logger.warning("Using fallback/default rules for preprocessing")

            logger.info(f"Processing post text with preprocessing agent: {post_text}")

            result = await self.chain.ainvoke({
                "post_text": post_text,
                "rules": rules
            })

            improved_post = result.content.strip()
            logger.info(f"Refined post generated: {improved_post}")
            return improved_post

        except Exception as e:
            logger.error("Error in preprocessing agent", error=str(e), exc_info=True)
            return post_text  # fallback: return the original text

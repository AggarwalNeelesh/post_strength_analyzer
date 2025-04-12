from typing import Dict, Any
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough

from app.utils.logging_config import get_logger
from app.utils.llm_factory import get_llm

logger = get_logger(__name__)

RULES_PROMPT_WITH_DATA = """
You are an expert social media strategist. Below is a dataset of previous social media posts from a business:

{post_data}

Please:
1. Derive practical rules for what makes a strong post.
2. Compare posts with images/videos vs. text-only for performance.
3. Identify optimal posting times based on `publish_date`.
4. Detect text patterns that lead to better metrics (engagement, reach, etc).
5. Provide insights into how reach, impression, and engagement correlate.

Output these findings as actionable rules to guide future post evaluations.
"""

class RulesAgent:
    def __init__(self, temperature: float = 0):
        self.llm = get_llm(temperature=temperature)
        self.prompt = PromptTemplate(
            input_variables=["post_data"],
            template=RULES_PROMPT_WITH_DATA
        )
        self.chain = RunnablePassthrough() | self.prompt | self.llm
        logger.info("Rules agent initialized")

    async def process(self, account_id: int, post_data: str) -> str:
        try:
            logger.info(f"Generating post evaluation rules for account_id: {account_id}")
            result = await self.chain.ainvoke({"post_data": post_data})
            return result.content.strip()
        except Exception as e:
            logger.error("Failed to generate rules", error=str(e), exc_info=True)
            return "Unable to derive rules from current data."

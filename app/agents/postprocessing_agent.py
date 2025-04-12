from typing import Dict, Any, List, Optional
import json
import structlog
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough    
import re
import json

from app.utils.logging_config import get_logger
from app.utils.llm_factory import get_llm
from app.db.redis_client import redis_client  # assuming you place redis_client in a utils file

logger = get_logger(__name__)

POSTPROCESSING_PROMPT = """
You are an AI assistant helping businesses improve their social media performance by analyzing post content and past engagement data.

Your task is to:
1. Evaluate how strong the new post is likely to perform in terms of reach and engagement.
2. Suggest improvements in content, timing, formatting, and the use of images or hashtags.
3. Guide the business to increase visibility and response through actionable recommendations.

Inputs:
- Original Post: The raw, user-written social media post.
- Refined Text: The AI-enhanced version of the post (may be similar or improved).
- Past Post Insights: Historical data showing metrics (likes, shares, comments) and characteristics (posting time, media type, etc.) of previously published posts.

Use the following rules while calculating `post_strength`:
- Start from a base strength score derived from analyzing content engagement patterns in the refined text and past post insights.
- If an image **is present**, add +1 to the score. If not, subtract 1.
- If the post_text **contains at least one hashtag**, add +1. If none, subtract 1.
- If the post_text **contains at least one emoji**, add +1. If none, subtract 1.
- If the post_text **length is between 80 and 250 characters**, add +1. If not, subtract 1.
- The final score must be between 1 and 10 (inclusive).

Original Post: {post_text}

Refined Text: {enhanced_text}

Past Post Insights (Sample): {results}


Do not include any explanations or extra text. Only return the JSON in the exact format below:
json
{{
  "post_strength": Integer between 1 and 10,   // 1 is weakest, 10 is strongest
  "enhanced_text": "String",  // The final improved version of the post, keep it as a plain string
  "suggested_schedule_time": "YYYY-MM-DD HH:MM:SS", // The time should be in this exact format only
  "is_image_required": boolean,  // Whether adding an image is crucial or not
  "suggested_hashtag": "String",  // Suggested matching hashtags for the post
  "suggested_emojis": "String",  // Suggested matching emojis for the post
  "explanation": "String"  // Brief reasoning behind the score and suggestions
}}
"""


class PostprocessingAgent:
    def __init__(self, temperature: float = 0.4):
        self.llm = get_llm(temperature=temperature)
        self.prompt = PromptTemplate(
            input_variables=["post_text", "enhanced_text", "results"],
            template=POSTPROCESSING_PROMPT
        )
        self.chain = RunnablePassthrough() | self.prompt | self.llm
        logger.info("Postprocessing agent initialized")

    def _format_results(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "No previous post data available."
        try:
            compact_results = [
                {
                    "post_text": post.get("post_text", "")[:100],
                    "likes": post.get("likes"),
                    "comments": post.get("comments"),
                    "shares": post.get("shares"),
                    "impression": post.get("impression"),
                    "publish_date": post.get("publish_date")
                }
                for post in results[:10]
            ]
            return json.dumps(compact_results, indent=2, default=str)
        except Exception as e:
            logger.error("Error formatting results", error=str(e), exc_info=True)
            return str(results)



    def normalize(self, text: str) -> str:
        return ' '.join(text.lower().split())

    async def _is_duplicate_post(self, account_id: int, normalized_input: str) -> bool:
        key = f"post_history:{account_id}"
        recent_posts = await redis_client.smembers(key)
        return normalized_input in recent_posts

    async def _store_post(self, account_id: int, enhanced_text: str):
        key = f"post_history:{account_id}"
        normalized = self.normalize(enhanced_text)
        await redis_client.sadd(key, normalized)
        await redis_client.expire(key, 86400 * 30)  # keep post history for 30 days

    async def process(
        self,
        post_text: str,
        enhanced_text: Optional[str],
        data: List[Dict[str, Any]],
        account_id: int
    ) -> Dict[str, Any]:
        try:
            formatted_results = self._format_results(data)
            enhanced_text = enhanced_text or "No refined version available."
            normalized_input = self.normalize(post_text)

            logger.info("Processing post with postprocessing agent")
            result = await self.chain.ainvoke({
                "post_text": post_text,
                "enhanced_text": enhanced_text,
                "results": formatted_results
            })

            logger.info(f"Postprocessing completed result : {result.content}")

            try:
                parsed = json.loads(result.content.strip())
                logger.info(f"Parsed AI response successfully: {parsed}")
                key = f"post_history:{account_id}"
                recent_posts = await redis_client.smembers(key)
                is_duplicate = await self._is_duplicate_post(account_id, normalized_input)
                logger.info(f"Recent posts for account {account_id}: {recent_posts} and is Duplicate : {is_duplicate}")

                # Check for repost
                if is_duplicate:
                    logger.info("Detected repost of enhanced content — returning full strength.")
                    parsed["post_strength"] = 10
                    parsed["explanation"] = "This post is already in optimal format. No changes needed."
                    parsed["enhanced_text"] = post_text
                else:
                    logger.info("Storing new post in Redis for future duplicate checks.")
                    await self._store_post(account_id, parsed["enhanced_text"])
                    logger.info(f"Post stored successfully in Redis for account {account_id} with key {key}")

                # Default is_image_required if missing
                if parsed.get("is_image_required") is None:
                    parsed["is_image_required"] = True

                return parsed

            except Exception as parse_err:
                logger.warning("Failed to parse AI response as JSON. Returning fallback.")
                logger.warning(f"Raw AI response: {result.content} error : {parse_err}")
                return {
                    "post_strength": 7,
                    "enhanced_text": enhanced_text,
                    "suggested_schedule_time": "Afternoon (1–3 PM)",
                    "is_image_required": True,
                    "suggested_hashtag": "#engage #growth",
                    "suggested_emojis": "🚀🔥💬",
                    "explanation": "Default fallback. Couldn't parse AI response properly."
                }

        except Exception as e:
            logger.error(f"Error in postprocessing agent: {str(e)}", exc_info=True)
            return {
                "post_strength": 1,
                "enhanced_text": post_text,
                "suggested_schedule_time": "Evening",
                "is_image_required": True,
                "suggested_hashtag": "#socialmedia",
                "suggested_emojis": "😅🤖💡",
                "explanation": "Postprocessing failed due to internal error."
            }
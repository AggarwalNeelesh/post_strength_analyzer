from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Header
import structlog
import time
from pydantic import BaseModel

from app.agents.preprocessing_agent import PreprocessingAgent
from app.agents.sql_agent import SQLAgent
from app.agents.postprocessing_agent import PostprocessingAgent
from app.utils.logging_config import get_logger
from app.db.mysql_client import init_db_pool
from app.agents.rules_agent import RulesAgent

logger = get_logger(__name__)

router = APIRouter()
# Dependency to ensure the database is initialized

# Initialize agents
preprocessing_agent = PreprocessingAgent()
sql_agent = SQLAgent()
postprocessing_agent = PostprocessingAgent()
rules_agent = RulesAgent()


class AnalyzePostRequest(BaseModel):
    post_text: str
    is_image_present: bool
    schedule_time: Optional[str] = None

@router.post("/analyze-post")
async def analyze_post_strength(
    request: AnalyzePostRequest,
    enterprise_id: Optional[int] = Header(None, alias="enterprise_id")
) -> Dict[str, Any]:
    """
    Analyze post quality and suggest improvements for better engagements.
    """
    logger.info(f"Received post strength analysis request : {enterprise_id}")
    start_time = time.time()

    try:
        logger.info(f"Processing post analysis. Request: {request}")
        logger.info(f"enterprise ID: {enterprise_id}")


        # Step 1: Analyze past posts and score this one
        sql_start = time.time()
        logger.info("Fetching past posts from DB")
        post_data = await sql_agent.process(enterprise_id)
        formatted_post_data = format_post_data_for_rules(post_data)
        logger.info("SQL data analysis completed", duration=f"{time.time() - sql_start:.2f}s")

        # Step 2: Generate rules based on context
        rules_start = time.time()
        rules = await rules_agent.process(enterprise_id, formatted_post_data)
        logger.info("Rules generation completed", duration=f"{time.time() - rules_start:.2f}s")

        # Step 3: Preprocess the post_text using rules
        preprocess_start = time.time()
        refined_text = await preprocessing_agent.process(request.post_text, rules)
        logger.info("Preprocessing completed", duration=f"{time.time() - preprocess_start:.2f}s")

        # Step 4: Postprocess response with suggestions
        response_data = await postprocessing_agent.process(
            post_text=request.post_text,
            enhanced_text=refined_text,
            data=post_data,
            account_id=enterprise_id
        )

        # Step 5: Construct final structured response
        final_response = {
            "post_strength": float(response_data.get("post_strength", 0.75)),
            "enhanced_text": response_data.get("enhanced_text", refined_text),
            "suggested_schedule_time": response_data.get("suggested_schedule_time", request.schedule_time),
            "is_image_required": bool(response_data.get("is_image_required", True)),
            "suggested_hashtag": response_data.get("suggested_hashtag", ""),
            "suggested_emojis": response_data.get("suggested_emojis", ""), 
            "explanation": response_data.get("explanation", "No explanation provided.")
        }

        logger.info("Post analysis completed", response=final_response)
        total_time = time.time() - start_time
        logger.info("Total post strength processing time", total_duration=f"{total_time:.2f}s")

        return final_response

    except Exception as e:
        logger.error("Error processing post analysis", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing post: {str(e)}")


def format_post_data_for_rules(raw_posts: list[dict]) -> str:
    formatted = []
    for idx, post in enumerate(raw_posts, 1):
        formatted.append(
            f"{idx}. \"{post['post_text']}\" | likes: {post['likes']} | shares: {post['shares']} | "
            f"reach: {post['reach']} | impressions: {post['impression']} | image: {'yes' if post['image_urls'] else 'no'} | "
            f"published: {post['publish_date']}"
        )
    return "\n".join(formatted)


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}

@router.post("/query")
async def process_query(
    request: Dict[str, Any],
    account_id: Optional[int] = Header(None, alias="accountId"),
    is_reseller: Optional[bool] = Header(False, alias="isReseller")
) -> Dict[str, Any]:
    """
    Process a natural language query using LangChain agents.
    
    Args:
        request: A dictionary containing the user's question.
        account_id: Account ID from header
        is_reseller: Boolean indicating if the user is a reseller
    """
    if "question" not in request:
        raise HTTPException(status_code=400, detail="Missing 'question' field in request")
    
    original_question = request["question"]
    logger.info("Received query request", 
                question=original_question,
                account_id=account_id,
                is_reseller=is_reseller)
    
    start_time = time.time()
    
    try:
        # Step 1: Generate rules based on context
        rules_start = time.time()
        rules = await rules_agent.process(account_id, is_reseller)
        logger.info("Rules generation completed", duration=f"{time.time() - rules_start:.2f}s")
        
        # Step 2: Preprocess the question with rules
        preprocess_start = time.time()
        refined_question = await preprocessing_agent.process(original_question, rules)
        logger.info("Preprocessing completed", duration=f"{time.time() - preprocess_start:.2f}s")
        
        # Step 3: Generate and execute SQL query
        sql_start = time.time()
        logger.info("SQL query generation started")
        sql_result = await sql_agent.process(refined_question)
        logger.info("SQL processing completed", duration=f"{time.time() - sql_start:.2f}s")
        
        # Step 4: Postprocess the results
        user_response = await postprocessing_agent.process(
            question=original_question,
            query=sql_result.get("query"),
            data=sql_result.get("data", [])
        )
        
        # Prepare the response
        response = {
            "original_question": original_question,
            "refined_question": refined_question,
            "sql_query": sql_result.get("query"),
            "response": user_response,
            "data": sql_result.get("data", [])
        }
        
        if "error" in sql_result:
            response["error"] = sql_result["error"]
        
        logger.info("Query processed successfully")
        
        total_time = time.time() - start_time
        logger.info("Total query processing completed", total_duration=f"{total_time:.2f}s")
        return response
    
    except Exception as e:
        logger.error("Error processing query", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

# Dependency to ensure the database is initialized
async def ensure_db_initialized():
    init_db_pool() 



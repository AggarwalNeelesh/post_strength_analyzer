from typing import Dict, Any, List, Optional
import structlog
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough, RunnableSequence
import re
import time

from app.utils.logging_config import get_logger
from app.db.mysql_client import execute_query, get_database_schema
from app.utils.llm_factory import get_llm

logger = get_logger(__name__)

SQL_GENERATION_PROMPT = """
You are an expert SQL query generator. Based on the database schema and the user's question, 
generate a valid SQL query that will retrieve the information requested.

Database Schema:
{schema}

User Question: {question}

Rules:
1. Generate only the SQL query, without any explanation.
2. Use proper SQL syntax for MySQL.
3. Make sure the query is secured against SQL injection.
4. Only reference tables and columns that exist in the schema.
5. Keep the query as simple as possible while answering the question completely.

SQL Query:
"""

class SQLAgent:
    def __init__(self):
        self._schema_cache: Optional[str] = None
        self._query_template = """
            SELECT COALESCE(NULLIF(business_id, 0), 0) AS business_id,
                   COALESCE(NULLIF(source_id, 0), 0) AS source_id,
                   COALESCE(NULLIF(post_url, ''), 'Not present') AS post_url,
                   COALESCE(NULLIF(post_id, ''), 'Not present') AS post_id,
                   COALESCE(NULLIF(post_text, ''), 'Not present') AS post_text,
                   COALESCE(NULLIF(image_urls, ''), 'Not present') AS image_urls,
                   COALESCE(NULLIF(video_urls, ''), 'Not present') AS video_urls,
                   IFNULL(DATE_FORMAT(publish_date, '%Y-%m-%d %H:%i:%s'), 'Not present') AS publish_date,
                   COALESCE(NULLIF(page_name, ''), 'Not present') AS page_name,
                   COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(response, '$.engagement')), ''), 'Not present') AS engagement,
                   COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(response, '$.reach')), ''), 'Not present') AS reach,
                   COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(response, '$.impression')), ''), 'Not present') AS impression,
                   COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(response, '$.likeCount')), ''), 'Not present') AS likes,
                    COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(response, '$.shareCount')), ''), 'Not present') AS shares,
                    COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(response, '$.commentCount')), ''), 'Not present') AS comments
            FROM business_posts
            WHERE enterprise_id = %(account_id)s
              AND JSON_LENGTH(response) > 0
            ORDER BY id DESC
            LIMIT 50;
        """
        logger.info("SQLAgent initialized with static post analysis query")

    async def process(self, account_id: int) -> List[Dict[str, Any]]:
        """
        Executes the predefined SQL query to fetch recent post history
        for a given business account (enterprise_id).
        """
        try:
            logger.info(f"Running SQL query for post history. account_id={account_id}")
            data = await execute_query(self._query_template, {"account_id": account_id})
            logger.info(f"Query executed successfully. Rows returned: {len(data)}")
            return data
        except Exception as e:
            logger.error("Failed to execute SQL query", error=str(e), exc_info=True)
            return []

    async def _format_schema(self, schema: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format the database schema for prompt usage."""
        schema_text = []
        for table_name, columns in schema.items():
            schema_text.append(f"Table: {table_name}")
            column_list = []
            for column in columns:
                col_type = column.get("Type", "")
                nullable = "NOT NULL" if column.get("Null", "YES") == "NO" else "NULL"
                key = "PRIMARY KEY" if column.get("Key", "") == "PRI" else ""
                default = f"DEFAULT {column.get('Default')}" if column.get("Default") else ""
                column_list.append(
                    f"  - {column.get('Field', '')}: {col_type} {nullable} {key} {default}".strip()
                )
            schema_text.append("\n".join(column_list))
        return "\n\n".join(schema_text)

    async def _get_cached_schema(self) -> str:
        """Fetch and cache schema for business_posts table only."""
        if self._schema_cache is None:
            schema = await get_database_schema()
            business_posts_schema = {"business_posts": schema.get("business_posts", [])}
            self._schema_cache = await self._format_schema(business_posts_schema)
        return self._schema_cache

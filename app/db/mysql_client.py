import atexit
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Any, Optional
import os
import time

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
import structlog

from app.config.settings import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Global connection pool
pool: Optional[MySQLConnectionPool] = None

def init_db_pool() -> None:
    """Initialize the MySQL connection pool."""
    global pool
    
    if pool is not None:
        logger.info("Database pool already initialized")
        return
    
    try:
        # Try to connect to the database
        pool = MySQLConnectionPool(
            pool_name=settings.MYSQL_POOL_NAME,
            pool_size=settings.MYSQL_POOL_SIZE,
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            use_pure=True,
            autocommit=True,
        )
        logger.info(
            "MySQL connection pool initialized", 
            pool_name=settings.MYSQL_POOL_NAME, 
            pool_size=settings.MYSQL_POOL_SIZE
        )
    except mysql.connector.Error as err:
        logger.error("Failed to initialize database pool", error=str(err))
        
        # For development - create an in-memory database or mock
        if os.getenv("ENVIRONMENT", "development") == "development":
            logger.warning("Using mock database for development")
            # Initialize a mock or in-memory database here
        else:
            raise  # Re-raise the error in production

def close_db_pool() -> None:
    """Close all connections in the pool."""
    global pool
    if pool:
        # This will close all connections in the pool
        for i in range(settings.MYSQL_POOL_SIZE):
            try:
                conn = pool.get_connection()
                conn.close()
            except:
                pass
        pool = None
        logger.info("Database pool closed")

# Register the function to close the pool when the application exits
atexit.register(close_db_pool)

@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[mysql.connector.MySQLConnection, None]:
    """Get a connection from the pool as an async context manager."""
    if pool is None:
        init_db_pool()
    
    connection = None
    try:
        connection = pool.get_connection()
        logger.debug("Database connection acquired from pool")
        yield connection
    except mysql.connector.Error as err:
        logger.error("Database connection error", error=str(err))
        raise
    finally:
        if connection:
            connection.close()
            logger.debug("Database connection returned to pool")

async def execute_query(
    query: str, 
    params: Optional[tuple] = None,
    fetch: bool = True,
    timeout: int = 30  # Add timeout parameter
) -> List[Dict[str, Any]]:
    """Execute a SQL query and return the results as a list of dictionaries."""
    async with get_db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Add optimizer hints for better performance
            if query.lower().startswith('select'):
                query = f"SELECT /*+ MAX_EXECUTION_TIME({timeout*1000}) */ " + query[6:]
            
            start_time = time.time()
            cursor.execute(query, params)
            
            if fetch:
                result = cursor.fetchall()
                query_time = time.time() - start_time
                logger.info("Query execution completed", 
                           duration=f"{query_time:.2f}s",
                           rows_returned=len(result),
                           query=f"{query}")
                return result
            return []
        except mysql.connector.Error as err:
            logger.error("Query execution error", 
                        query=query, 
                        error=str(err), 
                        exc_info=True)
            raise
        finally:
            cursor.close()

async def get_table_schema(table_name: str) -> List[Dict[str, Any]]:
    """Get the schema for a specific table."""
    query = f"DESCRIBE {table_name}"
    return await execute_query(query)

async def get_database_schema() -> Dict[str, List[Dict[str, Any]]]:
    """Get the schema for required tables only."""
    # Define the tables we actually need for our queries
    required_tables = ['business_posts']  # Add other required tables here
    
    schema = {}
    for table_name in required_tables:
        try:
            table_schema = await get_table_schema(table_name)
            schema[table_name] = table_schema
        except Exception as e:
            logger.error(f"Error fetching schema for {table_name}", error=str(e))
            # Continue with other tables if one fails
            continue
    
    return schema 
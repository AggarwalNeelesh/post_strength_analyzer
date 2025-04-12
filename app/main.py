import os
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import structlog
import time
from contextlib import asynccontextmanager

from app.api.routes import router
from app.config.settings import settings
from app.utils.logging_config import configure_logging, get_logger
from app.db.mysql_client import init_db_pool, close_db_pool

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Replace @app.on_event handlers with lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting application")
    init_db_pool()
    
    yield  # This is where the application runs
    
    # Shutdown logic
    logger.info("Shutting down application")
    close_db_pool()

# Update FastAPI app initialization to use lifespan
app = FastAPI(
    title="Natural Language to SQL API",
    description="An API that converts natural language questions to SQL queries using LangChain agents",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        "Request processed",
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration=f"{process_time:.4f}s",
    )
    return response

# Include routers
app.include_router(router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=False,  # Disable uvicorn access logs
        use_colors=False,  # Avoid color codes in logs
        log_config=None,   # Use our custom logging config
    ) 
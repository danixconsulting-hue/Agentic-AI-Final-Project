# fastapi_app.py
"""
FastAPI application for ChildWelfare Training Chatbot Agent

Exposes the chatbot as a REST API with endpoints for:
- Chat messages
- Knowledge base management
- Health checks
"""

import os
import asyncio
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.genai import types

# Import chatbot components
from childwelfare_agent import (
    initialize_rag_system,
    add_document_to_rag,
    search_documents,
    web_search,
    ingest_from_github,
    ingest_local_file,
    create_customer_chatbot_agent,
    run_chatbot
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
agent = None
active_sessions = {}

# ============================================================================
# Pydantic Models
# ============================================================================

class ChatMessage(BaseModel):
    """Chat message request"""
    user_id: str = "user1"
    session_id: str = "session1"
    message: str
    temperature: Optional[float] = None


class ChatResponse(BaseModel):
    """Chat response"""
    success: bool
    response: str
    session_id: str
    user_id: str
    tool_used: Optional[str] = None


class DocumentRequest(BaseModel):
    """Add document to RAG system"""
    content: str
    metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    """Document addition response"""
    success: bool
    doc_id: Optional[str] = None
    message: str


class SearchRequest(BaseModel):
    """Search knowledge base"""
    query: str
    top_k: int = 3


class SearchResponse(BaseModel):
    """Search results"""
    success: bool
    query: str
    results: List[Dict[str, Any]]
    message: str


class WebSearchRequest(BaseModel):
    """Web search request"""
    query: str


class WebSearchResponse(BaseModel):
    """Web search results"""
    success: bool
    query: str
    results: List[Dict[str, Any]]
    message: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str
    active_sessions: int


# ============================================================================
# Startup and Shutdown
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup, cleanup on shutdown"""
    global agent

    logger.info("Initializing chatbot system...")
    try:
        # Initialize RAG system
        initialize_rag_system()
        logger.info("✓ FAISS RAG system initialized")

        # Create agent
        agent = create_customer_chatbot_agent()
        logger.info("✓ Child Welfare Training support agent created")

        # Add sample documents
        sample_docs = [
        {
            "content": "Teachers and Social workers must report suspected child abuse or neglect directly to either law enforcement or DFPS.Phone: 1-800-252-5400",
            "metadata": {"title": "Support Channels", "category": "contact"}
        },
        {
            "content": "Under Texas Family Code, within what timeframe must a 'professional' report suspected child abuse or neglect?",
            "metadata": {"title": "Statutory Timeframe", "category": "Urgency"}
        },
        {
            "content": "A teacher notices suspicious bruising on a student and tells the school social worker to handle the situation. Who is legally liable under Texas law?",
            "metadata": {"title": "Professional Liability", "category": "Scope of duty"}
        },
        {
            "content": "A school social worker suspects neglect, but lacks physical proof. Does this meet the threshold for reporting to the DFPS?",
            "metadata": {"title": "Legal Standard", "category": "Reporting"}
        },
	{
            "content": "If a teacher suspects a student is in immediate physical danger, what is the required protocol regarding utilizing the online portal vs. direct contact?",
            "metadata": {"title": "Reporting Channels", "category": "Emergency Protocols"}
        }
        ]

        for doc in sample_docs:
            add_document_to_rag(doc["content"], doc["metadata"])

        logger.info(f"✓ Added {len(sample_docs)} sample documents to knowledge base")
        logger.info("✓ Chatbot system ready for requests")

    except Exception as e:
        logger.error(f"✗ Initialization failed: {str(e)}")
        raise

    yield

    # Cleanup
    logger.info("Shutting down chatbot system...")
    active_sessions.clear()
    logger.info("✓ Cleanup complete")


# ============================================================================
# Create FastAPI App
# ============================================================================

app = FastAPI(
    title="Child Welfare Training Chatbot API",
    description="Google ADK-powered Child Welfare Training chatbot with RAG and web search",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and status"""
    return HealthResponse(
        status="healthy",
        message="Chatbot API is running",
        active_sessions=len(active_sessions)
    )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Training Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "search": "/search",
            "web_search": "/web-search",
            "add_document": "/add-document",
            "sessions": "/sessions",
            "docs": "/docs"
        }
    }


# ============================================================================
# Chat Endpoints
# ============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatMessage):
    """
    Send a message to the chatbot and get a response.

    The agent intelligently chooses between:
    - RAG (search_documents) for company information
    - Web Search for external/real-time information
    """
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    try:
        # Track session
        if request.session_id not in active_sessions:
            active_sessions[request.session_id] = {
                "user_id": request.user_id,
                "message_count": 0
            }

        active_sessions[request.session_id]["message_count"] += 1

        logger.info(f"Chat request - Session: {request.session_id}, Message: {request.message[:50]}...")

        # Run agent
        response = await run_chatbot(
            agent,
            request.message,
            user_id=request.user_id,
            session_id=request.session_id
        )

        # Determine which tool was likely used based on message
        tool_used = "RAG" if any(word in request.message.lower() for word in
                                  ["support", "timeframe", "protocol", "reporting", "duty", "hours", "contact"]) else "Web Search"

        logger.info(f"Response sent - Session: {request.session_id}")

        return ChatResponse(
            success=True,
            response=response,
            session_id=request.session_id,
            user_id=request.user_id,
            tool_used=tool_used
        )

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@app.get("/sessions")
async def get_sessions():
    """Get all active sessions"""
    return {
        "active_sessions": len(active_sessions),
        "sessions": active_sessions
    }


@app.delete("/sessions/{session_id}")
async def end_session(session_id: str):
    """End a chat session"""
    if session_id in active_sessions:
        del active_sessions[session_id]
        return {"status": "success", "message": f"Session {session_id} ended"}
    return {"status": "not_found", "message": f"Session {session_id} not found"}


# ============================================================================
# Knowledge Base Endpoints
# ============================================================================

@app.post("/add-document", response_model=DocumentResponse)
async def add_document(request: DocumentRequest):
    """
    Add a new document to the RAG knowledge base.

    The agent will immediately be able to search this document.
    """
    try:
        logger.info(f"Adding document: {request.content[:50]}...")

        result = add_document_to_rag(
            request.content,
            request.metadata or {}
        )

        return DocumentResponse(
            success=result["success"],
            doc_id=result.get("doc_id"),
            message=result["message"]
        )

    except Exception as e:
        logger.error(f"Error adding document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding document: {str(e)}")


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search the knowledge base using semantic similarity.

    This is what the agent uses for company-related questions.
    """
    try:
        logger.info(f"Search request: {request.query}")

        result = search_documents(request.query, request.top_k)

        return SearchResponse(
            success=result["success"],
            query=request.query,
            results=result.get("results", []),
            message=result["message"]
        )

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


# ============================================================================
# Web Search Endpoints
# ============================================================================

@app.post("/web-search", response_model=WebSearchResponse)
async def web_search_endpoint(request: WebSearchRequest):
    """
    Search the web for real-time information.

    This is what the agent uses for external/current information.
    Requires TAVILY_API_KEY to be set.
    """
    try:
        logger.info(f"Web search request: {request.query}")

        result = web_search(request.query)

        return WebSearchResponse(
            success=result["success"],
            query=request.query,
            results=result.get("results", []),
            message=result["message"]
        )

    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Web search error: {str(e)}")


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP Exception: {exc.detail}")
    return {
        "success": False,
        "error": exc.detail,
        "status_code": exc.status_code
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return {
        "success": False,
        "error": "Internal server error",
        "detail": str(exc)
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "fastapi_app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )

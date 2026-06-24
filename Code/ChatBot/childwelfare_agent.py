#childwelfare_agent.py
"""
Google ADK Child Welfare Training Chatbot Agent with FAISS RAG and Web Search

This agent provides:
1. FAISS-based RAG system for document retrieval
2. Web search for real-time information
3. ChildWelfare Training chatbot functionality
"""

import os
import sys
from typing import Dict, Any, List, Optional
import faiss
import numpy as np
import requests
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from vertexai.preview.language_models import TextEmbeddingModel

# Set up authentication
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
# change your project
os.environ["GOOGLE_CLOUD_PROJECT"] = "project-176c7d8a-2df4-4d02-bc0"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

# Point to service account key
#service_key_path = os.path.join(os.path.dirname(__file__), "..", "service-account-key.json")
#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(service_key_path)

# Global RAG storage
faiss_index = None
document_store = {}
doc_id_to_idx = {}
idx_to_doc_id = {}
embedding_model = None
next_doc_id = 0

# Global session service for conversation memory
global_session_service = InMemorySessionService()


def initialize_rag_system():
    """Initialize the FAISS index and embedding model."""
    global faiss_index, embedding_model

    # Initialize FAISS index (768 dimensions for text-embedding-005)
    embedding_dim = 768
    faiss_index = faiss.IndexFlatL2(embedding_dim)

    # Initialize Vertex AI embedding model
    embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")

    print("✓ FAISS RAG system initialized")


def add_document_to_rag(
    content: str,
    metadata: Dict[str, Any] = None,
    tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Add a document to the RAG system.

    Args:
        content: Document text content
        metadata: Optional metadata (title, source, etc.)
        tool_context: Runtime context

    Returns:
        Dict with success status and document ID
    """
    global faiss_index, document_store, doc_id_to_idx, idx_to_doc_id, next_doc_id, embedding_model

    try:
        if not embedding_model:
            return {"success": False, "message": "RAG system not initialized"}

        # Generate embedding
        embedding = embedding_model.get_embeddings([content])[0].values
        embedding_array = np.array([embedding], dtype='float32')

        # Add to FAISS index
        current_idx = faiss_index.ntotal
        faiss_index.add(embedding_array)

        # Store document
        doc_id = f"doc_{next_doc_id}"
        next_doc_id += 1

        document_store[doc_id] = {
            "content": content,
            "metadata": metadata or {},
            "embedding": embedding
        }
        doc_id_to_idx[doc_id] = current_idx
        idx_to_doc_id[current_idx] = doc_id

        return {
            "success": True,
            "doc_id": doc_id,
            "message": f"Document added successfully with ID: {doc_id}"
        }
    except Exception as e:
        return {"success": False, "message": f"Error adding document: {str(e)}"}


def search_documents(
    query: str,
    top_k: int = 3,
    tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Search documents in the RAG system using semantic similarity.

    Args:
        query: Search query
        top_k: Number of top results to return
        tool_context: Runtime context

    Returns:
        Dict with search results
    """
    global faiss_index, document_store, idx_to_doc_id, embedding_model

    try:
        if not embedding_model:
            return {"success": False, "message": "RAG system not initialized"}

        if faiss_index.ntotal == 0:
            return {
                "success": True,
                "results": [],
                "message": "No documents in the knowledge base yet"
            }

        # Generate query embedding
        query_embedding = embedding_model.get_embeddings([query])[0].values
        query_array = np.array([query_embedding], dtype='float32')

        # Search FAISS index
        distances, indices = faiss_index.search(query_array, min(top_k, faiss_index.ntotal))

        # Retrieve documents
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:
                doc_id = idx_to_doc_id.get(idx)
                if doc_id and doc_id in document_store:
                    doc = document_store[doc_id]
                    results.append({
                        "doc_id": doc_id,
                        "content": doc["content"],
                        "metadata": doc["metadata"],
                        "distance": float(distances[0][i])
                    })

        return {
            "success": True,
            "results": results,
            "message": f"Found {len(results)} relevant documents"
        }
    except Exception as e:
        return {"success": False, "message": f"Error searching documents: {str(e)}"}


def web_search(
    query: str,
    tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Perform web search to get real-time information.

    Args:
        query: Search query
        tool_context: Runtime context

    Returns:
        Dict with web search results
    """
    try:
        # Check if Tavily API key is available
        tavily_key = "paste your key here"
        if not tavily_key:
            return {
                "success": False,
                "message": "TAVILY_API_KEY not set. Web search requires Tavily API key."
            }

        from tavily import TavilyClient

        client = TavilyClient(api_key=tavily_key)
        response = client.search(query, max_results=3)

        results = []
        for result in response.get("results", []):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "score": result.get("score", 0)
            })

        return {
            "success": True,
            "results": results,
            "query": query,
            "message": f"Found {len(results)} web results"
        }
    except ImportError:
        return {
            "success": False,
            "message": "tavily-python package not installed. Install with: pip install tavily-python"
        }
    except Exception as e:
        return {"success": False, "message": f"Error performing web search: {str(e)}"}


def ingest_from_github(
    owner: str = "danixconsulting-hue",
    repo: str = "Agentic-AI-Final-Project",
    path: str = "",
    github_token: Optional[str] = None,
    tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Ingest text documents from a GitHub repository into the knowledge base.

    Args:
        owner: GitHub repository owner
        repo: Repository name
        path: Path within the repository to search (optional)
        github_token: Optional GitHub Personal Access Token for authentication
        tool_context: Runtime context
    """
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        
        # Use provided token or fallback to environment variable
        token = github_token or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"

        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        response = requests.get(api_url, headers=headers)

        if response.status_code != 200:
            return {"success": False, "message": f"GitHub API error {response.status_code}: {response.text}"}

        items = response.json()
        if not isinstance(items, list):
            items = [items]

        count = 0
        for item in items:
            # Process supported text files
            if item["type"] == "file" and item["name"].lower().endswith(('.md', '.txt')):
                file_resp = requests.get(item["download_url"], headers=headers)
                if file_resp.status_code == 200:
                    add_document_to_rag(
                        content=file_resp.text,
                        metadata={
                            "title": item["name"],
                            "source": "github",
                            "repo": f"{owner}/{repo}",
                            "url": item["html_url"]
                        }
                    )
                    count += 1

        return {
            "success": True,
            "message": f"Successfully ingested {count} files from GitHub: {owner}/{repo}"
        }
    except Exception as e:
        return {"success": False, "message": f"Failed to ingest from GitHub: {str(e)}"}

def ingest_local_file(
    file_path: str,
    tool_context: ToolContext = None
) -> Dict[str, Any]:
    """
    Ingest a local text, markdown, or PDF file into the RAG system.

    Args:
        file_path: Path to the local file
        tool_context: Runtime context
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "message": f"File not found: {file_path}"}

        ext = file_path.lower().split('.')[-1]
        if ext == 'pdf':
            import pypdf
            reader = pypdf.PdfReader(file_path)
            content = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

        filename = os.path.basename(file_path)
        return add_document_to_rag(
            content=content,
            metadata={"title": filename, "source": "local_file", "path": file_path}
        )
    except Exception as e:
        return {"success": False, "message": f"Error ingesting file: {str(e)}"}

def create_researcher_agent():
    """Create a specialized Researcher Agent for deep dives into documentation and web search."""
    instruction = """You are a specialized Researcher Agent for the Child Welfare Training system.
Your primary goal is to find accurate, detailed information using the available tools.

Use search_documents for:
- Texas Department of Family & Protective Services (DFPS) specific policies, procedures, and manuals.
- Legal requirements under Texas Family Code 261.101 through 261.110.

Use web_search for:
- Broad Federal, State, and local laws.
- Real-time updates, news, and external reports on child welfare.

Always prioritize search_documents for Texas-specific DFPS queries.
Summarize your findings clearly for the Orchestrator."""

    return Agent(
        name="Researcher",
        model="gemini-2.5-flash",
        instruction=instruction,
        tools=[search_documents, web_search]
    )

def create_reviewer_agent():
    """Create a specialized Reviewer Agent to validate safety and compliance."""
    instruction = """You are a specialized Reviewer Agent. Your role is to validate responses against safety protocols and legal guidelines.
    You check if the information provided is consistent with mandatory reporting laws in Texas and safety guidelines.
    
    If you detect inaccuracies or potential safety violations, provide corrections.
    If the information is safe and accurate, confirm it."""
    
    return Agent(
        name="Reviewer",
        model="gemini-2.5-flash",
        instruction=instruction,
        tools=[search_documents]
    )

def create_customer_chatbot_agent():
    """Create the ChildWelfare Training chatbot agent with intelligent RAG and web search tool selection."""
    researcher = create_researcher_agent()
    reviewer = create_reviewer_agent()
    instruction = """You are a helpful Child Welfare training support chatbot assistant with access to three tools:
1. search_documents - Searches the Texas Department of Family & Protective Services (policies, procedures, FAQs)
2. web_search - Searches the internet for real-time information
3. ingest_local_file - Ingests a local file (.txt, .md, .pdf) into the knowledge base

INTELLIGENT TOOL SELECTION STRATEGY:

Use search_documents (RAG) for questions about:
- Reporting abuse, neglect, and exploitation of a child in Texas
- Mandatory reporting in Texas
- Contact information for DFPS
- Notes, files, or documents for reporting
- False reporting
- Good faith reporter
- Requirements under Texas Family Code 261.101 through 261.110

Use web_search for questions about:
- Federal, State, and local laws and policies on child abuse and neglect
- Mandatory reporting of child abuse and neglect in Texas
- Data and Reports on child abuse and neglect
- Texas child centered care
- Child safety and prevention
- Adoption and foster care
- Child Investigations
- Child Services

DECISION LOGIC:
- Read the question carefully
- Determine if it's about OUR company/services → Use search_documents first
- If it needs current/external information → Use web_search
- If question is ambiguous, try search_documents first, then web_search if needed
- NEVER make up information - always cite sources

RESPONSE GUIDELINES:
- Be friendly, professional, and helpful
- Provide accurate information based on search results
- Cite where information came from (knowledge base or web source)
- If you find relevant documents, quote key information
- If you cannot find information, be honest about it
- Suggest alternatives if the answer isn't available

Example question routing:
Q: "What is Statutory Timeframe and Urgency?" → Use search_documents (DFPS policy)
Q: "What is the latest Child abuse and neglect news?" → Use web_search (real-time info)
Q: "Who has the Professional Liability and Scope of Duty?" → Use search_documents (DFPS procedure)
Q: "What are the Legal Standards for Reporting Child abuse and neglect" → Use web_search (external knowledge)
"""

    agent = Agent(
        name="training_support_agent",
        model="gemini-2.5-flash",
        instruction=instruction,
        tools=[researcher, reviewer, add_document_to_rag, ingest_from_github, ingest_local_file]
    )

    return agent


async def run_chatbot(agent, message: str, user_id: str = "customer1", session_id: str = "session1"):
    """
    Run the chatbot agent with conversation memory.

    Args:
        agent: The chatbot agent
        message: User message
        user_id: User identifier
        session_id: Session identifier for conversation memory
    """
    global global_session_service

    # Create or get session
    try:
        await global_session_service.create_session(
            app_name="training_chatbot",
            user_id=user_id,
            session_id=session_id
        )
    except:
        pass  # Session already exists

    # Create runner
    runner = Runner(
        agent=agent,
        app_name="training_chatbot",
        session_service=global_session_service
    )

    print(f"\n{'='*60}")
    print(f"User: {message}")
    print(f"{'='*60}\n")
    print("Agent: ", end="", flush=True)

    # Create message content
    message_content = types.Content(
        role="user",
        parts=[types.Part(text=message)]
    )

    # Run agent and collect response
    response_text = ""
    event_count = 0
    max_events = 25

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message_content
    ):
        event_count += 1

        if hasattr(event, 'content') and event.content:
            if hasattr(event.content, 'parts') and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
                        print(part.text, end='', flush=True)

        if event_count >= max_events:
            print("\n(Reached max events limit)")
            break

    print(f"\n{'='*60}\n")
    return response_text


async def main():
    """Main function to test the training chatbot agent."""

    print("=" * 60)
    print("Google ADK Training Chatbot Agent")
    print("=" * 60)
    print()

    # Initialize RAG system
    print("Initializing FAISS RAG system...")
    initialize_rag_system()
    print()

    # Add sample documents to knowledge base
    print("Ingesting txdfps.pdf into knowledge base...")
    ingest_result = ingest_local_file("txdfps.pdf")
    print(f"  • {ingest_result['message']}")

    print("Adding additional sample documents to knowledge base...")
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
        result = add_document_to_rag(doc["content"], doc["metadata"])
        print(f"  • {result['message']}")
    print()

    # Create chatbot agent
    print("Creating ChildWelfare Training chatbot agent...")
    agent = create_customer_chatbot_agent()
    print("✓ Agent created successfully")
    print()

    # Test conversations
    print("=" * 60)
    print("Testing Training Chatbot")
    print("=" * 60)
    print()

    test_queries = [
	"What is Statutory Timeframe and Urgency?",
	"What is the latest Child abuse and neglect news?",
	"Who has the Professional Liability and Scope of Duty?",
	"What are the Legal Standards for Reporting Child abuse and neglect",
    ]

    for query in test_queries:
        await run_chatbot(agent, query)

    print("\n" + "=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

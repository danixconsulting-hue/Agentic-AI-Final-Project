#streamlit_ui.py

"""
Streamlit UI for Child Welfare Training Chatbot Agent

Simple and intuitive interface for chatting with the chatbot.
Can connect to local FastAPI or Cloud Run deployment.
"""

import streamlit as st
import requests
import json
from datetime import datetime
from typing import Optional
import os

# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="Child Welfare Training Chatbot",
    page_icon="👪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# Styling
# ============================================================================

st.markdown("""
<style>
    .main {
        padding: 0rem 1rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd !important;
        border-left: 4px solid #2196F3;
        color: #000000 !important;
    }
    .assistant-message {
        background-color: #ffffff !important;
        border-left: 4px solid #4CAF50;
        color: #000000 !important;
    }
    .error-message {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        color: #000000 !important;
    }
    .info-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.85rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }
    .rag-badge {
        background-color: #c8e6c9;
        color: #1b5e20;
    }
    .web-badge {
        background-color: #bbdefb;
        color: #0d47a1;
    }
    .orchestrator-badge {
        background-color: #e1bee7;
        color: #4a148c;
    }
    .researcher-badge {
        background-color: #b2ebf2;
        color: #006064;
    }
    .reviewer-badge {
        background-color: #ffe0b2;
        color: #e65100;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# Session State Initialization
# ============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = f"streamlit_session_{datetime.now().timestamp()}"

if "api_url" not in st.session_state:
    st.session_state.api_url = "http://localhost:8000"

if "connected" not in st.session_state:
    st.session_state.connected = False

# ============================================================================
# Sidebar Configuration
# ============================================================================

with st.sidebar:
    st.title("⚙️ Configuration")

    # API Configuration
    st.subheader("🌐 API Connection")

    api_option = st.radio(
        "Select API location:",
        ["Local (localhost)", "Cloud Run", "Custom URL"]
    )

    if api_option == "Local (localhost)":
        st.session_state.api_url = "http://localhost:8000"
        st.info("Using local API at http://localhost:8000")

    elif api_option == "Cloud Run":
        cloud_url = st.text_input(
            "Cloud Run URL",
            placeholder="https://your-project.run.app",
            help="Enter your Cloud Run deployment URL"
        )
        if cloud_url:
            st.session_state.api_url = cloud_url.rstrip("/")

    else:
        custom_url = st.text_input(
            "Custom API URL",
            value=st.session_state.api_url,
            help="Enter custom API URL"
        )
        if custom_url:
            st.session_state.api_url = custom_url.rstrip("/")

    # Test Connection
    if st.button("🔌 Test Connection", use_container_width=True):
        try:
            response = requests.get(f"{st.session_state.api_url}/health", timeout=5)
            if response.status_code == 200:
                st.session_state.connected = True
                data = response.json()
                st.success("✓ Connected!")
                st.write(f"Status: {data['status']}")
                st.write(f"Active sessions: {data['active_sessions']}")
            else:
                st.session_state.connected = False
                st.error(f"✗ Error: Status {response.status_code}")
        except Exception as e:
            st.session_state.connected = False
            st.error(f"✗ Connection failed: {str(e)}")

    st.divider()

    # Session Information
    st.subheader("📋 Session Info")
    st.write(f"**Session ID:** `{st.session_state.session_id}`")
    st.write(f"**Messages:** {len(st.session_state.messages)}")
    st.write(f"**Connected:** {'✓ Yes' if st.session_state.connected else '✗ No'}")

    st.divider()

    # Knowledge Base Management
    st.subheader("📚 Knowledge Base")

    with st.expander("Add Document"):
        doc_content = st.text_area(
            "Document content:",
            height=100,
            placeholder="Enter document content..."
        )
        doc_category = st.text_input(
            "Category:",
            placeholder="e.g., policy, shipping, support"
        )

        if st.button("➕ Add Document", use_container_width=True):
            if not doc_content:
                st.error("Please enter document content")
            elif not st.session_state.connected:
                st.error("API not connected")
            else:
                try:
                    response = requests.post(
                        f"{st.session_state.api_url}/add-document",
                        json={
                            "content": doc_content,
                            "metadata": {"category": doc_category}
                        },
                        timeout=10
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"✓ {data['message']}")
                    else:
                        st.error(f"Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Failed to add document: {str(e)}")

    with st.expander("Search Knowledge Base"):
        search_query = st.text_input(
            "Search query:",
            placeholder="What do you want to search for?"
        )

        if st.button("🔍 Search", use_container_width=True):
            if not search_query:
                st.error("Please enter a search query")
            elif not st.session_state.connected:
                st.error("API not connected")
            else:
                try:
                    response = requests.post(
                        f"{st.session_state.api_url}/search",
                        json={"query": search_query, "top_k": 3},
                        timeout=10
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.write(f"**Found {len(data['results'])} results:**")
                        for i, result in enumerate(data['results'], 1):
                            st.write(f"{i}. {result['content'][:100]}...")
                    else:
                        st.error(f"Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Search failed: {str(e)}")

    st.divider()

    # Active Agents
    st.subheader("🤖 Active Agents")
    st.markdown("- 👔 **Orchestrator**: `Online`")
    st.markdown("- 🔍 **Researcher**: `Online`")
    st.markdown("- ⚖️ **Reviewer**: `Online`")
    st.divider()

    # Clear Chat
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.success("Chat history cleared")
        st.rerun()

# ============================================================================
# Main Content
# ============================================================================

# Header
col1, col2 = st.columns([4, 1])
with col1:
    st.title("👪 Child Welfare Training Chatbot")
    st.caption("Google ADK-powered customer support with RAG and web search")

with col2:
    if st.session_state.connected:
        st.success("🟢 Connected")
    else:
        st.warning("🔴 Not Connected")

st.divider()

# Chat Messages Display
chat_container = st.container()

with chat_container:
    for i, message in enumerate(st.session_state.messages):
        if message["role"] == "user":
            st.markdown(
                f"""
                <div class="chat-message user-message">
                    <strong>You:</strong> {message["content"]}
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            badges = []
            
            # Agent Badge
            if message.get("agent"):
                agent_class = f"{message['agent'].lower()}-badge"
                badges.append(f'<span class="info-badge {agent_class}">{message["agent"]}</span>')
            
            # Tool Badge
            if message.get("tool_used"):
                tool_class = "rag-badge" if message["tool_used"] == "RAG" else "web-badge"
                badges.append(f'<span class="info-badge {tool_class}">{message["tool_used"]}</span>')

            st.markdown(
                f"""
                <div class="chat-message assistant-message">
                    <strong>Assistant:</strong> {" ".join(badges)}
                    <br>{message["content"]}
                </div>
                """,
                unsafe_allow_html=True
            )

# Input Area
st.divider()
col1, col2 = st.columns([4, 1])

with col1:
    user_input = st.text_input(
        "Message:",
        placeholder="Ask me anything about our services...",
        label_visibility="collapsed"
    )

with col2:
    send_button = st.button("📤 Send", use_container_width=True)

# Handle Message Sending
if send_button and user_input:
    if not st.session_state.connected:
        st.error("❌ API not connected. Please configure connection in sidebar.")
    else:
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        # Get response from API
        try:
            with st.spinner("🔄 Getting response..."):
                response = requests.post(
                    f"{st.session_state.api_url}/chat",
                    json={
                        "user_id": "streamlit_user",
                        "session_id": st.session_state.session_id,
                        "message": user_input
                    },
                    timeout=30
                )

            if response.status_code == 200:
                data = response.json()
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data["response"],
                    "tool_used": data.get("tool_used"),
                    "agent": data.get("agent")
                })
                st.rerun()
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("detail", f"Status {response.status_code}")
                st.error(f"❌ Error: {error_msg}")

        except requests.exceptions.Timeout:
            st.error("❌ Request timeout. Please try again.")
        except requests.exceptions.ConnectionError:
            st.error("❌ Connection error. Please check the API URL.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# ============================================================================
# Info Section
# ============================================================================

if len(st.session_state.messages) == 0:
    st.info("""
    ### Welcome to Child Welfare Training Chatbot! 🧒

    This assistant uses a **Multi-Agent Architecture** powered by Google ADK and Gemini to provide intelligent guidance on Child Abuse and Neglect resources.

    **Features:**
    - 🧠 **Training Intelligence** - Automatically chooses between training manuals (knowledge Base) and current regulations (web)
    - 📚 **RAG System** - Semantic search over specialized child welfare knowledge bases
    - 👔 **Orchestrator Agent** - Manages conversation flow and delegates tasks.
    - 🔍 **Researcher Agent** - Deep-dives into training manuals and legal regulations using RAG.
    - ⚖️ **Reviewer Agent** - Validates responses against safety protocols and guidelines.
    - 🌐 **Web Search** - Real-time external information
    - 💬 **Conversation Memory** - Remembers previous messages

    **How to Use:**
    1. Configure your API connection in the sidebar
    2. Test the connection
    3. Start asking questions!

    **Example Questions:**
    - "What is DFPS in Texas?"
    - "What are the Reporting Channels for Child Abuse?"
    - "What are the Legal Standards for Reporting Child neglect and abuse?"
    - "What's the Professional Liability of social workers?
    """)

# ============================================================================
# Footer
# ============================================================================

st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("📖 [Documentation](https://github.com/your-repo)")

with col2:
    st.caption("🐛 [Report Issues](https://github.com/your-repo/issues)")

with col3:
    st.caption("💬 Chat Sessions: " + str(len(st.session_state.messages) // 2))

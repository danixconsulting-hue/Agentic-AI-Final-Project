# Dockerfile

# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Add FastAPI and Uvicorn to requirements
RUN echo "fastapi>=0.115.0" >> requirements.txt && \
    echo "uvicorn>=0.27.0" >> requirements.txt && \
    echo "pydantic>=2.5.0" >> requirements.txt && \
    echo "python-multipart>=0.0.6" >> requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY childwelfare_agent.py .
COPY fastapi_app.py .

# Create directories for service account
RUN mkdir -p /app/credentials

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE
ENV GOOGLE_CLOUD_PROJECT=project-176c7d8a-2df4-4d02-bc0
ENV GOOGLE_CLOUD_LOCATION=us-central1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run FastAPI app with Uvicorn
CMD ["uvicorn", "fastapi_app:app", "--host", "0.0.0.0", "--port", "8080"]

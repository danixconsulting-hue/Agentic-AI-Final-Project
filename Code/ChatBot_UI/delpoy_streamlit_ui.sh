#!/bin/bash

################################################################################
#                  Google Cloud Build Deployment Script                        #
#              Streamlit UI for Child Welfare Training Chatbot Agent           #
#                    NO LOCAL DOCKER NEEDED                                    #
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Configuration
# ============================================================================

SERVICE_NAME="${SERVICE_NAME:-training-chatbot-ui}"
GCP_PROJECT="${GCP_PROJECT:-project-176c7d8a-2df4-4d02-bc0}"
GCP_REGION="${GCP_REGION:-us-central1}"
IMAGE_NAME="${IMAGE_NAME:-training-chatbot-ui}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Google Cloud Build Deployment - Streamlit UI                ║${NC}"
echo -e "${BLUE}║              No Local Docker Required                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Pre-Deployment Checks
# ============================================================================

echo -e "${YELLOW}[1/5] Checking prerequisites...${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}✗ gcloud CLI not found. Please install Google Cloud SDK.${NC}"
    echo "  Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if service account key exists
if [ ! -f "service-account-key.json" ]; then
    echo -e "${YELLOW}⚠ service-account-key.json not found in current directory${NC}"
    echo "  This is optional - Cloud Build can use default service account"
else
    echo -e "${GREEN}✓ Service account key found${NC}"
fi

# Check if required files exist
if [ ! -f "streamlit_ui.py" ]; then
    echo -e "${RED}✗ streamlit_ui.py not found${NC}"
    exit 1
fi

if [ ! -f "Dockerfile.streamlit" ]; then
    echo -e "${RED}✗ Dockerfile.streamlit not found${NC}"
    exit 1
fi

if [ ! -f "cloudbuild-streamlit.yaml" ]; then
    echo -e "${RED}✗ cloudbuild-streamlit.yaml not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites found${NC}"
echo ""

# ============================================================================
# Configuration Display
# ============================================================================

echo -e "${YELLOW}[2/5] Deployment Configuration${NC}"
echo "  Service Name:    $SERVICE_NAME"
echo "  GCP Project:     $GCP_PROJECT"
echo "  Region:          $GCP_REGION"
echo "  Image Name:      $IMAGE_NAME"
echo "  Image Registry:  gcr.io/$GCP_PROJECT/$IMAGE_NAME"
echo ""
echo -e "${BLUE}✓ Using Cloud Build (no local Docker needed!)${NC}"
echo ""

# ============================================================================
# Set GCP Project
# ============================================================================

echo -e "${YELLOW}[3/5] Setting GCP project...${NC}"
gcloud config set project "$GCP_PROJECT"
gcloud auth configure-docker gcr.io
echo -e "${GREEN}✓ GCP project configured${NC}"
echo ""

# ============================================================================
# Enable Required APIs
# ============================================================================

echo -e "${YELLOW}[3.5/5] Enabling required APIs...${NC}"

echo "  Enabling Cloud Build API..."
gcloud services enable cloudbuild.googleapis.com --quiet

echo "  Enabling Cloud Run API..."
gcloud services enable run.googleapis.com --quiet

echo "  Enabling Container Registry API..."
gcloud services enable containerregistry.googleapis.com --quiet

echo -e "${GREEN}✓ All APIs enabled${NC}"
echo ""

# ============================================================================
# Submit Build to Cloud Build
# ============================================================================

echo -e "${YELLOW}[4/5] Submitting build to Google Cloud Build...${NC}"
echo "  This will build the Streamlit Docker image in the cloud"
echo "  Build may take 2-5 minutes..."
echo ""

BUILD_ID=$(gcloud builds submit . \
    --config=cloudbuild-streamlit.yaml \
    --substitutions "_SERVICE_NAME=$SERVICE_NAME,_REGION=$GCP_REGION" \
    --format='value(id)' \
    --no-source 2>/dev/null || gcloud builds submit . --config=cloudbuild-streamlit.yaml --format='value(id)')

if [ -z "$BUILD_ID" ]; then
    echo -e "${RED}✗ Build submission failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Build submitted successfully${NC}"
echo "  Build ID: $BUILD_ID"
echo ""

# ============================================================================
# Wait for Build to Complete
# ============================================================================

echo -e "${YELLOW}Waiting for build to complete...${NC}"
echo "  You can monitor progress with:"
echo "  gcloud builds log $BUILD_ID --stream"
echo ""

gcloud builds wait "$BUILD_ID"

BUILD_STATUS=$(gcloud builds describe "$BUILD_ID" --format='value(status)')

if [ "$BUILD_STATUS" != "SUCCESS" ]; then
    echo -e "${RED}✗ Build failed with status: $BUILD_STATUS${NC}"
    echo "  View logs: gcloud builds log $BUILD_ID"
    exit 1
fi

echo -e "${GREEN}✓ Build completed successfully${NC}"
echo ""

# ============================================================================
# Get Service URL
# ============================================================================

echo -e "${YELLOW}[5/5] Retrieving service URL...${NC}"

# Wait a moment for Cloud Run to stabilize
sleep 5

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --platform managed \
    --region $GCP_REGION \
    --format 'value(status.url)' 2>/dev/null || echo "")

if [ -z "$SERVICE_URL" ]; then
    echo -e "${YELLOW}⚠ Could not retrieve service URL immediately${NC}"
    echo "  Check Cloud Run console in a moment:"
    echo "  https://console.cloud.google.com/run"
else
    echo -e "${GREEN}✓ Service deployed successfully${NC}"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                   🚀 BUILD & DEPLOYMENT SUCCESS              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ -n "$SERVICE_URL" ]; then
    echo -e "${BLUE}Service Details:${NC}"
    echo "  Name:    $SERVICE_NAME"
    echo "  URL:     $SERVICE_URL"
    echo "  Region:  $GCP_REGION"
    echo ""
fi

# ============================================================================
# Next Steps
# ============================================================================

echo -e "${BLUE}Next Steps:${NC}"
echo ""

if [ -n "$SERVICE_URL" ]; then
    echo "1. Open Streamlit UI in browser:"
    echo "   $SERVICE_URL"
    echo ""
    echo "2. In the Streamlit UI configuration:"
    echo "   - Select 'Cloud Run' API option"
    echo "   - For the FastAPI service URL, enter the API service URL"
    echo "   - For example: https://training-chatbot.run.app"
    echo ""
    echo "3. Find your API service URL:"
    echo "   gcloud run services list --platform managed"
    echo ""
else
    echo "1. Check Cloud Run console:"
    echo "   https://console.cloud.google.com/run"
    echo ""
    echo "2. Find your service URL and follow steps above"
fi

echo ""
echo "4. View build logs:"
echo "   gcloud builds log $BUILD_ID"
echo ""
echo "5. View service logs:"
echo "   gcloud run logs read $SERVICE_NAME --platform managed --region $GCP_REGION --limit 50"
echo ""
echo "6. Update service:"
echo "   ./deploy_streamlit_ui.sh"
echo ""
echo "7. Delete service:"
echo "   gcloud run services delete $SERVICE_NAME --platform managed --region $GCP_REGION"
echo ""

echo -e "${BLUE}Environment Variables:${NC}"
echo "  To set environment variables during deployment, edit the"
echo "  cloudbuild-streamlit.yaml file or use:"
echo "  gcloud run services update $SERVICE_NAME --update-env-vars KEY=VALUE"
echo ""

echo -e "${BLUE}Streaming Logs:${NC}"
if [ -n "$SERVICE_URL" ]; then
    echo "  Real-time logs:"
    echo "  gcloud run logs read $SERVICE_NAME --follow --platform managed --region $GCP_REGION"
fi
echo ""

echo -e "${GREEN}✨ Your Streamlit UI is now deployed to Google Cloud!${NC}"
echo ""

################################################################################
#                            ADDITIONAL INFORMATION                            #
################################################################################

echo -e "${BLUE}Configuration Guide:${NC}"
echo ""
echo "When using the Streamlit UI, configure it as follows:"
echo ""
echo "1. Connection Type: Select 'Cloud Run'"
echo ""
echo "2. API URL: Enter your FastAPI service URL (from deploy_cloud_build.sh)"
echo "   Example: https://trainingcd fi-chatbot.run.app"
echo ""
echo "3. Test Connection: Click 'Test Connection' to verify"
echo ""

echo -e "${BLUE}Streamlit UI Features:${NC}"
echo "  ✓ Real-time chat with Google ADK chatbot"
echo "  ✓ Conversation memory and session management"
echo "  ✓ Document upload and knowledge base search"
echo "  ✓ Tool selection visualization (RAG vs Web Search)"
echo "  ✓ Connection status monitoring"
echo "  ✓ Multiple API endpoint support (Local, Cloud Run, Custom)"
echo ""

echo -e "${BLUE}Architecture:${NC}"
echo "  Streamlit UI (Cloud Run) <---> FastAPI Backend (Cloud Run)"
echo "                                      |"
echo "                                      ├-- Google ADK Agent"
echo "                                      ├-- FAISS RAG Index"
echo "                                      └-- Vertex AI APIs"
echo ""

################################################################################

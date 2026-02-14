#!/bin/bash

# ==========================================
# CrawlWess API Usage Examples (cURL)
# ==========================================

# 1. Base Configuration
# ---------------------
HOST="http://localhost:8000"
# NOTE: Ensure this matches the ADMIN_PASSWORD you set in your environment variables!
PASSWORD="${ADMIN_PASSWORD:-admin123}" 
USERNAME="admin" # Username can be anything, only password is verified

echo "Using Host: $HOST"
echo "Using Password: **** (from env ADMIN_PASSWORD or default)"

# 2. Public Endpoints
# -------------------
echo ""
echo ">>> 1. Health Check (GET /)"
curl -s -X GET "$HOST/" | python3 -m json.tool

# 3. Protected Debug Endpoints
# ----------------------------
# These endpoints require Basic Authentication

echo ""
echo ">>> 2. Trigger RSS Fetch (POST /debug/fetch)"
curl -s -X POST "$HOST/debug/fetch" \
     -u "$USERNAME:$PASSWORD" | python3 -m json.tool

echo ""
echo ">>> 3. Trigger Daily Report (POST /debug/report)"
curl -s -X POST "$HOST/debug/report" \
     -u "$USERNAME:$PASSWORD" | python3 -m json.tool

echo ""
echo ">>> 4. Trigger Cleanup (POST /debug/cleanup)"
curl -s -X POST "$HOST/debug/cleanup" \
     -u "$USERNAME:$PASSWORD" | python3 -m json.tool

echo ""
echo ">>> 5. Trigger Full Flow [Fetch -> Report] (POST /debug/full-flow)"
curl -s -X POST "$HOST/debug/full-flow" \
     -u "$USERNAME:$PASSWORD" | python3 -m json.tool

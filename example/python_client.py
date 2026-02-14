import requests
import os
import sys
import time

# Configuration
# ==========================================
# Get config from env or use defaults
HOST = os.getenv("API_HOST", "https://crawlwess-production.up.railway.app/")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "huang@123")
USERNAME = "admin" # Username can be anything, only password is verified

# Helpers
# ==========================================
def print_separator():
    print("-" * 50)

def call_endpoint(method, endpoint, description):
    url = f"{HOST}{endpoint}"
    print(f"\n>>> {description}")
    print(f"Request: {method} {url}")
    
    try:
        if method == "GET":
            response = requests.get(url)
        else:
            # POST with Basic Auth
            response = requests.post(url, auth=(USERNAME, ADMIN_PASSWORD))
            
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response Body: {response.json()}")
        except:
            print(f"Response Body: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    print_separator()

# Main Execution
# ==========================================
if __name__ == "__main__":
    print(f"Starting API Tests against {HOST}")
    print(f"Using Admin Password: {'*' * len(ADMIN_PASSWORD)}")
    print_separator()

    # 1. Health Check
    call_endpoint("GET", "/", "Checking API Health")

    # 2. Trigger RSS Fetch
    # This will trigger the background job to fetch RSS feeds
    call_endpoint("POST", "/debug/fetch", "Triggering RSS Fetch Job")

    # 3. Trigger Daily Report
    # This will trigger the generation and sending of the daily report
    call_endpoint("POST", "/debug/report", "Triggering Daily Report Job")

    # 4. Trigger Cleanup
    # This will trigger the cleanup of old files
    call_endpoint("POST", "/debug/cleanup", "Triggering Cleanup Job")

    # 5. Trigger Full Flow
    # This triggers Fetch followed by Report (note: execution might be parallel depending on scheduler)
    call_endpoint("POST", "/debug/full-flow", "Triggering Full Flow (Fetch + Report)")

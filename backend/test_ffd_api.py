#!/usr/bin/env python3
"""
Test script for FFD API integration
Run this to test the FFD API connection and response parsing
"""

import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# FFD API Configuration
FFD_TOKEN = "PM_PORT_API_1a2b9c6d5e4f"
FFD_API_URL = "https://ffd.pmd.gov.pk/api/pm-dashboard"

def test_ffd_api():
    """Test the FFD API directly"""
    print("=" * 60)
    print("FFD API TEST SCRIPT")
    print("=" * 60)
    print(f"API URL: {FFD_API_URL}")
    print(f"API Token: {FFD_TOKEN}")
    print(f"Test Time: {datetime.now().isoformat()}")
    print("=" * 60)
    
    try:
        # Prepare request data
        request_data = {"API_KEY": FFD_TOKEN}
        print(f"Request Data: {request_data}")
        
        # Make the API request
        print("\nSending POST request to FFD API...")
        response = requests.post(FFD_API_URL, data=request_data, timeout=30)
        
        # Log response details
        print(f"\nResponse Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Content Type: {response.headers.get('Content-Type', 'Not specified')}")
        print(f"Response Content Length: {len(response.content)} bytes")
        
        # Check if request was successful
        if response.status_code == 200:
            print("✅ API request successful!")
        else:
            print(f"❌ API request failed with status: {response.status_code}")
        
        # Log raw response content
        print(f"\n" + "="*60)
        print("RAW RESPONSE CONTENT:")
        print("="*60)
        print(response.text)
        print("="*60)
        
        # Try to parse as JSON
        try:
            json_data = response.json()
            print("\n✅ Successfully parsed as JSON!")
            print("\nFORMATTED JSON RESPONSE:")
            print("="*60)
            print(json.dumps(json_data, indent=2, ensure_ascii=False))
            print("="*60)
            
            # Analyze the structure
            print(f"\nJSON STRUCTURE ANALYSIS:")
            print(f"Data type: {type(json_data)}")
            if isinstance(json_data, dict):
                print(f"Top-level keys: {list(json_data.keys())}")
                
                if 'data' in json_data:
                    data_array = json_data['data']
                    print(f"Data array length: {len(data_array)}")
                    
                    if data_array:
                        print(f"First item keys: {list(data_array[0].keys())}")
                        print(f"First item: {json.dumps(data_array[0], indent=2, ensure_ascii=False)}")
                        
                        # List all location names
                        names = [item.get('name', 'Unknown') for item in data_array]
                        print(f"\nAll location names: {names}")
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse as JSON: {e}")
            print("Response might not be valid JSON")
        
        return response
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    return None

def test_flask_backend():
    """Test the Flask backend health"""
    print("\n" + "="*60)
    print("FLASK BACKEND TEST")
    print("="*60)
    
    backend_url = "http://localhost:5000"
        
    try:
        # Test health endpoint
        response = requests.get(f"{backend_url}/api/health", timeout=10)
        print(f"Health check status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Flask backend is running!")
            health_data = response.json()
            print(f"Health data: {json.dumps(health_data, indent=2)}")
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask backend. Make sure it's running on localhost:5000")
    except Exception as e:
        print(f"❌ Backend test error: {e}")

if __name__ == "__main__":
    # Test FFD API directly
    test_ffd_api()
    
    # Test Flask backend
    test_flask_backend()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

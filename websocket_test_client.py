#!/usr/bin/env python3
"""
WebSocket Test Client for Guardian AI Ingest System

This script demonstrates how to connect to the Guardian AI WebSocket
ingest endpoint and send test data.

Usage:
    python websocket_test_client.py

Requirements:
    pip install websockets asyncio
"""

import asyncio
import websockets
import json
import sys
from datetime import datetime, timezone


# Configuration
WEBSOCKET_URL = "ws://localhost:8000/ws/ingest/{child_hash}/"
CHILD_HASH = "9KKm7qf2n9OjpI3K"  # Replace with actual child_hash


async def test_direct_connection():
    """
    Test the direct connection endpoint where child_hash is in the URL.
    """
    url = WEBSOCKET_URL.format(child_hash=CHILD_HASH)
    print(f"\n{'='*60}")
    print(f"Testing Direct Connection")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    try:
        async with websockets.connect(url) as websocket:
            print("✓ Connected to WebSocket")
            
            # Receive connection acknowledgment
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            # Test 1: Send location data
            print("Test 1: Sending location data...")
            location_message = {
                "type": "location",
                "data": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }
            }
            await websocket.send(json.dumps(location_message))
            print(f"→ Sent: {json.dumps(location_message, indent=2)}")
            
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            # Test 2: Send screen time data
            print("Test 2: Sending screen time data...")
            screen_time_message = {
                "type": "screen_time",
                "data": {
                    "date": datetime.now().date().isoformat(),
                    "total_screen_time": 7200,  # 2 hours in seconds
                    "app_wise_data": {
                        "com.example.app1": {
                            "10": 3600,  # 1 hour at 10am
                            "11": 1800   # 30 minutes at 11am
                        },
                        "com.example.app2": {
                            "10": 1800   # 30 minutes at 10am
                        }
                    }
                }
            }
            await websocket.send(json.dumps(screen_time_message))
            print(f"→ Sent: {json.dumps(screen_time_message, indent=2)}")
            
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            # Test 3: Send site access logs
            print("Test 3: Sending site access logs...")
            site_access_message = {
                "type": "site_access",
                "data": {
                    "logs": [
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "url": "https://example.com",
                            "accessed": True
                        },
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "url": "https://blocked-site.com",
                            "accessed": False
                        }
                    ]
                }
            }
            await websocket.send(json.dumps(site_access_message))
            print(f"→ Sent: {json.dumps(site_access_message, indent=2)}")
            
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            # Test 4: Send invalid message to test error handling
            print("Test 4: Sending invalid message (testing error handling)...")
            invalid_message = {
                "type": "invalid_type",
                "data": {}
            }
            await websocket.send(json.dumps(invalid_message))
            print(f"→ Sent: {json.dumps(invalid_message, indent=2)}")
            
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            print("✓ All tests completed successfully!")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ Connection failed with status code: {e.status_code}")
        print(f"  This likely means the child_hash '{CHILD_HASH}' does not exist.")
        print(f"  Please create a child with this hash or update CHILD_HASH in the script.")
    except websockets.exceptions.WebSocketException as e:
        print(f"✗ WebSocket error: {e}")
    except ConnectionRefusedError:
        print(f"✗ Connection refused. Is the server running at {url}?")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


async def test_auth_connection():
    """
    Test the authentication flow endpoint where child_hash is sent after connection.
    """
    url = "ws://localhost:8000/ws/ingest-auth/"
    print(f"\n{'='*60}")
    print(f"Testing Authentication Flow")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    try:
        async with websockets.connect(url) as websocket:
            print("✓ Connected to WebSocket")
            
            # Receive auth request
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            # Send authentication
            print("Authenticating...")
            auth_message = {
                "type": "auth",
                "child_hash": CHILD_HASH
            }
            await websocket.send(json.dumps(auth_message))
            print(f"→ Sent: {json.dumps(auth_message, indent=2)}")
            
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            # Send location data after authentication
            print("Sending location data after authentication...")
            location_message = {
                "type": "location",
                "data": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }
            }
            await websocket.send(json.dumps(location_message))
            print(f"→ Sent: {json.dumps(location_message, indent=2)}")
            
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            print("✓ Authentication flow test completed successfully!")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ Connection failed with status code: {e.status_code}")
    except websockets.exceptions.WebSocketException as e:
        print(f"✗ WebSocket error: {e}")
    except ConnectionRefusedError:
        print(f"✗ Connection refused. Is the server running at {url}?")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


async def test_continuous_sending():
    """
    Test sending multiple messages in quick succession to simulate
    continuous data streaming from a mobile client.
    """
    url = WEBSOCKET_URL.format(child_hash=CHILD_HASH)
    print(f"\n{'='*60}")
    print(f"Testing Continuous Data Streaming")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    try:
        async with websockets.connect(url) as websocket:
            print("✓ Connected to WebSocket")
            
            # Receive connection acknowledgment
            response = await websocket.recv()
            print(f"← Server: {response}\n")
            
            # Send 10 location updates rapidly
            print("Sending 10 location updates...")
            for i in range(10):
                location_message = {
                    "type": "location",
                    "data": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "latitude": 40.7128 + (i * 0.001),  # Slightly different each time
                        "longitude": -74.0060 + (i * 0.001)
                    }
                }
                await websocket.send(json.dumps(location_message))
                print(f"→ Sent location #{i+1}")
                
                # Receive acknowledgment
                response = await websocket.recv()
                response_data = json.loads(response)
                if response_data.get('type') == 'ack':
                    print(f"  ✓ Acknowledged")
                else:
                    print(f"  ✗ Error: {response}")
                
                # Small delay to simulate real-world timing
                await asyncio.sleep(0.1)
            
            print("\n✓ Continuous streaming test completed successfully!")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


async def test_reconnection_strategy():
    """
    Test reconnection with exponential backoff strategy.
    This simulates what a mobile client should do when connection is lost.
    """
    url = WEBSOCKET_URL.format(child_hash=CHILD_HASH)
    print(f"\n{'='*60}")
    print(f"Testing Reconnection Strategy")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    max_retries = 5
    base_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            print(f"Connection attempt {attempt + 1}/{max_retries}...")
            
            async with websockets.connect(url) as websocket:
                print("✓ Connected successfully!")
                
                # Receive acknowledgment
                response = await websocket.recv()
                print(f"← {response}\n")
                
                # Send a test message
                message = {
                    "type": "location",
                    "data": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "latitude": 40.7128,
                        "longitude": -74.0060
                    }
                }
                await websocket.send(json.dumps(message))
                response = await websocket.recv()
                print(f"← {response}\n")
                
                print("✓ Reconnection strategy test completed!")
                return  # Success, exit
                
        except (websockets.exceptions.WebSocketException, ConnectionRefusedError) as e:
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            print(f"✗ Connection failed: {e}")
            
            if attempt < max_retries - 1:
                print(f"  Retrying in {delay} seconds...\n")
                await asyncio.sleep(delay)
            else:
                print(f"  Max retries reached. Would fall back to HTTP endpoint.")


def print_usage():
    """Print usage instructions."""
    print("\n" + "="*60)
    print("Guardian AI WebSocket Test Client")
    print("="*60)
    print("\nThis script tests the WebSocket ingest endpoints.")
    print(f"\nCurrent configuration:")
    print(f"  Server: localhost:8000")
    print(f"  Child Hash: {CHILD_HASH}")
    print("\nBefore running:")
    print("  1. Ensure the Django server is running:")
    print("     python manage.py runserver")
    print("     or: daphne -b 0.0.0.0 -p 8000 guardianAI.asgi:application")
    print(f"  2. Create a child with hash '{CHILD_HASH}' or update CHILD_HASH")
    print("\nAvailable tests:")
    print("  1. Direct connection (child_hash in URL)")
    print("  2. Authentication flow")
    print("  3. Continuous data streaming")
    print("  4. Reconnection strategy")
    print("="*60 + "\n")


async def main():
    """Run all tests."""
    print_usage()
    
    # Check if websockets module is available
    try:
        import websockets
    except ImportError:
        print("✗ Error: 'websockets' module not found.")
        print("  Install it with: pip install websockets")
        sys.exit(1)
    
    tests = [
        ("Direct Connection Test", test_direct_connection),
        ("Authentication Flow Test", test_auth_connection),
        ("Continuous Streaming Test", test_continuous_sending),
        ("Reconnection Strategy Test", test_reconnection_strategy),
    ]
    
    for test_name, test_func in tests:
        try:
            await test_func()
            await asyncio.sleep(1)  # Brief pause between tests
        except KeyboardInterrupt:
            print("\n\n✗ Tests interrupted by user")
            break
        except Exception as e:
            print(f"\n✗ Test '{test_name}' failed with error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user. Goodbye!")
        sys.exit(0)

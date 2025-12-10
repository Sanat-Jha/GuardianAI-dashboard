"""
Mobile Client Implementation Example with Fallback Strategy

This module demonstrates how a mobile client should implement the WebSocket
connection with HTTP fallback for the Guardian AI ingest system.

Key Features:
- Primary: WebSocket connection for real-time data streaming
- Fallback: HTTP POST endpoint when WebSocket fails
- Automatic reconnection with exponential backoff
- Local data buffering during connection loss
- Seamless switching between WebSocket and HTTP

Usage:
    client = GuardianAIClient(child_hash="abc123", server_url="localhost:8000")
    await client.connect()
    
    # Send data
    await client.send_location(latitude=40.7128, longitude=-74.0060)
    await client.send_screen_time(date="2025-12-10", total_time=3600, app_data={...})
    await client.send_site_access_logs(logs=[...])
"""

import asyncio
import websockets
import json
import aiohttp
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from collections import deque
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GuardianAIClient:
    """
    Guardian AI mobile client with WebSocket primary and HTTP fallback.
    """
    
    def __init__(
        self,
        child_hash: str,
        server_url: str = "localhost:8000",
        use_ssl: bool = False,
        max_buffer_size: int = 1000,
        max_reconnect_attempts: int = 5,
        base_reconnect_delay: float = 1.0
    ):
        """
        Initialize the Guardian AI client.
        
        Args:
            child_hash: Unique identifier for the child
            server_url: Server domain/IP and port (e.g., "localhost:8000")
            use_ssl: Whether to use secure connections (wss/https)
            max_buffer_size: Maximum number of messages to buffer when offline
            max_reconnect_attempts: Max WebSocket reconnection attempts before HTTP fallback
            base_reconnect_delay: Base delay in seconds for exponential backoff
        """
        self.child_hash = child_hash
        self.server_url = server_url
        self.use_ssl = use_ssl
        self.max_buffer_size = max_buffer_size
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_reconnect_delay = base_reconnect_delay
        
        # Connection state
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.connection_mode = "disconnected"  # disconnected, websocket, http
        
        # Message buffer for offline mode
        self.message_buffer: deque = deque(maxlen=max_buffer_size)
        
        # URLs
        ws_protocol = "wss" if use_ssl else "ws"
        http_protocol = "https" if use_ssl else "http"
        self.websocket_url = f"{ws_protocol}://{server_url}/ws/ingest/{child_hash}/"
        self.http_url = f"{http_protocol}://{server_url}/api/ingest/"
        
        # Background tasks
        self._reconnect_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        logger.info(f"Initialized GuardianAIClient for child_hash: {child_hash}")
    
    async def connect(self) -> bool:
        """
        Establish connection to the server.
        Tries WebSocket first, falls back to HTTP mode if that fails.
        
        Returns:
            True if connected (via WebSocket or ready for HTTP), False otherwise
        """
        try:
            await self._connect_websocket()
            return True
        except Exception as e:
            logger.warning(f"WebSocket connection failed: {e}")
            logger.info("Falling back to HTTP mode")
            self.connection_mode = "http"
            return True  # HTTP mode is always "ready"
    
    async def _connect_websocket(self):
        """Internal method to establish WebSocket connection."""
        try:
            logger.info(f"Connecting to WebSocket: {self.websocket_url}")
            self.websocket = await websockets.connect(self.websocket_url)
            
            # Receive connection acknowledgment
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if response_data.get('type') == 'connection_established':
                self.is_connected = True
                self.connection_mode = "websocket"
                logger.info("✓ WebSocket connected successfully")
                
                # Start heartbeat to monitor connection
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                
                # Send any buffered messages
                await self._flush_buffer()
                
                return True
            else:
                raise Exception(f"Unexpected response: {response_data}")
                
        except Exception as e:
            self.is_connected = False
            self.websocket = None
            raise e
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        self.is_connected = False
        self.connection_mode = "disconnected"
        logger.info("Disconnected from server")
    
    async def _send_via_websocket(self, message_type: str, data: Dict[str, Any]) -> bool:
        """
        Send data via WebSocket.
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_connected or not self.websocket:
            return False
        
        try:
            message = {
                "type": message_type,
                "data": data
            }
            
            await self.websocket.send(json.dumps(message))
            
            # Wait for acknowledgment
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if response_data.get('type') == 'ack':
                logger.debug(f"✓ {message_type} acknowledged")
                return True
            elif response_data.get('type') == 'error':
                logger.error(f"Server error: {response_data.get('message')}")
                return False
            else:
                logger.warning(f"Unexpected response: {response_data}")
                return False
                
        except (websockets.exceptions.WebSocketException, asyncio.TimeoutError) as e:
            logger.error(f"WebSocket send failed: {e}")
            self.is_connected = False
            
            # Start reconnection in background
            if not self._reconnect_task:
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())
            
            return False
    
    async def _send_via_http(self, message_type: str, data: Dict[str, Any]) -> bool:
        """
        Send data via HTTP POST fallback.
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Format data for HTTP endpoint
            payload = {
                "child_hash": self.child_hash
            }
            
            if message_type == "screen_time":
                payload["screen_time_info"] = data
            elif message_type == "location":
                payload["location_info"] = data
            elif message_type == "site_access":
                payload["site_access_info"] = data
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.http_url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.debug(f"✓ {message_type} sent via HTTP")
                        return True
                    else:
                        logger.error(f"HTTP error: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"HTTP send failed: {e}")
            return False
    
    async def _send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """
        Send a message via WebSocket or HTTP fallback.
        Buffers the message if both fail.
        
        Returns:
            True if sent successfully, False if buffered
        """
        # Try WebSocket first if connected
        if self.connection_mode == "websocket":
            if await self._send_via_websocket(message_type, data):
                return True
            else:
                # WebSocket failed, switch to HTTP
                logger.info("Switching to HTTP fallback mode")
                self.connection_mode = "http"
        
        # Try HTTP if WebSocket failed or not connected
        if await self._send_via_http(message_type, data):
            return True
        
        # Both failed, buffer the message
        logger.warning("Both WebSocket and HTTP failed, buffering message")
        self._buffer_message(message_type, data)
        return False
    
    def _buffer_message(self, message_type: str, data: Dict[str, Any]):
        """Add a message to the buffer."""
        self.message_buffer.append({
            "type": message_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        logger.debug(f"Buffered message (buffer size: {len(self.message_buffer)})")
    
    async def _flush_buffer(self):
        """Send all buffered messages."""
        if not self.message_buffer:
            return
        
        logger.info(f"Flushing {len(self.message_buffer)} buffered messages...")
        
        while self.message_buffer:
            message = self.message_buffer.popleft()
            success = await self._send_message(message['type'], message['data'])
            
            if not success:
                # Put it back if sending failed
                self.message_buffer.appendleft(message)
                break
            
            await asyncio.sleep(0.1)  # Small delay between messages
        
        if not self.message_buffer:
            logger.info("✓ All buffered messages sent")
    
    async def _reconnect_loop(self):
        """Background task to attempt WebSocket reconnection."""
        attempt = 0
        
        while attempt < self.max_reconnect_attempts:
            delay = self.base_reconnect_delay * (2 ** attempt)
            logger.info(f"Reconnection attempt {attempt + 1}/{self.max_reconnect_attempts} in {delay}s...")
            
            await asyncio.sleep(delay)
            
            try:
                await self._connect_websocket()
                logger.info("✓ Reconnected successfully")
                self._reconnect_task = None
                return
            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")
                attempt += 1
        
        logger.warning(f"Max reconnection attempts reached. Staying in HTTP mode.")
        self.connection_mode = "http"
        self._reconnect_task = None
    
    async def _heartbeat_loop(self):
        """Monitor WebSocket connection health."""
        try:
            while self.is_connected and self.websocket:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Try to ping the connection
                try:
                    pong = await self.websocket.ping()
                    await asyncio.wait_for(pong, timeout=5)
                except:
                    logger.warning("WebSocket heartbeat failed")
                    self.is_connected = False
                    
                    # Start reconnection
                    if not self._reconnect_task:
                        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
                    break
        except asyncio.CancelledError:
            pass
    
    # Public API methods
    
    async def send_location(self, latitude: float, longitude: float, timestamp: Optional[str] = None) -> bool:
        """
        Send location data.
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            timestamp: ISO format timestamp (defaults to now)
        
        Returns:
            True if sent successfully, False if buffered
        """
        data = {
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "latitude": latitude,
            "longitude": longitude
        }
        return await self._send_message("location", data)
    
    async def send_screen_time(
        self,
        date: str,
        total_screen_time: int,
        app_wise_data: Dict[str, Dict[str, int]]
    ) -> bool:
        """
        Send screen time data.
        
        Args:
            date: Date in YYYY-MM-DD format
            total_screen_time: Total screen time in seconds
            app_wise_data: Dict of {app_domain: {hour: seconds}}
        
        Returns:
            True if sent successfully, False if buffered
        """
        data = {
            "date": date,
            "total_screen_time": total_screen_time,
            "app_wise_data": app_wise_data
        }
        return await self._send_message("screen_time", data)
    
    async def send_site_access_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """
        Send site access logs.
        
        Args:
            logs: List of {timestamp, url, accessed} dicts
        
        Returns:
            True if sent successfully, False if buffered
        """
        data = {"logs": logs}
        return await self._send_message("site_access", data)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current client status."""
        return {
            "child_hash": self.child_hash,
            "connection_mode": self.connection_mode,
            "is_connected": self.is_connected,
            "buffered_messages": len(self.message_buffer),
            "websocket_url": self.websocket_url,
            "http_url": self.http_url
        }


# Example usage
async def example_usage():
    """Example of how to use the GuardianAIClient."""
    
    # Initialize client
    client = GuardianAIClient(
        child_hash="abc123def456",
        server_url="localhost:8000",
        use_ssl=False
    )
    
    # Connect to server
    await client.connect()
    
    # Send location update
    await client.send_location(
        latitude=40.7128,
        longitude=-74.0060
    )
    
    # Send screen time data
    await client.send_screen_time(
        date="2025-12-10",
        total_screen_time=7200,
        app_wise_data={
            "com.example.app1": {"10": 3600, "11": 1800},
            "com.example.app2": {"10": 1800}
        }
    )
    
    # Send site access logs
    await client.send_site_access_logs([
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": "https://example.com",
            "accessed": True
        }
    ])
    
    # Check status
    status = client.get_status()
    print(f"Client status: {status}")
    
    # Keep connection alive for a while
    await asyncio.sleep(60)
    
    # Disconnect
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(example_usage())

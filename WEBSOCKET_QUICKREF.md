# WebSocket Quick Reference Card

## URLs

### WebSocket Endpoints
```
ws://localhost:8000/ws/ingest/<child_hash>/          # Direct connection
ws://localhost:8000/ws/ingest-auth/                  # Auth flow
```

### HTTP Fallback
```
POST http://localhost:8000/api/ingest/               # Existing endpoint
```

## Message Format

### Send (Client → Server)
```json
{
  "type": "screen_time" | "location" | "site_access",
  "data": { ... }
}
```

### Receive (Server → Client)
```json
{
  "type": "connection_established" | "ack" | "error",
  "message": "...",
  "result": { ... }
}
```

## Quick Start

### Install
```bash
pip install -r requirements.txt
```

### Run Server
```bash
python manage.py runserver
```

### Test
```bash
python websocket_test_client.py
```

## Code Snippets

### Python WebSocket Client
```python
import asyncio
import websockets
import json

async def connect():
    uri = "ws://localhost:8000/ws/ingest/abc123/"
    async with websockets.connect(uri) as ws:
        # Receive acknowledgment
        msg = await ws.recv()
        print(msg)
        
        # Send location
        await ws.send(json.dumps({
            "type": "location",
            "data": {
                "timestamp": "2025-12-10T10:30:00Z",
                "latitude": 40.7128,
                "longitude": -74.0060
            }
        }))
        
        # Receive acknowledgment
        response = await ws.recv()
        print(response)

asyncio.run(connect())
```

### JavaScript WebSocket Client
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/ingest/abc123/');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

// Send location
ws.send(JSON.stringify({
  type: 'location',
  data: {
    timestamp: new Date().toISOString(),
    latitude: 40.7128,
    longitude: -74.0060
  }
}));
```

### Android/Kotlin WebSocket Client
```kotlin
import okhttp3.*
import org.json.JSONObject

class WebSocketClient(private val childHash: String) {
    private val client = OkHttpClient()
    private var webSocket: WebSocket? = null
    
    fun connect() {
        val request = Request.Builder()
            .url("ws://localhost:8000/ws/ingest/$childHash/")
            .build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                println("Connected")
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                println("Received: $text")
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                println("Error: ${t.message}")
                // Fallback to HTTP
            }
        })
    }
    
    fun sendLocation(lat: Double, lon: Double) {
        val message = JSONObject().apply {
            put("type", "location")
            put("data", JSONObject().apply {
                put("timestamp", System.currentTimeMillis())
                put("latitude", lat)
                put("longitude", lon)
            })
        }
        webSocket?.send(message.toString())
    }
}
```

### iOS/Swift WebSocket Client
```swift
import Foundation

class WebSocketClient {
    private var webSocket: URLSessionWebSocketTask?
    private let childHash: String
    
    init(childHash: String) {
        self.childHash = childHash
    }
    
    func connect() {
        let url = URL(string: "ws://localhost:8000/ws/ingest/\(childHash)/")!
        webSocket = URLSession.shared.webSocketTask(with: url)
        webSocket?.resume()
        receiveMessage()
    }
    
    func sendLocation(lat: Double, lon: Double) {
        let message: [String: Any] = [
            "type": "location",
            "data": [
                "timestamp": ISO8601DateFormatter().string(from: Date()),
                "latitude": lat,
                "longitude": lon
            ]
        ]
        
        let jsonData = try! JSONSerialization.data(withJSONObject: message)
        let jsonString = String(data: jsonData, encoding: .utf8)!
        
        webSocket?.send(.string(jsonString)) { error in
            if let error = error {
                print("Error sending: \(error)")
                // Fallback to HTTP
            }
        }
    }
    
    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    print("Received: \(text)")
                default:
                    break
                }
                self?.receiveMessage()
            case .failure(let error):
                print("Error: \(error)")
                // Reconnect or fallback to HTTP
            }
        }
    }
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Start server: `python manage.py runserver` |
| Child not found (4004) | Use valid child_hash from database |
| Module not found | Run: `pip install -r requirements.txt` |
| Message not acknowledged | Check JSON format matches spec |
| Connection drops | Implement reconnection logic |

## Production Checklist

- [ ] Install Redis: `sudo apt-get install redis-server`
- [ ] Update settings.py to use Redis channel layer
- [ ] Use Daphne: `daphne guardianAI.asgi:application`
- [ ] Configure nginx for WebSocket proxying
- [ ] Use wss:// (WebSocket Secure) with SSL/TLS
- [ ] Set up systemd service for auto-restart
- [ ] Monitor connection count and message rate
- [ ] Implement rate limiting
- [ ] Set up logging and alerts

## Files Reference

| File | Purpose |
|------|---------|
| `backend/consumers.py` | WebSocket message handlers |
| `backend/routing.py` | WebSocket URL routing |
| `guardianAI/asgi.py` | ASGI application config |
| `guardianAI/settings.py` | Django settings (channels config) |
| `websocket_test_client.py` | Test WebSocket connection |
| `mobile_client_example.py` | Full client implementation |
| `WEBSOCKET_IMPLEMENTATION.md` | Complete documentation |
| `WEBSOCKET_SETUP.md` | Setup and deployment guide |

## Support Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python manage.py runserver

# Run production server
daphne -b 0.0.0.0 -p 8000 guardianAI.asgi:application

# Test WebSocket
python websocket_test_client.py

# Test with wscat
wscat -c ws://localhost:8000/ws/ingest/abc123/

# Check Redis (if using)
redis-cli ping

# View logs
tail -f /var/log/guardianai/access.log
```

## Message Examples

### Screen Time
```json
{
  "type": "screen_time",
  "data": {
    "date": "2025-12-10",
    "total_screen_time": 3600,
    "app_wise_data": {
      "com.example.app": {"10": 1800, "11": 1800}
    }
  }
}
```

### Location
```json
{
  "type": "location",
  "data": {
    "timestamp": "2025-12-10T10:30:00Z",
    "latitude": 40.7128,
    "longitude": -74.0060
  }
}
```

### Site Access
```json
{
  "type": "site_access",
  "data": {
    "logs": [
      {
        "timestamp": "2025-12-10T10:30:00Z",
        "url": "https://example.com",
        "accessed": true
      }
    ]
  }
}
```

---

**Need more help?** Check `WEBSOCKET_IMPLEMENTATION.md` for complete documentation.

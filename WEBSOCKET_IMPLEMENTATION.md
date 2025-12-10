# WebSocket Ingest Implementation

## Overview

The Guardian AI backend now supports real-time data ingestion via WebSocket connections, with the HTTP endpoint maintained as a fallback mechanism. Mobile clients should primarily use WebSocket for continuous data transmission and fall back to HTTP POST if the WebSocket connection fails.

## Architecture

### Components Added:
1. **backend/consumers.py** - WebSocket consumers handling real-time data
2. **backend/routing.py** - WebSocket URL routing configuration
3. **guardianAI/asgi.py** - ASGI application with protocol routing
4. **settings.py** - Channel layers and ASGI configuration

### Dependencies Added:
- `channels==4.2.0` - Django Channels for WebSocket support
- `daphne==4.2.1` - ASGI server for serving WebSocket connections
- `channels-redis==4.2.0` - Redis backend for production (optional)

## WebSocket Endpoints

### 1. Direct Connection (Recommended)
**URL:** `ws://domain/ws/ingest/<child_hash>/`

The child_hash is included in the URL path. Connection is accepted if the child exists.

**Connection Flow:**
1. Client connects with child_hash in URL
2. Server validates child_hash exists
3. Server sends connection acknowledgment
4. Client can send data messages

**Example URL:** `ws://localhost:8000/ws/ingest/abc123def456/`

### 2. Authentication Flow
**URL:** `ws://domain/ws/ingest-auth/`

Client must authenticate with child_hash after connecting.

**Connection Flow:**
1. Client connects without child_hash
2. Server requests authentication
3. Client sends auth message with child_hash
4. Server validates and confirms authentication
5. Client can send data messages

## Message Format

### Connection Established (Server → Client)
```json
{
  "type": "connection_established",
  "child_hash": "abc123def456",
  "message": "WebSocket connection established successfully"
}
```

### Data Messages (Client → Server)

All data messages follow this structure:
```json
{
  "type": "screen_time" | "location" | "site_access",
  "data": { ... }
}
```

#### Screen Time Data
```json
{
  "type": "screen_time",
  "data": {
    "date": "2025-12-10",
    "total_screen_time": 3600,
    "app_wise_data": {
      "com.example.app": {
        "0": 1800,
        "1": 1800
      }
    }
  }
}
```

#### Location Data
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

#### Site Access Logs
```json
{
  "type": "site_access",
  "data": {
    "logs": [
      {
        "timestamp": "2025-12-10T10:30:00Z",
        "url": "https://example.com",
        "accessed": true
      },
      {
        "timestamp": "2025-12-10T10:31:00Z",
        "url": "https://blocked-site.com",
        "accessed": false
      }
    ]
  }
}
```

### Acknowledgment (Server → Client)
```json
{
  "type": "ack",
  "message_type": "screen_time",
  "status": "success",
  "result": {
    "stored": true,
    "created": false,
    "date": "2025-12-10"
  }
}
```

### Error Response (Server → Client)
```json
{
  "type": "error",
  "message": "Error description"
}
```

## Error Codes

WebSocket close codes:
- `4001` - Authentication failed (missing child_hash)
- `4004` - Child not found (invalid child_hash)

## Mobile Client Implementation Guide

### Connection Strategy

```pseudo
1. Try WebSocket connection first
2. If WebSocket fails or disconnects:
   - Buffer data locally
   - Attempt reconnection with exponential backoff
   - If reconnection fails after N attempts, fall back to HTTP
3. Send buffered data via HTTP endpoint
4. Continue attempting WebSocket reconnection in background
5. Switch back to WebSocket when connection is restored
```

### Recommended Flow

```
┌─────────────────┐
│  Mobile Client  │
└────────┬────────┘
         │
         ├─► Try WebSocket Connection
         │   ws://domain/ws/ingest/<child_hash>/
         │
         ├─► Success?
         │   ├─► Yes: Use WebSocket
         │   │   ├─► Send data via WebSocket
         │   │   ├─► Buffer locally if send fails
         │   │   └─► Monitor connection status
         │   │
         │   └─► No: Fall back to HTTP
         │       └─► POST to /api/ingest/
         │
         └─► Connection Lost?
             ├─► Buffer data locally
             ├─► Retry WebSocket (exponential backoff)
             └─► Use HTTP if retry limit reached
```

## Python Test Client Example

See `websocket_test_client.py` for a complete implementation example.

## HTTP Fallback Endpoint

The existing HTTP endpoint remains unchanged:

**URL:** `POST /api/ingest/`

**Request Body:**
```json
{
  "child_hash": "abc123def456",
  "screen_time_info": { ... },
  "location_info": { ... },
  "site_access_info": { "logs": [...] }
}
```

This endpoint should be used when:
- WebSocket connection cannot be established
- WebSocket connection is unstable
- Batch sending buffered data after reconnection failure

## Running the Server

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations (if any)
python manage.py migrate

# Run with Daphne (ASGI server)
daphne -b 0.0.0.0 -p 8000 guardianAI.asgi:application

# Or use Django's development server (also supports ASGI in Django 3+)
python manage.py runserver
```

### Production

For production, use Daphne with Redis channel layer:

1. Update `settings.py` to use Redis backend:
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('localhost', 6379)],
        },
    },
}
```

2. Run with Daphne:
```bash
daphne -b 0.0.0.0 -p 8000 guardianAI.asgi:application
```

3. Use a process manager (systemd, supervisor) to keep it running.

## Testing

### Manual Testing with wscat
```bash
# Install wscat
npm install -g wscat

# Connect to WebSocket
wscat -c ws://localhost:8000/ws/ingest/abc123def456/

# Send test message
{"type": "location", "data": {"timestamp": "2025-12-10T10:30:00Z", "latitude": 40.7128, "longitude": -74.0060}}
```

### Python Test Client
```bash
# Run the test client
python websocket_test_client.py
```

## Security Considerations

1. **Child Hash Validation**: Server validates child_hash exists before accepting connection
2. **Message Validation**: All incoming messages are validated before processing
3. **Error Handling**: Comprehensive error handling prevents crashes from malformed data
4. **Connection Limits**: Consider implementing rate limiting for production
5. **TLS/SSL**: Use `wss://` (WebSocket Secure) in production
6. **Authentication**: For enhanced security, implement token-based authentication

## Future Enhancements

1. **Token Authentication**: Add JWT or token-based auth for WebSocket connections
2. **Connection Monitoring**: Add heartbeat/ping mechanism to detect dead connections
3. **Rate Limiting**: Implement per-client rate limiting
4. **Metrics**: Add monitoring for connection count, message rates, etc.
5. **Compression**: Enable WebSocket compression for large payloads
6. **Reconnection**: Server-side reconnection handling with session persistence

## Troubleshooting

### WebSocket Connection Fails
- Ensure Daphne or ASGI server is running
- Check that `channels` is installed and in INSTALLED_APPS
- Verify URL pattern matches (check trailing slashes)
- Check firewall/network allows WebSocket connections

### Messages Not Being Processed
- Check server logs for errors
- Verify message format matches expected schema
- Ensure child_hash is valid
- Check database connectivity

### Performance Issues
- Switch from InMemoryChannelLayer to Redis in production
- Monitor database query performance
- Consider batch processing for high-frequency updates
- Implement message queuing for async processing

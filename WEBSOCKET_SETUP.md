# WebSocket Server Quick Start Guide

## Installation

1. **Install new dependencies:**
```bash
pip install -r requirements.txt
```

This will install:
- `channels==4.2.0` - Django Channels framework
- `daphne==4.2.1` - ASGI HTTP/WebSocket server
- `channels-redis==4.2.0` - Redis channel layer (optional for production)

## Running the Server

### Option 1: Django Development Server (Recommended for Development)

Django's development server (since Django 3.0+) supports ASGI and WebSockets:

```bash
python manage.py runserver
```

The server will be available at:
- HTTP: `http://localhost:8000`
- WebSocket: `ws://localhost:8000`

### Option 2: Daphne ASGI Server (Recommended for Production)

Daphne is the production-ready ASGI server:

```bash
daphne -b 0.0.0.0 -p 8000 guardianAI.asgi:application
```

Options:
- `-b 0.0.0.0`: Bind to all network interfaces
- `-p 8000`: Port number
- `--proxy-headers`: Use when behind a proxy (nginx, etc.)
- `-v 2`: Verbose logging (0-3)

### Option 3: Daphne with systemd (Production)

Create a systemd service file `/etc/systemd/system/guardianai.service`:

```ini
[Unit]
Description=Guardian AI WebSocket Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/Guardian AI
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/daphne -b 0.0.0.0 -p 8000 guardianAI.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable guardianai
sudo systemctl start guardianai
sudo systemctl status guardianai
```

## Testing the WebSocket Connection

### 1. Using the Python Test Client

```bash
python websocket_test_client.py
```

**Important:** Update the `CHILD_HASH` variable in the script to match an existing child in your database.

### 2. Using wscat (WebSocket CLI Tool)

Install wscat:
```bash
npm install -g wscat
```

Connect and test:
```bash
# Connect
wscat -c ws://localhost:8000/ws/ingest/abc123def456/

# After connection, send test message:
{"type": "location", "data": {"timestamp": "2025-12-10T10:30:00Z", "latitude": 40.7128, "longitude": -74.0060}}
```

### 3. Using Browser JavaScript Console

Open browser console on your site and run:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/ingest/abc123def456/');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  console.log('Received:', event.data);
};

// Send test message
ws.send(JSON.stringify({
  type: 'location',
  data: {
    timestamp: new Date().toISOString(),
    latitude: 40.7128,
    longitude: -74.0060
  }
}));
```

## Channel Layers Configuration

### Development (In-Memory - Current Configuration)

Already configured in `settings.py`:
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    },
}
```

**Pros:**
- No additional setup required
- Works immediately
- Good for development/testing

**Cons:**
- Doesn't support multiple server instances
- Lost on restart

### Production (Redis - Recommended)

1. **Install Redis:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Windows
# Download from https://redis.io/download
```

2. **Start Redis:**
```bash
redis-server
```

3. **Update settings.py:**
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

**Pros:**
- Supports multiple server instances
- Persistent across restarts
- Production-ready

## Nginx Configuration (Production)

If using nginx as a reverse proxy:

```nginx
upstream guardianai {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # WebSocket support
    location /ws/ {
        proxy_pass http://guardianai;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Regular HTTP
    location / {
        proxy_pass http://guardianai;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static/ {
        alias /path/to/Guardian AI/staticfiles/;
    }

    # Media files
    location /media/ {
        alias /path/to/Guardian AI/media/;
    }
}
```

## Monitoring and Debugging

### View WebSocket Connections

Check logs for WebSocket activity:
```bash
# With Daphne
daphne -v 2 -b 0.0.0.0 -p 8000 guardianAI.asgi:application

# View logs in real-time
tail -f /var/log/guardianai/access.log
```

### Common Issues

**1. "Connection refused"**
- Server not running
- Firewall blocking port 8000
- Wrong URL/port

**2. "Child not found" (close code 4004)**
- Invalid child_hash
- Child doesn't exist in database

**3. "Module not found: channels"**
- Run: `pip install -r requirements.txt`

**4. "WebSocket upgrade failed"**
- Using HTTP endpoint for WebSocket
- Check URL starts with `ws://` or `wss://`
- Nginx/proxy misconfiguration

### Performance Monitoring

Monitor WebSocket connections:
```python
# In Django shell
from channels.layers import get_channel_layer
channel_layer = get_channel_layer()

# Check if Redis is working (if using Redis backend)
import asyncio
asyncio.run(channel_layer.send('test', {'type': 'test.message'}))
```

## Security Checklist

- [ ] Use `wss://` (WebSocket Secure) in production
- [ ] Configure SSL/TLS certificates
- [ ] Implement rate limiting for WebSocket connections
- [ ] Add authentication token validation
- [ ] Monitor for abuse/DOS attacks
- [ ] Set up firewall rules
- [ ] Keep dependencies updated
- [ ] Use environment variables for sensitive config

## Next Steps

1. **Create a child account** to get a valid child_hash
2. **Run the test client** to verify WebSocket functionality
3. **Integrate mobile client** using the example code
4. **Monitor performance** and adjust configuration as needed
5. **Set up production server** with Redis and nginx

## Mobile Client Integration

Mobile clients should:
1. Connect to WebSocket on app start
2. Send data via WebSocket while connected
3. Buffer data locally if WebSocket fails
4. Fall back to HTTP POST endpoint
5. Attempt WebSocket reconnection with exponential backoff
6. Switch back to WebSocket when available

See `mobile_client_example.py` for complete implementation.

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebSocket endpoint with child_hash in URL
    # Usage: ws://domain/ws/ingest/<child_hash>/
    re_path(r'ws/ingest/(?P<child_hash>[^/]+)/$', consumers.IngestConsumer.as_asgi()),
    
    # WebSocket endpoint with authentication flow
    # Usage: ws://domain/ws/ingest-auth/
    re_path(r'ws/ingest-auth/$', consumers.IngestAuthConsumer.as_asgi()),
]

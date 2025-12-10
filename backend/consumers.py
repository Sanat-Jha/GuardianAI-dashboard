import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class IngestConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for receiving real-time ingest data from mobile clients.
    
    Connection URL: ws://domain/ws/ingest/<child_hash>/
    
    Expected message format:
    {
        "type": "screen_time" | "location" | "site_access",
        "data": { ... }  // The actual payload
    }
    
    For screen_time:
    {
        "type": "screen_time",
        "data": {
            "date": "2025-12-10",
            "total_screen_time": 3600,
            "app_wise_data": {"com.example.app": {"0": 1800, "1": 1800}}
        }
    }
    
    For location:
    {
        "type": "location",
        "data": {
            "timestamp": "2025-12-10T10:30:00Z",
            "latitude": 40.7128,
            "longitude": -74.0060
        }
    }
    
    For site_access:
    {
        "type": "site_access",
        "data": {
            "logs": [
                {"timestamp": "2025-12-10T10:30:00Z", "url": "https://example.com", "accessed": true}
            ]
        }
    }
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.child_hash = self.scope['url_route']['kwargs']['child_hash']
        
        # Verify child exists
        child_exists = await self.verify_child_exists(self.child_hash)
        
        if not child_exists:
            # Reject connection if child doesn't exist
            await self.close(code=4004)
            return
        
        # Accept the WebSocket connection
        await self.accept()
        
        # Send connection acknowledgment
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'child_hash': self.child_hash,
            'message': 'WebSocket connection established successfully'
        }))
        
        print(f"WebSocket connected for child_hash: {self.child_hash}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        print(f"WebSocket disconnected for child_hash: {self.child_hash}, code: {close_code}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            # Parse incoming JSON message
            message = json.loads(text_data)
            message_type = message.get('type')
            data = message.get('data')
            
            if not message_type or not data:
                await self.send_error('Invalid message format. Expected "type" and "data" fields.')
                return
            
            # Add child_hash to data
            data['child_hash'] = self.child_hash
            
            # Route message to appropriate handler
            if message_type == 'screen_time':
                result = await self.handle_screen_time(data)
            elif message_type == 'location':
                result = await self.handle_location(data)
            elif message_type == 'site_access':
                result = await self.handle_site_access(data)
            else:
                await self.send_error(f'Unknown message type: {message_type}')
                return
            
            # Send success acknowledgment
            await self.send(text_data=json.dumps({
                'type': 'ack',
                'message_type': message_type,
                'status': 'success',
                'result': result
            }))
            
        except json.JSONDecodeError as e:
            await self.send_error(f'Invalid JSON: {str(e)}')
        except Exception as e:
            await self.send_error(f'Error processing message: {str(e)}')
            print(f"Error in WebSocket receive: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def send_error(self, message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))
    
    @database_sync_to_async
    def verify_child_exists(self, child_hash):
        """Verify that the child exists in the database"""
        from accounts.models import Child
        return Child.objects.filter(child_hash=child_hash).exists()
    
    @database_sync_to_async
    def handle_screen_time(self, data):
        """Handle screen time data ingestion"""
        from backend.models import ScreenTime
        
        try:
            obj, created = ScreenTime.store_from_dict(data)
            return {
                'stored': True,
                'created': created,
                'date': str(obj.date) if obj else None
            }
        except ValueError as e:
            raise Exception(f'Screen time validation error: {str(e)}')
        except Exception as e:
            raise Exception(f'Screen time storage error: {str(e)}')
    
    @database_sync_to_async
    def handle_location(self, data):
        """Handle location data ingestion"""
        from backend.models import LocationHistory
        
        try:
            obj = LocationHistory.store_from_dict(data)
            return {
                'stored': True,
                'timestamp': obj.timestamp.isoformat() if obj else None
            }
        except ValueError as e:
            raise Exception(f'Location validation error: {str(e)}')
        except Exception as e:
            raise Exception(f'Location storage error: {str(e)}')
    
    @database_sync_to_async
    def handle_site_access(self, data):
        """Handle site access logs ingestion"""
        from backend.models import SiteAccessLog
        
        try:
            logs = data.get('logs', [])
            objs = SiteAccessLog.store_from_list(self.child_hash, logs)
            return {
                'stored': True,
                'count': len(objs)
            }
        except ValueError as e:
            raise Exception(f'Site access validation error: {str(e)}')
        except Exception as e:
            raise Exception(f'Site access storage error: {str(e)}')


class IngestAuthConsumer(AsyncWebsocketConsumer):
    """
    Alternative WebSocket consumer with authentication support.
    
    Connection URL: ws://domain/ws/ingest-auth/
    
    First message must be authentication:
    {
        "type": "auth",
        "child_hash": "abc123"
    }
    
    After authentication, same message format as IngestConsumer.
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.child_hash = None
        self.authenticated = False
        
        # Accept connection but require authentication
        await self.accept()
        
        # Request authentication
        await self.send(text_data=json.dumps({
            'type': 'auth_required',
            'message': 'Please authenticate with child_hash'
        }))
        
        print("WebSocket connected, awaiting authentication")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if self.child_hash:
            print(f"WebSocket disconnected for child_hash: {self.child_hash}, code: {close_code}")
        else:
            print(f"WebSocket disconnected (unauthenticated), code: {close_code}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            message = json.loads(text_data)
            message_type = message.get('type')
            
            # Handle authentication
            if not self.authenticated:
                if message_type == 'auth':
                    await self.handle_auth(message)
                else:
                    await self.send_error('Authentication required. Send auth message first.')
                return
            
            # Handle regular messages (same as IngestConsumer)
            data = message.get('data')
            
            if not message_type or not data:
                await self.send_error('Invalid message format. Expected "type" and "data" fields.')
                return
            
            # Add child_hash to data
            data['child_hash'] = self.child_hash
            
            # Route message to appropriate handler
            if message_type == 'screen_time':
                result = await self.handle_screen_time(data)
            elif message_type == 'location':
                result = await self.handle_location(data)
            elif message_type == 'site_access':
                result = await self.handle_site_access(data)
            else:
                await self.send_error(f'Unknown message type: {message_type}')
                return
            
            # Send success acknowledgment
            await self.send(text_data=json.dumps({
                'type': 'ack',
                'message_type': message_type,
                'status': 'success',
                'result': result
            }))
            
        except json.JSONDecodeError as e:
            await self.send_error(f'Invalid JSON: {str(e)}')
        except Exception as e:
            await self.send_error(f'Error processing message: {str(e)}')
            print(f"Error in WebSocket receive: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def handle_auth(self, message):
        """Handle authentication message"""
        child_hash = message.get('child_hash')
        
        if not child_hash:
            await self.send_error('child_hash required for authentication')
            await self.close(code=4001)
            return
        
        # Verify child exists
        child_exists = await self.verify_child_exists(child_hash)
        
        if not child_exists:
            await self.send_error('Invalid child_hash')
            await self.close(code=4004)
            return
        
        # Authentication successful
        self.child_hash = child_hash
        self.authenticated = True
        
        await self.send(text_data=json.dumps({
            'type': 'auth_success',
            'child_hash': self.child_hash,
            'message': 'Authentication successful'
        }))
        
        print(f"WebSocket authenticated for child_hash: {self.child_hash}")
    
    async def send_error(self, message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))
    
    @database_sync_to_async
    def verify_child_exists(self, child_hash):
        """Verify that the child exists in the database"""
        from accounts.models import Child
        return Child.objects.filter(child_hash=child_hash).exists()
    
    @database_sync_to_async
    def handle_screen_time(self, data):
        """Handle screen time data ingestion"""
        from backend.models import ScreenTime
        
        try:
            obj, created = ScreenTime.store_from_dict(data)
            return {
                'stored': True,
                'created': created,
                'date': str(obj.date) if obj else None
            }
        except ValueError as e:
            raise Exception(f'Screen time validation error: {str(e)}')
        except Exception as e:
            raise Exception(f'Screen time storage error: {str(e)}')
    
    @database_sync_to_async
    def handle_location(self, data):
        """Handle location data ingestion"""
        from backend.models import LocationHistory
        
        try:
            obj = LocationHistory.store_from_dict(data)
            return {
                'stored': True,
                'timestamp': obj.timestamp.isoformat() if obj else None
            }
        except ValueError as e:
            raise Exception(f'Location validation error: {str(e)}')
        except Exception as e:
            raise Exception(f'Location storage error: {str(e)}')
    
    @database_sync_to_async
    def handle_site_access(self, data):
        """Handle site access logs ingestion"""
        from backend.models import SiteAccessLog
        
        try:
            logs = data.get('logs', [])
            objs = SiteAccessLog.store_from_list(self.child_hash, logs)
            return {
                'stored': True,
                'count': len(objs)
            }
        except ValueError as e:
            raise Exception(f'Site access validation error: {str(e)}')
        except Exception as e:
            raise Exception(f'Site access storage error: {str(e)}')

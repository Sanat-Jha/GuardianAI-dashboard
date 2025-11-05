# Blocked Apps API Documentation

## Overview
The Child model now includes a `blocked_apps` field that stores a list of blocked app package names as a JSON array.

## Database Field
- **Field Name**: `blocked_apps`
- **Type**: JSONField
- **Default**: Empty list `[]`
- **Description**: Stores a list of Android app package names that should be blocked for this child

## API Endpoints

### 1. Get Blocked Apps
Retrieve the list of blocked apps for a specific child.

**Endpoint**: `GET /api/blocked-apps/<child_hash>/`

**Authentication**: None (public endpoint - accessible by mobile app)

**URL Parameters**:
- `child_hash` (string): The unique hash identifier for the child

**Response** (Success - 200):
```json
{
    "child_hash": "9KKm7qf2n9OjpI3K",
    "blocked_apps": [
        "com.facebook.katana",
        "com.instagram.android",
        "com.snapchat.android"
    ],
    "status": "success"
}
```

**Response** (Child Not Found - 404):
```json
{
    "error": "Child not found",
    "status": "error"
}
```

**Example Usage**:
```bash
curl -X GET http://localhost:8000/api/blocked-apps/9KKm7qf2n9OjpI3K/
```

---

### 2. Update Blocked Apps (Guardian Dashboard)
Update the list of blocked apps for a specific child. Only accessible by authenticated guardians who have access to this child.

**Endpoint**: `POST /api/blocked-apps/<child_hash>/update/`

**Authentication**: Required (login_required - guardian must be logged in)

**URL Parameters**:
- `child_hash` (string): The unique hash identifier for the child

**Request Body**:
```json
{
    "blocked_apps": [
        "com.facebook.katana",
        "com.instagram.android",
        "com.snapchat.android"
    ]
}
```

**Response** (Success - 200):
```json
{
    "child_hash": "9KKm7qf2n9OjpI3K",
    "blocked_apps": [
        "com.facebook.katana",
        "com.instagram.android",
        "com.snapchat.android"
    ],
    "status": "success",
    "message": "Blocked apps updated successfully"
}
```

**Response** (Child Not Found or No Permission - 404):
```json
{
    "error": "Child not found or you do not have permission",
    "status": "error"
}
```

**Response** (Invalid Data - 400):
```json
{
    "error": "blocked_apps must be a list",
    "status": "error"
}
```

**Example Usage**:
```bash
curl -X POST http://localhost:8000/api/blocked-apps/9KKm7qf2n9OjpI3K/update/ \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionid=<your-session-id>" \
  -d '{
    "blocked_apps": [
        "com.facebook.katana",
        "com.instagram.android"
    ]
}'
```

---

## Common App Package Names

Here are some common Android app package names for reference:

- **Facebook**: `com.facebook.katana`
- **Instagram**: `com.instagram.android`
- **WhatsApp**: `com.whatsapp`
- **Snapchat**: `com.snapchat.android`
- **TikTok**: `com.zhiliaoapp.musically`
- **Twitter/X**: `com.twitter.android`
- **YouTube**: `com.google.android.youtube`
- **Netflix**: `com.netflix.mediaclient`
- **Spotify**: `com.spotify.music`
- **Reddit**: `com.reddit.frontpage`
- **Discord**: `com.discord`
- **Telegram**: `org.telegram.messenger`
- **Chrome**: `com.android.chrome`
- **Games**: Various (e.g., `com.king.candycrushsaga`, `com.supercell.clashofclans`)

---

## Mobile App Integration

The mobile app should:

1. **On App Start/Login**: Call `GET /api/blocked-apps/<child_hash>/` to retrieve the list of blocked apps
2. **Periodically**: Poll this endpoint every 5-10 minutes to check for updates
3. **Block Apps**: Use Android's accessibility service or device admin to prevent launching apps in the blocked list
4. **Enforce Blocking**: Monitor app launches and prevent access to any app in the `blocked_apps` list

---

## Migration

After adding the `blocked_apps` field, run:

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

This will add the new field to the database with a default empty list for existing children.

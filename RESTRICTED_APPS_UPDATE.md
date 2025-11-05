# Restricted Apps System Update

## Changes Made:

### 1. Database Model (`accounts/models.py`)
- **Changed:** `blocked_apps` field (JSONField list) → `restricted_apps` field (JSONField dict)
- **New Format:** `{"package.name": hours_allowed}` e.g., `{"com.instagram.android": 2.5}`
- **Migration Required:** Run `python manage.py makemigrations` and `python manage.py migrate`

### 2. Backend API (`backend/views.py`)
- **Updated:** `get_blocked_apps()` → Now returns `restricted_apps` dict instead of `blocked_apps` list
- **Updated:** `update_blocked_apps()` → Now expects `restricted_apps` dict with validation for numeric hours values
- **Response Format:**
```json
{
  "child_hash": "abc123",
  "restricted_apps": {
    "com.instagram.android": 2.5,
    "com.facebook.katana": 1.0
  },
  "status": "success"
}
```

### 3. Frontend Component
- **New File:** `restricted_apps_manager.html` (replaces `blocked_apps_manager.html`)
- **UI Changes:**
  - Title: "Restricted Apps Manager" (was "Blocked Apps Manager")
  - Icon: Clock icon (was X/block icon)
  - Colors: Amber/yellow theme (was red theme)
  - Added: Hours input field next to app search
  - Shows: Time limit for each app

### 4. JavaScript Functions (Need to Update)
The following functions need to be updated in `dashboard_scripts.html`:

#### Functions to Rename/Update:
1. `loadBlockedApps()` → `loadRestrictedApps()`
2. `addBlockedApp()` → `addRestrictedApp()`
3. `removeBlockedApp()` → `removeRestrictedApp()`
4. `quickBlockApp()` → `quickRestrictApp()`
5. `updateBlockedAppsOnServer()` → `updateRestrictedAppsOnServer()`
6. `fetchAppDetailsForBlocked()` → `fetchAppDetailsForRestricted()`
7. `renderBlockedAppsList()` → `renderRestrictedAppsList()`
8. `updateQuickAddButtons()` → `updateQuickRestrictButtons()`

#### Key Logic Changes:
- Store as object `{domain: hours}` instead of array `[domain1, domain2]`
- Display hours alongside each app
- Allow editing hours for existing restrictions
- Validate hours input (positive numbers)

### 5. Template Update
- **Updated:** `dashboard.html` → Include `restricted_apps_manager.html` instead of `blocked_apps_manager.html`

## Migration Steps:

1. **Run Migration:**
```bash
python manage.py makemigrations
python manage.py migrate
```

2. **Data Migration (if needed):**
If you have existing `blocked_apps` data, create a data migration to convert:
- From: `["com.app1", "com.app2"]`
- To: `{"com.app1": 0, "com.app2": 0}` (0 hours = blocked completely)

3. **Update Mobile App:**
The mobile app needs to:
- Read `restricted_apps` as dict instead of `blocked_apps` as list
- Implement time tracking per app
- Enforce time limits based on hours allowed

## Testing:

1. Load dashboard - should see "Restricted Apps Manager"
2. Add app with time limit (e.g., 2.5 hours)
3. Verify stored as `{"com.package": 2.5}` in database
4. Edit time limit for existing app
5. Remove app from restrictions
6. Test quick-add buttons with default 2 hours

## Mobile App API Changes:

The mobile app should expect this format from `/api/blocked-apps/{child_hash}/`:
```json
{
  "restricted_apps": {
    "com.instagram.android": 2.5,
    "com.youtube": 1.0
  }
}
```

Instead of:
```json
{
  "blocked_apps": [
    "com.instagram.android",
    "com.youtube"
  ]
}
```

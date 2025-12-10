# 📚 Guardian AI – Technical Documentation

*(All paths are absolute and refer to the current workspace `c:\Users\sanat\Desktop\Guardian AI`)*

---

## 1️⃣ Overview

Guardian AI is a **Django‑based parental‑control platform** that collects a child’s device usage (screen‑time, app usage, location, and web‑site access) from a mobile client, stores the data in a **SQLite** database, and visualises it on a rich, interactive **dashboard** for the guardian (parent).

Key components:

| Component | Location | Purpose |
|-----------|----------|---------|
| **accounts** | `c:\Users\sanat\Desktop\Guardian AI\accounts` | User (guardian) authentication, child management, and UI pages for login / signup. |
| **backend** | `c:\Users\sanat\Desktop\Guardian AI\backend` | Core data models (`ScreenTime`, `AppScreenTime`, `LocationHistory`, `SiteAccessLog`, `App`), API endpoints for ingestion and reporting, and the dashboard view. |
| **guardianAI** | `c:\Users\sanat\Desktop\Guardian AI\guardianAI` | Project‑level settings, WSGI/ASGI entry points, and URL routing. |
| **templates** | `c:\Users\sanat\Desktop\Guardian AI\accounts\templates\dashboard` | HTML + Django template tags that render the dashboard UI. |
| **staticfiles** | `c:\Users\sanat\Desktop\Guardian AI\staticfiles` | Compiled static assets (CSS, JS, images) served by Django’s `collectstatic`. |

The dashboard is a **single‑page view** (`backend.views.dashboard_view`) that pulls all required data from the database, passes it to the template `dashboard.html`, and then uses a collection of reusable components (stat cards, charts, lists, modals) to display the information.

---

## 2️⃣ Database Models

All models are defined in `accounts/models.py` and `backend/models.py`. Below is a concise description of each model, its fields, and its relationships.

### 2.1 `accounts/models.py`

| Model | Fields | Description |
|-------|--------|-------------|
| **Guardian** (`AbstractBaseUser`, `PermissionsMixin`) | `email`, `full_name`, `is_staff`, `is_active`, `date_joined`, `groups`, `user_permissions`, `children` (M2M → `Child`) | Represents a parent. Uses email as the login identifier. The `children` many‑to‑many field lets a guardian own many children (and a child can have multiple guardians). |
| **Child** (`AbstractBaseUser`, `PermissionsMixin`) | `child_hash` (unique, used as login identifier), `first_name`, `last_name`, `date_of_birth`, `is_active`, `date_joined`, `restricted_apps` (JSON), `profile_image` (ImageField), `groups`, `user_permissions` | Represents a child device. `child_hash` is a random URL‑safe token generated on creation. The `restricted_apps` JSON stores per‑app time‑limit rules (`{ "com.example.app": 2 }`). |
| **GuardianManager** / **ChildManager** | Custom managers that provide `create_user`, `create_superuser`, and `create_user` (for `Child`) with automatic hash generation. | Handles safe creation of guardians and children. |

### 2.2 `backend/models.py`

| Model | Fields | Relationships | Description |
|-------|--------|---------------|-------------|
| **ScreenTime** | `child` (FK → `Child`), `date`, `total_screen_time` (seconds), `app_wise_data` (JSON – legacy), `created`, `updated` | One row per child per day. Legacy JSON kept for backward compatibility. | Stores daily aggregate screen‑time. Provides helper methods `get_app_breakdown()` and `get_app_hourly_breakdown()` that read from the newer `AppScreenTime` table if present. |
| **AppScreenTime** | `screen_time` (FK → `ScreenTime`), `app` (FK → `App`), `hour` (0‑23), `seconds`, `created`, `updated` | One entry per hour per app per day. | Normalised, relational storage of per‑app hourly usage. |
| **LocationHistory** | `child` (FK → `Child`), `timestamp`, `latitude`, `longitude`, `created` | Stores raw GPS points. | Auto‑prunes entries older than 365 days on save. |
| **SiteAccessLog** | `child` (FK → `Child`), `timestamp`, `url`, `accessed` (bool), `created` | Stores each website request (allowed or blocked). | Auto‑prunes entries older than 365 days on save. |
| **App** | `domain` (unique, e.g. `com.facebook.katana`), `app_name`, `icon_url`, `blocked_count` | Represents a mobile app. | Provides static method `create_from_package()` that pulls metadata from the Google Play Store (via `google_play_scraper`). The `blocked_count` tracks how many times the app has been blocked for any child. |

All models implement **static helper methods** for bulk ingestion:

* `ScreenTime.store_from_dict(data)` – creates/updates a `ScreenTime` row and populates `AppScreenTime` entries.
* `LocationHistory.store_from_dict(data)` – creates a location point.
* `SiteAccessLog.store_from_list(child_hash, log_list)` – bulk‑creates site‑access rows.

These helpers are used by the **mobile‑client ingestion endpoint** (`backend.views.api_ingest`).

---

## 3️⃣ Data Flow

### 3️⃣ 1 – Ingestion (Mobile → Server)

1. **Mobile client** sends a **POST** request to `/api/ingest/` (`backend.views.api_ingest`).
2. The request body is JSON with a top‑level `child_hash` and optional sections:

   ```json
   {
     "child_hash": "abc123",
     "screen_time_info": { "date": "2025-12-01", "total_screen_time": 7200, "app_wise_data": {...} },
     "location_info": { "timestamp": "2025-12-01T12:34:56Z", "latitude": 12.34, "longitude": 56.78 },
     "site_access_info": { "logs": [{ "timestamp": "...", "url": "...", "accessed": true }, …] }
   }
   ```
3. `api_ingest` extracts each section, injects the `child_hash` if missing, and calls the corresponding static helper:
   * `ScreenTime.store_from_dict()` → creates/updates a `ScreenTime` row **and** creates `AppScreenTime` rows for each hour‑level entry.
   * `LocationHistory.store_from_dict()` → creates a new GPS point.
   * `SiteAccessLog.store_from_list()` → bulk‑creates site‑access logs.
4. Each helper **prunes old data** (365 days) after insertion, ensuring the DB never grows unbounded.
5. The endpoint returns a JSON summary of what was stored (or errors).

### 3️⃣ 2 – Dashboard Rendering (Server → Browser)

1. Guardian logs in via `/accounts/login/`. Django’s authentication system sets `request.user` to a `Guardian` instance.
2. The **dashboard view** (`backend.views.dashboard_view`) is protected by `@login_required`. It:
   * Retrieves all children belonging to the guardian (`guardian.children.all()`).
   * For each child, pulls the **last 30 days** of `ScreenTime` rows, calculates:
     * `total_screen_time` (seconds) → formatted hours.
     * `average_screen_time`.
     * **App breakdown** via `ScreenTime.get_app_breakdown()` (uses `AppScreenTime` if present).
     * **Top apps** (sorted by usage).
     * **Location history** (latest 20 points).
     * **Site‑access logs** (latest 30 entries).
     * **Recent 7‑day stats** (average per day).
     * **Child age** (derived from `date_of_birth`).
   * Packs all this into a dictionary `children_data` keyed by child instance.
3. The view renders `accounts/templates/dashboard/dashboard.html` with context:
   ```python
   {
       "children": children,          # QuerySet of Child objects
       "children_data": children_data # Detailed per‑child stats
   }
   ```
4. **Template Structure** (`dashboard.html`)
   * **Sidebar** – included via `{% include 'dashboard/components/dashboard_sidebar.html' %}`.
   * **Add‑Child Modal** – reusable modal for creating a new child (`add_child_modal.html`).
   * **Main Content** – conditional rendering:
     * If no children → show `empty_state.html`.
     * Otherwise → show a **select‑prompt** (`select_child_prompt.html`) and a hidden `<div id="child-{{ child_hash }}" class="child-dashboard hidden">` for each child.
   * Inside each child‑dashboard:
     * **Stat cards** (`stat_card.html`) – total screen time, average daily, latest location, blocked sites.
     * **Screen‑time line chart** (`screen_time_chart.html`).
     * **App usage bar chart** (`app_usage_chart.html`).
     * **All‑apps list** (`all_apps_list.html`).
     * **Restricted‑apps manager**, **Location history**, **Site‑access log** – each a separate component.
   * **JavaScript** (`dashboard_scripts.html`) – fetches chart data via AJAX endpoints (`child_chart_data`, `child_stats_data`, `child_locations_data`, `child_site_logs_data`) and populates the UI with Chart.js / Tailwind‑style components.
   * **CSS** (`dashboard_styles.html`) – custom styling (glass‑morphism, gradients, dark mode) that satisfies the “rich aesthetics” requirement.
5. The **AJAX endpoints** (`child_chart_data`, `child_stats_data`, etc.) are simple `@login_required` view functions that:
   * Validate the `child_hash` belongs to the logged‑in guardian.
   * Apply optional `start_date` / `end_date` filters.
   * Serialize the required data (dates, screen‑time values, app breakdowns, location points, site logs) into JSON.
6. Front‑end JavaScript consumes these JSON payloads, renders charts, and updates the UI dynamically without a full page reload.

### 3️⃣ 3 – Additional API Endpoints

| URL | Method | Purpose | Key Logic |
|-----|--------|---------|-----------|
| `/api/login/` (`api_login`) | POST | Authenticate a guardian and return a list of their children (for mobile). | Uses `django.contrib.auth.authenticate`. |
| `/api/ingest/` (`api_ingest`) | POST | Receive bulk metrics from the mobile client. | Calls static `store_from_*` helpers. |
| `/api/blocked-apps/<child_hash>/` (`get_blocked_apps`) | GET | Return the `restricted_apps` JSON for a child. | Simple lookup + JSON response. |
| `/dashboard/` (`dashboard_view`) | GET | Render the main HTML dashboard. | Aggregates data, passes to template. |
| `/child/<child_hash>/chart/` (`child_chart_data`) | GET | Provide line‑chart (screen‑time) & bar‑chart (top apps) data. | Uses `ScreenTime.get_app_breakdown()`. |
| `/child/<child_hash>/stats/` (`child_stats_data`) | GET | Return high‑level stats (total, avg, latest location, site counts). | Same aggregation as in `dashboard_view`. |
| `/child/<child_hash>/locations/` (`child_locations_data`) | GET | Return recent GPS points. | Simple queryset → list of dicts. |
| `/child/<child_hash>/site-logs/` (`child_site_logs_data`) | GET | Return recent site‑access logs. | Simple queryset → list of dicts. |

All endpoints enforce **guardian ownership** (`Child.objects.get(child_hash=..., guardians=request.user)`) to prevent cross‑account data leakage.

---

## 4️⃣ URL Routing

* **Accounts URLs** – `accounts/urls.py`
```python
path('', views.landing_page, name='landing_page')
path('signup/', views.signup_view, name='signup')
path('login/', views.login_view, name='login')
path('logout/', views.logout_view, name='logout')
path('password-reset/', views.password_reset_info, name='password_reset')
path('child/<str:child_hash>/delete/', views.delete_child, name='delete_child')
path('child/<str:child_hash>/upload-profile-image/', views.upload_child_profile_image, name='upload_child_profile_image')
```
* **Backend URLs** – `backend/urls.py` (excerpt, full file omitted for brevity)
```python
path('dashboard/', views.dashboard_view, name='dashboard')
path('api/login/', views.api_login, name='api_login')
path('api/ingest/', views.api_ingest, name='api_ingest')
path('api/blocked-apps/<str:child_hash>/', views.get_blocked_apps, name='get_blocked_apps')
path('child/<str:child_hash>/chart/', views.child_chart_data, name='child_chart_data')
path('child/<str:child_hash>/stats/', views.child_stats_data, name='child_stats_data')
path('child/<str:child_hash>/locations/', views.child_locations_data, name='child_locations_data')
path('child/<str:child_hash>/site-logs/', views.child_site_logs_data, name='child_site_logs_data')
```
* **Project URLs** – `guardianAI/urls.py` includes the two app namespaces (`accounts` and `backend`).

---

## 5️⃣ Settings & External Services

* **OpenCage Geocoder** – Used in `dashboard_view` and `child_stats_data` to turn latitude/longitude into a compact address. The API key is read from `settings.OPENCAGE_API_KEY`.
* **Google Play Scraper** – `backend/models.App.create_from_package()` fetches app name & icon from the Play Store. If the request fails, a minimal fallback entry is created.
* **Static Files** – Django’s `collectstatic` gathers CSS/JS from each app’s `static/` directory into `staticfiles/`. The dashboard relies on Chart.js (or a similar charting library) that is loaded via static tags.

---

## 6️⃣ Data Lifecycle Summary
```
Mobile client  ──►  /api/ingest/  ──►  Store → ScreenTime
                                   │            ├─► AppScreenTime (hourly)
                                   │            ├─► LocationHistory
                                   │            └─► SiteAccessLog
                                   ▼
Guardian logs in (session cookie) ──► dashboard_view
                                   │
                                   ├─► Query recent ScreenTime (30 days)
                                   │    ├─► get_app_breakdown() → AppScreenTime
                                   │    └─► aggregate totals / averages
                                   ├─► Query LocationHistory (latest 20)
                                   ├─► Query SiteAccessLog (latest 30)
                                   ▼
Template renders HTML + JS → AJAX calls to chart / stats endpoints
                                   │
                                   └─► JSON responses → charts / tables
```
All **pruning** (removing data older than 365 days) happens automatically in the `save()` methods of `ScreenTime`, `LocationHistory`, and `SiteAccessLog`.

---

## 7️⃣ Dashboard UI Component Map

| Component (template) | Purpose | Data Source |
|----------------------|---------|--------------|
| `dashboard_sidebar.html` | Navigation (links to dashboard, settings, logout) | Static |
| `add_child_modal.html` | Modal form to create a new child (POST to dashboard view) | `dashboard_view` POST handling |
| `empty_state.html` | Friendly UI when a guardian has no children | Conditional (`{% if not children %}`) |
| `select_child_prompt.html` | Prompt to pick a child; JS toggles visibility of the selected child’s dashboard | JS (`dashboard_scripts.html`) |
| `stat_card.html` | Reusable card showing a label, value, subtitle, and optional icon | `children_data.stats` |
| `screen_time_chart.html` | Line chart of daily screen‑time (hours) | `/child/<hash>/chart/` → `line_chart` |
| `app_usage_chart.html` | Bar chart of top‑5 apps (hours) | `/child/<hash>/chart/` → `bar_chart` |
| `all_apps_list.html` | Full list of apps with icons and total hours | `/child/<hash>/chart/` → `app_list` |
| `restricted_apps_manager.html` | UI to view / edit `restricted_apps` JSON (future feature) | `child.restricted_apps` |
| `location_history.html` | Table / map of recent GPS points | `/child/<hash>/locations/` |
| `site_access_log.html` | Table of recent site accesses (allowed / blocked) | `/child/<hash>/site-logs/` |
| `no_data_message.html` | Message shown when a child has no recorded data | Conditional (`{% if data.has_data %}`) |
| `dashboard_scripts.html` | JavaScript that wires up AJAX calls, chart rendering, and UI interactivity (adds `dashboard-page` class to `<body>`) | — |
| `dashboard_styles.html` | Custom CSS (dark mode, glass‑morphism, gradients, hover animations) | — |

All components are **pure Django includes**, making the dashboard highly modular and easy to extend.

---

## 8️⃣ Security & Permissions

* **Authentication** – Django’s built‑in `login_required` decorator protects every view that accesses child data.
* **Guardian‑Child Ownership** – Every query that fetches a child (`Child.objects.get(child_hash=..., guardians=request.user)`) ensures the logged‑in guardian actually owns the child.
* **CSRF** – All POST endpoints that are part of the web UI (`signup_view`, `login_view`, `delete_child`, `upload_child_profile_image`) are protected by Django’s CSRF middleware. The mobile API endpoints (`api_login`, `api_ingest`) are deliberately **CSRF‑exempt** (`@csrf_exempt`) because they are consumed by native apps.
* **Input Validation** –
  * Image uploads are validated for size (≤ 5 MB) and type (jpg, jpeg, png, gif, webp) using Pillow.
  * JSON payloads are parsed with strict error handling; missing required fields raise `ValueError`.
  * Hour values are clamped to `0 ≤ hour ≤ 23`.
* **Data Pruning** – Guarantees that stale data never accumulates, reducing attack surface for data‑exfiltration.

---

## 9️⃣ Extensibility & Maintenance

* **Adding New Metrics** – Create a new model (e.g., `BatteryHistory`) with a `store_from_dict` helper, then expose an API endpoint and extend `dashboard_view` to include the data in `children_data`.
* **Changing Storage Backend** – All model definitions are standard Django ORM; swapping SQLite for PostgreSQL only requires updating `DATABASES` in `guardianAI/settings.py` and running migrations.
* **Front‑End Enhancements** – The dashboard already uses modular includes; new visualisations can be added as separate templates and wired via `dashboard_scripts.html`.

---

## 10️⃣ Quick Reference Diagram (textual)

```
+-------------------+      POST /api/ingest/      +-------------------+
| Mobile Client     |---------------------------->| backend.views    |
| (JSON payload)   |   → store_from_* helpers    | api_ingest       |
+-------------------+                             +-------------------+
          |                                                |
          |   (creates/updates)                            |
          v                                                v
+-------------------+      DB (SQLite)      +-------------------+
|  accounts.models  |<-------------------->| backend.models   |
|  Guardian, Child |   FK/M2M relations   | ScreenTime, ...  |
+-------------------+                      +-------------------+

Guardian logs in → dashboard_view → children_data dict → dashboard.html
   |
   |-- AJAX → child_chart_data / child_stats_data / child_locations_data /
   |          child_site_logs_data → JSON → JS → Charts / Tables
   |
   +-- UI includes (stat_card, app_usage_chart, etc.) render data
```

---

## 📌 TL;DR Summary

* **Models** – `Guardian` / `Child` (accounts) + `ScreenTime`, `AppScreenTime`, `LocationHistory`, `SiteAccessLog`, `App` (backend).
* **Data Ingestion** – Mobile POST → `api_ingest` → static `store_from_*` helpers → relational tables, with 365‑day pruning.
* **Dashboard Rendering** – `dashboard_view` aggregates per‑child stats, passes them to `dashboard.html`; the template uses many reusable components and AJAX endpoints to fetch chart data.
* **Security** – Ownership checks, CSRF protection for web UI, size/type validation for uploads, and automatic data cleanup.
* **Extensibility** – New metrics can be added by defining a model + helper + API endpoint; the UI can be expanded via additional template includes.

Feel free to dive into any of the files referenced above for deeper implementation details. Happy coding! 🚀

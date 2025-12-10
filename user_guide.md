# 📖 Guardian AI – User Guide

Welcome! This guide will walk you through **setting up**, **connecting a child device**, and **using the dashboard** to monitor screen‑time, app usage, location, and web activity.

---

## 1️⃣ Prerequisites

1. **Python 3.10+** installed on your development machine.
2. **Virtual environment** (recommended) – `python -m venv venv` and activate it.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. **SQLite** is used by default, so no extra database server is required.
5. (Optional) Obtain an **OpenCage API key** for reverse‑geocoding locations and add it to `guardianAI/settings.py`:
   ```python
   OPENCAGE_API_KEY = "YOUR_KEY_HERE"
   ```

---

## 2️⃣ Running the Application Locally

```bash
# Activate the virtual environment (Windows)
venv\Scripts\activate

# Apply migrations (creates the SQLite DB)
python manage.py migrate

# Create a super‑user (optional, for admin access)
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

Open your browser and navigate to `http://127.0.0.1:8000/`. You should see the **landing page**.

---

## 3️⃣ Creating a Guardian (Parent) Account

1. Click **Sign Up** on the landing page.
2. Fill in **Email**, **Password**, and optionally **Full Name**.
3. After successful registration you will be automatically logged in and redirected to the **Dashboard**.

> **Tip:** Use a strong password; the system stores passwords securely with Django’s hashing.

---

## 4️⃣ Installing & Connecting the Child App

> The child app is a separate mobile application (Android/iOS) that sends usage data to the backend.

1. **Install the app** on the child’s device (provided by the project’s mobile repo).
2. Open the app – you will be prompted to **enter the child’s hash**.
   * The hash is generated automatically when a guardian creates a child profile (see step 5).
   * You can view the hash on the dashboard under **Child Info Card** or retrieve it via the API endpoint `GET /api/blocked-apps/<child_hash>/`.
3. After entering the hash, the app will start sending JSON payloads to the server at `http://<your‑host>/api/ingest/`.
   * The mobile app handles authentication using the guardian’s email/password via the `POST /api/login/` endpoint.
4. Verify the connection by checking the **Recent Activity** section on the dashboard – you should see the first screen‑time entry appear within a few seconds.

---

## 5️⃣ Adding a Child from the Dashboard

1. In the **Dashboard** click the **Add Child** button (opens a modal).
2. Fill in:
   * **First name** (optional)
   * **Last name** (optional)
   * **Date of birth** (optional – used for age calculation)
3. Click **Create**. The system will generate a **unique `child_hash`** and display it on the **Child Info Card**.
4. Copy this hash and give it to the child’s mobile app (step 4).

---

## 6️⃣ Dashboard Overview – Detailed Section Walk‑through

The dashboard is composed of reusable components. Below is a description of each visible area.

### 6.1 Sidebar (`dashboard_sidebar.html`)
* Navigation links: **Dashboard**, **Settings**, **Logout**.
* Highlights the currently selected child (if any).

### 6.2 Child Selector Prompt (`select_child_prompt.html`)
* Shown when the guardian has multiple children.
* Click a child’s name/card to load that child’s detailed view.

### 6.3 Child‑Specific Dashboard (`child‑{{ child_hash }}`)
Once a child is selected, the following sections appear:

#### 📊 Stat Cards (`stat_card.html`)
| Card | What it Shows | Where the data comes from |
|------|---------------|---------------------------|
| **Total Screen Time** | Cumulative screen‑time across all recorded days (e.g., `45.2h`). | `ScreenTime.total_screen_time` summed over the queried period. |
| **Average Daily** | Average screen‑time per day (e.g., `2.1h/day`). | `total / number_of_days`. |
| **Latest Location** | Human‑readable address of the most recent GPS point (city, street, country). | Reverse‑geocoded via OpenCage API from `LocationHistory`. |
| **Blocked Sites** | Number of website blocks recorded. | `SiteAccessLog` where `accessed=False`. |

#### 📈 Screen‑Time Line Chart (`screen_time_chart.html`)
* X‑axis: Dates (last 30 days by default).
* Y‑axis: Hours of screen‑time per day.
* Hover to see exact values.
* Data source: `ScreenTime` rows → `total_screen_time`.

#### 📊 App Usage Bar Chart (`app_usage_chart.html`)
* Shows **top‑5 apps** by total usage hours.
* Bars are coloured, and each bar displays the app icon (fetched from the `App` model).
* Clicking a bar could be wired to filter the line chart (future enhancement).

#### 📋 All Apps List (`all_apps_list.html`)
* A scrollable list of **all recorded apps** with:
  * App icon
  * App name (or domain if name missing)
  * Total hours used (rounded to 1 decimal place)
* Useful for spotting less‑used apps.

#### 🛡️ Restricted Apps Manager (`restricted_apps_manager.html`)
* Displays the JSON dictionary stored in `Child.restricted_apps`.
* Allows the guardian to **set a daily time limit** (in hours) per app.
* When the mobile app reports usage, the backend can automatically block the app once the limit is exceeded (logic to be added in future releases).

#### 📍 Location History (`location_history.html`)
* Table of recent GPS points (timestamp, latitude, longitude).
* Optionally rendered on a map (e.g., Leaflet) – the template includes a placeholder `<div id="map"></div>`.

#### 🌐 Site Access Log (`site_access_log.html`)
* List of recent URLs visited, with a **green check** for allowed sites and a **red cross** for blocked sites.
* Shows timestamp and URL.

#### 📄 No‑Data Message (`no_data_message.html`)
* Shown when a child has no recorded screen‑time, location, or site logs.
* Encourages the guardian to verify that the child app is correctly configured.

---

## 7️⃣ API Quick Reference (for advanced users)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/login/` | POST | Returns guardian info + list of children after validating email/password. |
| `/api/ingest/` | POST | Accepts screen‑time, location, and site‑access data for a child. |
| `/api/blocked-apps/<child_hash>/` | GET | Retrieves the `restricted_apps` dictionary for a child. |
| `/dashboard/` | GET | Renders the HTML dashboard (web UI). |
| `/child/<child_hash>/chart/` | GET | JSON for line‑chart (screen‑time) and bar‑chart (top apps). |
| `/child/<child_hash>/stats/` | GET | High‑level stats (total, avg, latest location, site counts). |
| `/child/<child_hash>/locations/` | GET | Recent GPS points. |
| `/child/<child_hash>/site-logs/` | GET | Recent site‑access entries. |

All endpoints require the guardian to be **authenticated** (session cookie for web UI, token‑less login for mobile). The child‑hash is always validated against the logged‑in guardian’s children.

---

## 8️⃣ Troubleshooting

| Issue | Possible Cause | Fix |
|-------|----------------|-----|
| **No data appears on the dashboard** | Mobile app not sending payloads or wrong `child_hash`. | Verify the hash on the Child Info Card, ensure the device can reach `http://<host>/api/ingest/`, and check server logs for errors. |
| **Location shows “No location data”** | GPS not enabled on the child device or OpenCage API key missing. | Enable location services on the device and add a valid `OPENCAGE_API_KEY` to `settings.py`. |
| **App icons are blank** | Play Store lookup failed for a new app domain. | The system falls back to a placeholder; you can manually edit the `App` entry via Django admin (`/admin/`). |
| **CSRF errors on form submission** | Session cookie missing or using an old browser tab. | Refresh the page, ensure cookies are enabled, and try again. |

---

## 9️⃣ Next Steps & Future Enhancements

* **Real‑time push notifications** when a child exceeds a restricted‑app limit.
* **Map visualisation** of location history using Leaflet or Google Maps.
* **Export reports** (PDF/CSV) for weekly or monthly summaries.
* **Multi‑guardian sharing** – invite another guardian to manage the same child.

---

### 🎉 You’re Ready!

You now have a fully functional parental‑control system:
1. **Create** a guardian account.
2. **Add** a child and obtain its hash.
3. **Install** the child app and configure the hash.
4. **Monitor** everything from the beautiful dashboard.

Enjoy the peace of mind that comes with clear, actionable insights into your child’s digital habits! 🚀

---

*For any questions or contributions, feel free to open an issue on the project’s GitHub repository.*

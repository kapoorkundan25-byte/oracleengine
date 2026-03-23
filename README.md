# OracleEngine

A publicly accessible ASP.NET Core MVC website where:
- **Public visitors** can browse all pages without any account
- **Only the admin** (you) can log in and manage site settings
- Regular visitors are **read-only** — they cannot change anything

## Screenshots

**Public Home Page**
![Home Page](https://github.com/user-attachments/assets/849e1646-0b36-4b31-863d-7c5d27592656)

**Admin Login**
![Admin Login](https://github.com/user-attachments/assets/c7cf783d-7056-4f71-84f5-f7948e4ee113)

**Admin Settings Panel**
![Admin Settings](https://github.com/user-attachments/assets/890844d3-eddd-4604-9685-31209d17b19f)

---

## Getting Started

### Prerequisites

- [.NET 10 SDK](https://dotnet.microsoft.com/download)

### Run Locally

```bash
cd OracleEngine
dotnet run
```

The site will be available at `http://localhost:5169` (or the port shown in the terminal).

### Default Admin Credentials

| Field    | Value                |
|----------|----------------------|
| Username | `admin`              |
| Password | `Admin@Oracle#2026`  |

> **Important:** Change the admin password immediately after first login via the **Settings** page.

---

## How It Works

| Who          | What they can do                          |
|--------------|-------------------------------------------|
| Anyone       | View Home page, Privacy page              |
| Admin only   | Log in at `/Account/Login`, change site title, description, welcome message, contact email, and admin password |

### Access Control

- All public pages (`/`, `/Home/Privacy`) are accessible without login.
- The admin area (`/Admin/Settings`) requires authentication.
- Unauthenticated users who try to visit `/Admin/Settings` are automatically redirected to the login page and brought back after a successful login.
- The **Logout** button ends the admin session immediately.

### Settings Storage

Site content settings (title, description, welcome message, contact email) are saved to `site-settings.json` in the application root. The admin password hash is also stored there after the first password change.

The initial admin password hash is seeded from `appsettings.json` on first run.

---

## Deploying to Production (Live on the Internet)

### Option 1 — Azure App Service

```bash
cd OracleEngine
dotnet publish -c Release -o ./publish
# Then deploy the ./publish folder to Azure App Service
```

### Option 2 — Self-Hosted Linux Server (e.g. Ubuntu + nginx)

```bash
# Publish
cd OracleEngine
dotnet publish -c Release -o /var/www/oracleengine

# Create systemd service
sudo nano /etc/systemd/system/oracleengine.service
```

```ini
[Unit]
Description=OracleEngine ASP.NET Core App

[Service]
WorkingDirectory=/var/www/oracleengine
ExecStart=/usr/bin/dotnet /var/www/oracleengine/OracleEngine.dll
Restart=always
RestartSec=10
KillSignal=SIGINT
SyslogIdentifier=oracleengine
User=www-data
Environment=ASPNETCORE_ENVIRONMENT=Production
Environment=ASPNETCORE_URLS=http://localhost:5000

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable oracleengine
sudo systemctl start oracleengine
```

Then configure **nginx** as a reverse proxy to expose port 80/443. Use **Let's Encrypt** (certbot) for a free HTTPS certificate.

### Option 3 — Docker

```bash
cd OracleEngine
dotnet publish -c Release -o ./publish
docker build -t oracleengine .
docker run -p 8080:80 oracleengine
```

---

## Security Notes

- Admin password is stored as a **PBKDF2-SHA256** hash (100,000 iterations) — never stored in plain text.
- All admin forms use **anti-forgery tokens** (CSRF protection).
- The login redirect uses `Url.IsLocalUrl()` to prevent open redirect attacks.
- Admin cookies are `HttpOnly` to prevent JavaScript access.

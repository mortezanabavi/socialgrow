<<<<<<< HEAD
# 🚀 SocialGrow - Social Media Services & E-Commerce Platform

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2%20%7C%205.1-green)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**SocialGrow** is a full-featured e-commerce and social media marketing platform built with **Django** and **Bootstrap**. It enables automated online purchasing of social media services (Instagram, Telegram, Twitter, YouTube, etc.) with real-time price calculations, automated discounts, SMS OTP verification, and multiple payment gateway options.

---

## ✨ Features

- 📱 **Multi-Service Catalog:** Instagram (Followers, Likes, Views, Story Views), Telegram (Members, Reactions, Stars), Twitter, YouTube.
- ⚡ **Dynamic Order Pricing:** Real-time quantity-based pricing, volume tiers, and bump offers.
- 🔐 **Authentication & Security:** Phone OTP login & registration via SMS (Sms.ir / IPPanel), reCAPTCHA protection.
- 💳 **Wallet & Payment Gateways:** Online payment gateway integration (Zarinpal), digital wallet balance top-up, card-to-card tracking.
- 🎟 **Coupon & Discount Engine:** Percentage and fixed discount codes with minimum order amount & expiration rules.
- 💬 **Live Customer Support:** Support ticket tracking system with ticket replies and real-time live chat widget.
- 📝 **SEO Blog & Content Hub:** Full-featured blog with categories, tags, Jalali Persian date formatting, and CKEditor 5.
- 🔍 **Tracking System:** Real-time order tracking and refill (drop compensation) requests.
- 📱 **Responsive UI:** Clean, mobile-first Persian RTL Bootstrap interface.

---

## 🏗️ Project Architecture

```text
socialgrow/
├── accounts/               # Custom user model, OTP authentication, user profile & wallet
├── blog/                   # Blog articles, categories, tags, related products
├── social/                 # Services catalog, order processing, tickets, payment gateways, live chat
├── socialgrow/             # Django root settings, URL configuration, WSGI/ASGI
├── templates/              # HTML5 templates (Jinja/Django template engine)
├── static/                 # CSS, JavaScript, fonts, and frontend assets
├── fixtures/               # Initial demo products and settings (initial_data.json)
├── manage.py               # Django CLI management script
├── requirements.txt        # Python package dependencies
├── .env.example            # Sample environment variables configuration
└── .gitignore              # Git ignore rules for clean repository
```

---

## 🚀 Quick Start / Installation Guide

Follow these steps to set up and run the project locally on your machine.

### 1. Prerequisites
- **Python 3.10+** installed
- **Git** installed

### 2. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/socialgrow.git
cd socialgrow
```

### 3. Create and Activate Virtual Environment
**Windows (PowerShell / CMD):**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```
Edit `.env` to customize your secret keys, SMS credentials, and database settings (by default, it uses SQLite with zero configuration needed).

### 6. Run Migrations
```bash
python manage.py migrate
```

### 7. (Optional) Load Initial Demo Products
To populate the database with default social media products and categories:
```bash
python manage.py loaddata fixtures/initial_data.json
```

### 8. Create Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 9. Start Development Server
```bash
python manage.py runserver
```
Visit **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser.  
Access the Django Admin panel at **[http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)**.

---

## ⚙️ Environment Variables Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SECRET_KEY` | `(insecure default)` | Django secret encryption key |
| `DEBUG` | `True` | Set to `False` in production |
| `ALLOWED_HOSTS` | `*` | Comma-separated list of allowed hostnames |
| `DB_ENGINE` | `sqlite3` | Choose `sqlite3` or `mysql` |
| `DB_NAME` | `socialgrow` | MySQL database name |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | `""` | MySQL password |
| `DB_HOST` | `127.0.0.1` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `SMS_API_KEY` | `""` | SMS.ir / IPPanel API key |
| `SMS_TEMPLATE_OTP` | `559599` | SMS template ID for OTP verification |
| `ZARINPAL_MERCHANT`| `""` | Zarinpal merchant ID for online payments |
| `RECAPTCHA_SECRET_KEY`| `""` | Google reCAPTCHA v2/v3 secret key |

---

## 📄 License
This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

=======
# socialgrow
>>>>>>> cc94b7fedf075661f22e187100616cef69308c73

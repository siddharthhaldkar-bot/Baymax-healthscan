# Baymax HealthScan

Baymax HealthScan is a production-quality food health analysis platform. Inspired by Baymax, it serves as a personal food health companion, helping users analyze barcodes, inspect nutritional profiles, flag ingredients of concern, and receive personalized AI health assessments powered by the Google Gemini API.

## Core Features
1. **Barcode Scanning**: Scan product barcodes using your device camera or input them manually.
2. **Product Information Retrieval**: Fetches name, brand, image, ingredients, and nutrients from the Open Food Facts API.
3. **AI Health Analysis**: Evaluates ingredients/nutrients against the user's specific health goals using Google Gemini.
4. **Baymax Health Report Dashboard**: A beautiful dashboard on the Profile page aggregating your purchased items to display average diet scores, consumption progress charts, concern ingredients, and personalized recommendations.
5. **Purchase Confirmation Log**: Scanning items is transient; only items marked as purchased are saved to your database log to optimize storage.
6. **Multilingual Support**: Switch seamlessly between English, Hindi, and Marathi.

---

## Tech Stack
- **Backend**: Django 4.2+, Django REST Framework (DRF)
- **Database**: SQLite (for MVP)
- **Frontend**: JavaScript (ES6+), Bootstrap 5, Vanilla CSS (Glassmorphism, custom typography)
- **Integrations**: Open Food Facts API, Google Gemini API

---

## Installation & Setup

### 1. Clone & Navigate
Navigate into the workspace root directory:
```bash
cd /media/sid/960C00930C007093/BAYMAXXXXX
```

### 2. Configure Environment Variables
Copy the template environment file to `.env`:
```bash
cp .env.example .env
```
Open `.env` and configure your API key:
- `GEMINI_API_KEY`: Your official Google AI studio key.
*Note: If no API key is provided, the application automatically falls back to a high-quality local analysis service, allowing full testing of goal personalization and multilingual translations immediately.*

### 3. Install Dependencies
It is recommended to run in a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Run Migrations & Setup Database
Build the database structure and create your local admin user:
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Start Server
Run the local Django development server:
```bash
python manage.py runserver
```
Visit the application in your browser at `http://127.0.0.1:8000/`.

---

## Running Tests
To run the automated test suite verifying models, signals, views, and integrations:
```bash
python manage.py test
```

---

## Usage Guide
1. **Register or Login**: Go to `http://127.0.0.1:8000/register/` to sign up.
2. **Onboarding**: Upon first-time login, configure your health goal (e.g., Weight Loss) and preferred language (e.g., Hindi) in the welcoming onboarding popup.
3. **Scan a Product**: Go to the **Scan Barcode** page, start the camera scanner, or enter a barcode manually (e.g. `3017620422003` for Nutella).
4. **Mark as Purchased**: On the Results page, review the AI analysis, and log the item to your health history by clicking **"Yes, I bought it"** on the purchase prompt.
5. **View Health Report**: Go to the **Profile** page to view your **🩺 Baymax Health Report Dashboard** showing your average diet score, consumption breakdown, most frequent concern ingredients, and AI eating pattern analysis.
6. **Save Products**: Click **Save Product** on the top right of the Results page to bookmark items.

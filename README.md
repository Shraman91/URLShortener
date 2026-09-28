# Premium URL Shortener

A fast, beautiful, and secure URL shortener built with FastAPI (Python) and Next.js (TypeScript), powered by Firebase.

## Features
- **Advanced Options**: Custom aliases, password protection, expiration dates, and click limits.
- **Analytics**: Detailed click tracking including referrers, browsers, and devices.
- **User Accounts**: Manage your shortened URLs via a dedicated dashboard.
- **QR Codes**: Automatically generated QR codes for your short links.
- **API Key Access**: Support for bulk shortening via API keys.
- **Premium Design**: Modern, responsive UI with an off-white/maroon aesthetic.

---

## Local Setup Instructions

### 1. Firebase Configuration

You need a Firebase project with Authentication and Firestore enabled.

1. Go to the [Firebase Console](https://console.firebase.google.com/) and create a new project.
2. Navigate to **Authentication** > **Sign-in method** and enable **Email/Password** and **Google** sign-in providers.
3. Navigate to **Firestore Database** and create a new database.
4. **Backend (Admin SDK):**
   - Go to Project Settings > Service Accounts.
   - Click "Generate new private key". This will download a JSON file.
   - Rename this file to `serviceAccountKey.json` and place it in the `backend/` directory of this project. (See `backend/serviceAccountKey.json.example` for the expected format).
5. **Frontend (Client SDK):**
   - Go to Project Settings > General.
   - Under "Your apps", click the Web icon (</>) to add a new web app.
   - Copy the configuration object provided (apiKey, authDomain, etc.).
   - Create a `.env.local` file in the `frontend/` directory and add the following variables based on your config:
     ```
     NEXT_PUBLIC_FIREBASE_API_KEY=your_api_key
     NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_auth_domain
     NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
     NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your_storage_bucket
     NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
     NEXT_PUBLIC_FIREBASE_APP_ID=your_app_id
     ```

### 2. Backend Setup (FastAPI)

1. Open a terminal and navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the development server:
   ```bash
   uvicorn main:app --reload
   ```
   The backend will be running at `http://localhost:8000`.

### 3. Frontend Setup (Next.js)

1. Open a new terminal and navigate to the frontend folder:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   The frontend will be running at `http://localhost:3000`.

---

## Security Rules

To secure your Firestore database, deploy the rules in `backend/firestore.rules`. Since this application uses the Firebase Admin SDK on the backend for all direct database operations, client-side writes should be completely disabled.

You can set these rules in the "Rules" tab of the Firestore Database in your Firebase Console:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /urls/{urlCode} {
      allow read, write: if false; 
    }
    match /api_keys/{key} {
      allow read, write: if false;
    }
  }
}
```

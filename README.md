# ResqNet - Disaster Call Management System

A real-time disaster call management platform that enables efficient incident tracking and prioritization through a modern web interface and Python backend.

## Project Structure

```
├── Frontend/          # React + Vite web application
├── Backend/           # Python application
└── README.md          # This file
```

## Frontend

**Location**: `Frontend/`

A React-based web application built with Vite for managing and visualizing disaster incidents in real-time.

### Features
- **Dashboard**: Displays all incidents sorted by priority (critical → low)
- **Incident Cards**: Individual incident details with priority badges
- **Audio Recorder**: Record and submit call recordings
- **Stats Bar**: Real-time statistics and metrics
- **Live Updates**: Real-time incident feed using Supabase subscriptions

### Technology Stack
- **React** 18.3.1 - UI framework
- **Vite** 5.3.1 - Build tool and dev server
- **Supabase** 2.43.0 - Backend-as-a-service (database & real-time)
- **ESLint** - Code linting

### Available Scripts
```bash
npm run dev      # Start development server (usually on http://localhost:5173)
npm run build    # Create production build
npm run preview  # Preview the production build locally
```

### Setup
1. Navigate to `Frontend/` directory
2. Install dependencies: `npm install`
3. Create `Frontend/.env` with `VITE_API_URL=http://localhost:8000`
4. Run `npm run dev` to start the development server (http://localhost:5173)

Agent login/signup uses the backend API (no Supabase anon key required in the frontend).

### Components
- **App.jsx** - Main application component with clock and incident state management
- **Dashboard.jsx** - Displays incidents sorted by priority
- **IncidentCard.jsx** - Individual incident card component
- **AudioRecorder.jsx** - Audio recording functionality
- **StatsBar.jsx** - Statistics display component

## Backend

**Location**: `Backend/`

Python application for processing incidents and managing data logic.

### Components
- **main.py** - Main entry point
- **priority.py** - Incident priority management logic
- **valsea.py** - Core incident processing
- **supabase_client.py** - Supabase database client
- **requirements.txt** - Python dependencies

### Setup
1. Navigate to `Backend/` directory
2. Create venv: `python3 -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `Backend/.env.example` to `Backend/.env` and set:
   - `SUPABASE_URL` — project URL only (e.g. `https://YOUR_REF.supabase.co`, not `/rest/v1/`)
   - `SUPABASE_KEY` — service role / secret key (server only)
   - `GEMINI_API_KEY`, `VALSEA_API_KEY`
5. In Supabase Dashboard → SQL Editor, run `supabase_schema.sql` from the repo root
6. Run: `uvicorn main:app --reload` (from the `Backend/` directory)

## Project Info

- **Name**: ResqNet
- **Type**: Disaster Call Management System
- **Status**: In Development

## Testing Agent Account

- **Email**: agent@gmail.com
- **Password**: agent123

## Deployment

- **Agent Dashboard Frontend URL**: https://resqnetfrontend.vercel.app
- **Telegram Bot Username**: @GitGud_ResQNet_bot

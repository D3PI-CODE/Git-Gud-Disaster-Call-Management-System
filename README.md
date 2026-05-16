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
3. Create a `.env` file with:
   ```
   VITE_SUPABASE_URL=your_supabase_url
   VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
   ```
4. Run `npm run dev` to start the development server

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
2. Install dependencies: `pip install -r requirements.txt`
3. Configure Supabase credentials in environment variables
4. Run: `python main.py`

## Project Info

- **Name**: ResqNet
- **Type**: Disaster Call Management System
- **Status**: In Development
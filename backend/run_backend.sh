#!/bin/bash

# Kill any existing process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 1

# Navigate to the backend directory
cd /Users/mayankkumar/Desktop/Full\ control\ Final\ copy/backend

# Run the backend server using uvicorn
./venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000


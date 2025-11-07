# News Processing Web App

This is a clean deployment package containing only the essential files.

## Deploy to Render

1. Push this directory to GitHub
2. Go to https://render.com
3. Create new Web Service
4. Use these settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`
   - Environment: Python 3

## Local Development

```bash
python -m uvicorn backend.api.main:app --reload
```

## Features

- 5 STT Model Selection
- Real-time News Processing
- Text-to-Speech for Keypoints
- Mobile-optimized Interface

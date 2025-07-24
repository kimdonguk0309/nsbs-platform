#!/bin/bash
# Backend 서버 실행 (FastAPI + Uvicorn)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# Frontend 서버 실행 (Streamlit)
streamlit run frontend/app.py --server.port 8501

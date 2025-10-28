# Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

# This line forces a clean build to avoid storage errors
ENV CACHE_BUSTER=1 
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HF_HOME=/tmp/.cache/huggingface/
ENV PORT=7860

CMD ["python", "backend/app.py"]
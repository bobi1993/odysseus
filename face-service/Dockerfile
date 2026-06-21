# face-service/Dockerfile
# Lightweight ArcFace ONNX inference service — memory capped at 5GB
FROM python:3.11-slim

# System deps: OpenCV (headless) for frame extraction, ffmpeg for keyframe probing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-dri \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for model cache, uploads, keyframes
RUN mkdir -p /app/models /app/uploads /app/keyframes

# Non-root user for security
RUN useradd -m -u 1000 facesvc && \
    chown -R facesvc:facesvc /app
USER facesvc

EXPOSE 8050

# Healthcheck — lightweight model-info endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8050/api/health', timeout=5)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8050", "--workers", "1"]

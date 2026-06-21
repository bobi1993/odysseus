#!/usr/bin/env python3
"""
Local AI Suite Backend — FastAPI server that orchestrates all AI tools.

Provides REST API for:
- Vision: face detection, OCR, image analysis, object detection
- Audio: speech-to-text, text-to-speech
- Text: LLM chat, embeddings, code execution
- Video: frame extraction, scene detection, face clustering
- Chain: multi-step processing pipelines

Usage:
    python3 ai_suite_backend.py
"""

import os, sys, json, asyncio, logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("ai_backend")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DATA_DIR = Path(__file__).parent / "data" / "ai_suite"
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Local AI Suite", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ═══════════════════════════════════════════════════════════════════════════
# VISION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/vision/analyze")
async def analyze_image(path: str):
    """Analyze image: metadata, colors, faces."""
    try:
        import cv2, numpy as np
        from PIL import Image
        from collections import Counter

        img = Image.open(path)
        cv_img = cv2.imread(path)
        if cv_img is None:
            raise HTTPException(400, "Cannot read image")

        # Metadata
        result = {
            "path": path,
            "width": img.width, "height": img.height,
            "mode": img.mode, "format": img.format,
            "size_bytes": os.path.getsize(path),
        }

        # Colors
        pixels = list(img.getdata())
        if img.mode == "RGBA": pixels = [(r,g,b) for r,g,b,a in pixels]
        elif img.mode == "L": pixels = [(p,p,p) for p in pixels]
        elif img.mode == "P": img = img.convert("RGB"); pixels = list(img.getdata())
        quantized = [(r//32*32, g//32*32, b//32*32) for r,g,b in pixels[:10000]]
        result["colors"] = [{"rgb": list(c), "hex": "#{:02x}{:02x}{:02x}".format(*c)} for c,n in Counter(quantized).most_common(5)]

        # Face detection
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(30,30))
        result["faces"] = [{"bbox": [int(x),int(y),int(w),int(h)]} for x,y,w,h in faces]

        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/vision/ocr")
async def ocr_image(path: str):
    """Extract text from image."""
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(path))
        return {"text": text.strip()}
    except ImportError:
        raise HTTPException(501, "OCR not available — install pytesseract")


@app.post("/api/vision/describe")
async def describe_image(body: dict):
    """Describe image using vision LLM."""
    try:
        import base64, httpx
        path = body.get("path")
        model = body.get("model", "llama3.2:latest")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json={
            "model": model, "stream": False,
            "messages": [{"role": "user", "content": "Describe this image in detail.", "images": [b64]}]
        }, timeout=120)
        if r.status_code == 200:
            return {"description": r.json().get("message", {}).get("content", "")}
        raise HTTPException(500, "LLM error")
    except Exception as e:
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# AUDIO ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/audio/transcribe")
async def transcribe_audio(path: str, model: str = "base"):
    """Transcribe audio to text."""
    try:
        import whisper
        w = whisper.load_model(model)
        result = w.transcribe(path)
        return {"text": result.get("text", "").strip()}
    except ImportError:
        raise HTTPException(501, "Whisper not available")


@app.post("/api/audio/tts")
async def text_to_speech(body: dict):
    """Text to speech."""
    try:
        from gtts import gTTS
        text = body.get("text", "")
        output = body.get("output", str(DATA_DIR / "tts_output.mp3"))
        gTTS(text=text, lang="en").save(output)
        return {"path": output}
    except ImportError:
        raise HTTPException(501, "TTS not available")


# ═══════════════════════════════════════════════════════════════════════════
# TEXT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/text/chat")
async def chat(body: dict):
    """Chat with LLM."""
    try:
        import httpx
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json={
            "model": body.get("model", "llama3.2:latest"),
            "messages": body.get("messages", []),
            "stream": False,
        }, timeout=300)
        if r.status_code == 200:
            return r.json().get("message", {}).get("content", "")
        raise HTTPException(500, "LLM error")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/text/embed")
async def embed(body: dict):
    """Generate embeddings."""
    try:
        import httpx
        texts = body.get("texts", [])
        results = []
        for t in texts:
            r = httpx.post(f"{OLLAMA_URL}/api/embeddings", json={"model": "nomic-embed-text", "prompt": t}, timeout=60)
            if r.status_code == 200:
                results.append(r.json().get("embedding", []))
        return {"embeddings": results}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/text/execute")
async def execute_code(body: dict):
    """Execute Python code."""
    import subprocess
    code = body.get("code", "")
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
        return {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout"}


# ═══════════════════════════════════════════════════════════════════════════
# VIDEO ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/video/frames")
async def extract_frames(path: str, interval: float = 1.0, output_dir: Optional[str] = None):
    """Extract frames from video."""
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        fi = int(fps * interval)
        fc = 0
        frames = []
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        while True:
            ret, frame = cap.read()
            if not ret: break
            if fc % fi == 0:
                if output_dir:
                    p = os.path.join(output_dir, f"frame_{fc:06d}.jpg")
                    cv2.imwrite(p, frame)
                    frames.append(p)
                else:
                    frames.append(fc)
            fc += 1
        cap.release()
        return {"frames": frames, "total": len(frames)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/video/scenes")
async def detect_scenes(path: str, threshold: float = 30.0):
    """Detect scene changes."""
    try:
        import cv2, numpy as np
        cap = cv2.VideoCapture(path)
        prev = None
        scenes = []
        fn = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev is not None:
                diff = np.mean(np.abs(gray.astype(float) - prev.astype(float)))
                if diff > threshold:
                    scenes.append({"frame": fn, "timestamp": fn/cap.get(cv2.CAP_PROP_FPS), "diff": float(diff)})
            prev = gray
            fn += 1
        cap.release()
        return {"scenes": scenes}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/video/faces")
async def extract_faces(path: str, interval: float = 2.0, output_dir: Optional[str] = None):
    """Extract faces from video."""
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        fi = int(fps * interval)
        fc = 0
        fn = 0
        faces = []
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        while True:
            ret, frame = cap.read()
            if not ret: break
            if fc % fi == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                for (x,y,w,h) in cascade.detectMultiScale(gray, 1.1, 5):
                    face = frame[y:y+h, x:x+w]
                    if output_dir:
                        p = os.path.join(output_dir, f"face_{fn:06d}.jpg")
                        cv2.imwrite(p, face)
                        faces.append({"path": p, "frame": fc, "bbox": [x,y,w,h]})
                    else:
                        faces.append({"frame": fc, "bbox": [x,y,w,h]})
                    fn += 1
            fc += 1
        cap.release()
        return {"faces": faces, "total": len(faces)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# CHAIN ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/chain/run")
async def run_chain(body: dict):
    """Run a multi-step processing chain."""
    input_data = body.get("input")
    current = input_data
    results = {"input": input_data, "steps": {}, "output": None}

    for step in body.get("steps", []):
        name = step.get("name", "unnamed")
        tool = step.get("tool")
        params = step.get("params", {})
        try:
            # Resolve and call tool
            func = _resolve_tool(tool)
            if func:
                import asyncio
                if asyncio.iscoroutinefunction(func):
                    current = await func(current, **params) if params else await func(current)
                else:
                    current = func(current, **params) if params else func(current)
                results["steps"][name] = {"status": "ok"}
            else:
                results["steps"][name] = {"status": "error", "error": f"Unknown tool: {tool}"}
        except Exception as e:
            results["steps"][name] = {"status": "error", "error": str(e)}
            break

    results["output"] = current
    return results


def _resolve_tool(name: str):
    """Resolve tool name to function."""
    import cv2, numpy as np
    from PIL import Image
    from collections import Counter

    def analyze_image(path):
        img = Image.open(path)
        pixels = list(img.getdata())
        if img.mode == "RGBA": pixels = [(r,g,b) for r,g,b,a in pixels]
        quantized = [(r//32*32, g//32*32, b//32*32) for r,g,b in pixels[:10000]]
        return {"path": path, "width": img.width, "height": img.height,
                "colors": [{"rgb": list(c)} for c,n in Counter(quantized).most_common(5)]}

    def detect_faces(path):
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        return [{"bbox": [int(x),int(y),int(w),int(h)]} for x,y,w,h in cascade.detectMultiScale(gray, 1.1, 5)]

    def extract_frames(path, interval=1.0, output_dir=None):
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        fi = int(fps * interval)
        frames = []
        fc = 0
        if output_dir: Path(output_dir).mkdir(parents=True, exist_ok=True)
        while True:
            ret, frame = cap.read()
            if not ret: break
            if fc % fi == 0:
                if output_dir:
                    p = os.path.join(output_dir, f"frame_{fc:06d}.jpg")
                    cv2.imwrite(p, frame)
                    frames.append(p)
                else:
                    frames.append(fc)
            fc += 1
        cap.release()
        return frames

    tools = {
        "analyze_image": analyze_image,
        "detect_faces": detect_faces,
        "extract_frames": extract_frames,
    }
    return tools.get(name)


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the face recognition dashboard."""
    html_path = DATA_DIR / "face_dashboard.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    raise HTTPException(404, "Dashboard not found")


@app.get("/api/status")
async def status():
    """Suite status."""
    return {
        "status": "ok",
        "ollama_url": OLLAMA_URL,
        "data_dir": str(DATA_DIR),
        "endpoints": [
            "/api/vision/analyze", "/api/vision/ocr", "/api/vision/describe",
            "/api/audio/transcribe", "/api/audio/tts",
            "/api/text/chat", "/api/text/embed", "/api/text/execute",
            "/api/video/frames", "/api/video/scenes", "/api/video/faces",
            "/api/chain/run",
            "/dashboard",
        ]
    }


if __name__ == "__main__":
    port = int(os.getenv("AI_SUITE_PORT", "3002"))
    log.info(f"Starting AI Suite on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

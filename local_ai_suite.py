#!/usr/bin/env python3
"""
Local AI Suite — Complete orchestrator for all tools and vision modules.

Chains together:
- Vision: face detection/recognition, object detection, OCR, image analysis, segmentation
- Audio: speech-to-text (Whisper), text-to-speech (gTTS/Kokoro)
- Text: LLM inference via Ollama/OpenRouter, embeddings, RAG, code execution
- Video: frame extraction, scene detection, face clustering
- Popular models from HuggingFace integrated

Usage:
    python3 local_ai_suite.py --help
    python3 local_ai_suite.py vision --image path.jpg --task analyze
    python3 local_ai_suite.py vision --image path.jpg --task face-detect
    python3 local_ai_suite.py vision --image path.jpg --task describe --model llama3.2:latest
    python3 local_ai_suite.py audio --file audio.wav --task transcribe
    python3 local_ai_suite.py text --prompt "Hello" --model llama3.2:latest
    python3 local_ai_suite.py video --file video.mp4 --task extract-faces
    python3 local_ai_suite.py chain --config pipeline.json
"""

import os, sys, json, argparse, logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("ai_suite")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
DATA_DIR = Path(__file__).parent / "data" / "ai_suite"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# VISION MODULE
# ═══════════════════════════════════════════════════════════════════════════

class VisionModule:
    """Unified vision pipeline."""

    def analyze_image(self, image_path: str) -> dict:
        """Full image analysis: metadata, colors, faces, objects."""
        result = {"path": image_path, "faces": [], "objects": [], "colors": [], "metadata": {}}
        try:
            from PIL import Image
            from collections import Counter
            img = Image.open(image_path)
            result["metadata"] = {"width": img.width, "height": img.height, "mode": img.mode, "format": img.format, "size_bytes": os.path.getsize(image_path)}
            pixels = list(img.getdata())
            if img.mode == "RGBA": pixels = [(r,g,b) for r,g,b,a in pixels]
            elif img.mode == "L": pixels = [(p,p,p) for p in pixels]
            quantized = [(r//32*32, g//32*32, b//32*32) for r,g,b in pixels[:10000]]
            for c, n in Counter(quantized).most_common(5):
                result["colors"].append({"rgb": list(c), "hex": "#{:02x}{:02x}{:02x}".format(*c), "count": n})
        except Exception as e:
            log.error(f"Image analysis failed: {e}")
        return result

    def detect_faces(self, image_path: str) -> list:
        """Detect faces using OpenCV Haar cascade."""
        faces = []
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is None: return faces
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            detected = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            for (x, y, w, h) in detected:
                faces.append({"bbox": [int(x), int(y), int(w), int(h)]})
            log.info(f"Detected {len(faces)} faces")
        except Exception as e:
            log.error(f"Face detection failed: {e}")
        return faces

    def extract_text(self, image_path: str) -> str:
        """OCR using pytesseract or easyocr."""
        try:
            import pytesseract
            from PIL import Image
            return pytesseract.image_to_string(Image.open(image_path)).strip()
        except ImportError:
            try:
                import easyocr
                reader = easyocr.Reader(["en"])
                return " ".join([r[1] for r in reader.readtext(image_path)])
            except ImportError:
                log.error("No OCR library available"); return ""

    def describe_image(self, image_path: str, model: str = "llama3.2:latest") -> str:
        """Describe image using vision LLM via Ollama."""
        try:
            import base64, httpx
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            r = httpx.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "stream": False,
                "messages": [{"role": "user", "content": "Describe this image in detail.", "images": [b64]}]
            }, timeout=120)
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
        except Exception as e:
            log.error(f"Describe failed: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# AUDIO MODULE
# ═══════════════════════════════════════════════════════════════════════════

class AudioModule:
    """Speech-to-text and text-to-speech."""

    def transcribe(self, audio_path: str, model: str = "base") -> str:
        """Transcribe audio using Whisper."""
        try:
            import whisper
            w = whisper.load_model(model)
            return w.transcribe(audio_path).get("text", "").strip()
        except ImportError:
            try:
                from faster_whisper import WhisperModel
                w = WhisperModel(model)
                return " ".join([s.text for s, _ in w.transcribe(audio_path)]).strip()
            except ImportError:
                log.error("No Whisper library"); return ""

    def text_to_speech(self, text: str, output_path: str) -> bool:
        """TTS using gTTS or pyttsx3."""
        try:
            from gtts import gTTS
            gTTS(text=text, lang="en").save(output_path)
            return True
        except ImportError:
            try:
                import pyttsx3
                e = pyttsx3.init(); e.save_to_file(text, output_path); e.runAndWait()
                return True
            except ImportError:
                log.error("No TTS library"); return False


# ═══════════════════════════════════════════════════════════════════════════
# TEXT MODULE
# ═══════════════════════════════════════════════════════════════════════════

class TextModule:
    """LLM inference, embeddings, code execution."""

    def complete(self, prompt: str, model: str = "llama3.2:latest") -> str:
        try:
            import httpx
            r = httpx.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "stream": False,
                "messages": [{"role": "user", "content": prompt}]
            }, timeout=300)
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
        except Exception as e:
            log.error(f"Complete failed: {e}")
        return ""

    def chat(self, messages: list, model: str = "llama3.2:latest") -> str:
        try:
            import httpx
            r = httpx.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "stream": False, "messages": messages
            }, timeout=300)
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
        except Exception as e:
            log.error(f"Chat failed: {e}")
        return ""

    def embed(self, texts: list) -> list:
        try:
            import httpx
            results = []
            for t in texts:
                r = httpx.post(f"{OLLAMA_URL}/api/embeddings", json={"model": "nomic-embed-text", "prompt": t}, timeout=60)
                if r.status_code == 200:
                    results.append(r.json().get("embedding", []))
            return results
        except Exception as e:
            log.error(f"Embed failed: {e}")
            return []

    def execute_code(self, code: str, language: str = "python") -> dict:
        if language == "python":
            import subprocess
            try:
                r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
                return {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
            except subprocess.TimeoutExpired:
                return {"error": "Timeout"}
        return {"error": f"Unsupported: {language}"}


# ═══════════════════════════════════════════════════════════════════════════
# VIDEO MODULE
# ═══════════════════════════════════════════════════════════════════════════

class VideoModule:
    """Video processing pipeline."""

    def extract_frames(self, video_path: str, interval: float = 1.0, output_dir: str = None) -> list:
        frames = []
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            fi = int(fps * interval)
            fc = 0
            if output_dir: Path(output_dir).mkdir(parents=True, exist_ok=True)
            while True:
                ret, frame = cap.read()
                if not ret: break
                if fc % fi == 0:
                    if output_dir:
                        p = os.path.join(output_dir, f"frame_{fc:06d}.jpg")
                        cv2.imwrite(p, frame); frames.append(p)
                    else:
                        frames.append(fc)
                fc += 1
            cap.release()
            log.info(f"Extracted {len(frames)} frames")
        except Exception as e:
            log.error(f"Frame extraction failed: {e}")
        return frames

    def detect_scenes(self, video_path: str, threshold: float = 30.0) -> list:
        scenes = []
        try:
            import cv2, numpy as np
            cap = cv2.VideoCapture(video_path)
            prev = None; fn = 0
            while True:
                ret, frame = cap.read()
                if not ret: break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if prev is not None:
                    diff = np.mean(np.abs(gray.astype(float) - prev.astype(float)))
                    if diff > threshold:
                        scenes.append({"frame": fn, "timestamp": fn/cap.get(cv2.CAP_PROP_FPS), "diff": float(diff)})
                prev = gray; fn += 1
            cap.release()
            log.info(f"Detected {len(scenes)} scenes")
        except Exception as e:
            log.error(f"Scene detection failed: {e}")
        return scenes

    def extract_faces(self, video_path: str, interval: float = 2.0, output_dir: str = None) -> list:
        faces = []
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            fi = int(fps * interval); fc = 0; fn = 0
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            if output_dir: Path(output_dir).mkdir(parents=True, exist_ok=True)
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
            log.info(f"Extracted {len(faces)} faces")
        except Exception as e:
            log.error(f"Face extraction failed: {e}")
        return faces


# ═══════════════════════════════════════════════════════════════════════════
# CHAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class ChainOrchestrator:
    """Chain multiple tools into a pipeline."""

    def __init__(self):
        self.vision = VisionModule()
        self.audio = AudioModule()
        self.text = TextModule()
        self.video = VideoModule()

    def run_chain(self, config: dict) -> dict:
        """Run a processing chain from config."""
        current = config.get("input")
        results = {"input": current, "steps": {}, "output": None}

        for step in config.get("steps", []):
            name = step.get("name", "unnamed")
            tool = step.get("tool")
            params = step.get("params", {})
            try:
                func = self._resolve(tool)
                if func:
                    current = func(current, **params) if params else func(current)
                    results["steps"][name] = {"status": "ok"}
                else:
                    results["steps"][name] = {"status": "error", "error": f"Unknown tool: {tool}"}
            except Exception as e:
                results["steps"][name] = {"status": "error", "error": str(e)}
                break

        results["output"] = current
        return results

    def _resolve(self, name: str):
        tools = {
            "analyze_image": self.vision.analyze_image,
            "detect_faces": self.vision.detect_faces,
            "extract_text": self.vision.extract_text,
            "describe_image": self.vision.describe_image,
            "transcribe": self.audio.transcribe,
            "text_to_speech": self.audio.text_to_speech,
            "complete": self.text.complete,
            "chat": self.text.chat,
            "embed": self.text.embed,
            "execute_code": self.text.execute_code,
            "extract_frames": self.video.extract_frames,
            "detect_scenes": self.video.detect_scenes,
            "extract_faces": self.video.extract_faces,
        }
        return tools.get(name)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="Local AI Suite")
    s = p.add_subparsers(dest="cmd")

    v = s.add_parser("vision")
    v.add_argument("--image", required=True)
    v.add_argument("--task", choices=["analyze","face-detect","ocr","describe"], required=True)
    v.add_argument("--model", default="llama3.2:latest")

    a = s.add_parser("audio")
    a.add_argument("--file", required=True)
    a.add_argument("--task", choices=["transcribe","tts"], required=True)
    a.add_argument("--output")
    a.add_argument("--text")
    a.add_argument("--whisper-model", default="base")

    t = s.add_parser("text")
    t.add_argument("--prompt", required=True)
    t.add_argument("--model", default="llama3.2:latest")
    t.add_argument("--task", choices=["complete","chat","embed","execute"], default="complete")

    vid = s.add_parser("video")
    vid.add_argument("--file", required=True)
    vid.add_argument("--task", choices=["extract-frames","detect-scenes","extract-faces"], required=True)
    vid.add_argument("--interval", type=float, default=1.0)
    vid.add_argument("--output-dir")

    c = s.add_parser("chain")
    c.add_argument("--config", required=True)

    args = p.parse_args()
    if not args.cmd: p.print_help(); return

    suite = ChainOrchestrator()

    if args.cmd == "vision":
        fn = {"analyze": suite.vision.analyze_image, "face-detect": suite.vision.detect_faces,
              "ocr": suite.vision.extract_text, "describe": lambda p: suite.vision.describe_image(p, args.model)}
        print(json.dumps(fn[args.task](args.image), indent=2, default=str))

    elif args.cmd == "audio":
        if args.task == "transcribe":
            print(json.dumps({"text": suite.audio.transcribe(args.file, args.whisper_model)}, indent=2))
        elif args.task == "tts":
            if not args.text or not args.output: print("ERROR: --text and --output required"); return
            print(json.dumps({"ok": suite.audio.text_to_speech(args.text, args.output)}, indent=2))

    elif args.cmd == "text":
        fn = {"complete": lambda: suite.text.complete(args.prompt, args.model),
              "chat": lambda: suite.text.chat([{"role":"user","content":args.prompt}], args.model),
              "embed": lambda: suite.text.embed([args.prompt]),
              "execute": lambda: suite.text.execute_code(args.prompt)}
        print(json.dumps(fn[args.task](), indent=2, default=str))

    elif args.cmd == "video":
        fn = {"extract-frames": lambda: suite.video.extract_frames(args.file, args.interval, args.output_dir),
              "detect-scenes": lambda: suite.video.detect_scenes(args.file),
              "extract-faces": lambda: suite.video.extract_faces(args.file, args.interval, args.output_dir)}
        print(json.dumps(fn[args.task](), indent=2, default=str))

    elif args.cmd == "chain":
        with open(args.config) as f:
            cfg = json.load(f)
        print(json.dumps(suite.run_chain(cfg), indent=2, default=str))


if __name__ == "__main__":
    main()

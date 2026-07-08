import base64
import requests
import config

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

_camera_index   = 0
_camera_backend = None
_vision_model   = None
_available      = False


def init(camera_idx: int, backend, vision_model: str | None):
    global _camera_index, _camera_backend, _vision_model, _available
    _camera_index   = camera_idx
    _camera_backend = backend
    _vision_model   = vision_model
    _available      = _check_camera() and vision_model is not None
    state = "✓ ready" if _available else "(not available)"
    print(f"   Camera  {state}")


def _check_camera() -> bool:
    if not _CV2:
        return False
    cap = None
    try:
        cap = cv2.VideoCapture(_camera_index, _camera_backend)
        return cap.isOpened()
    except Exception:
        return False
    finally:
        if cap is not None:
            cap.release()


def is_available() -> bool:
    return _available


def capture_frame() -> str | None:
    if not _CV2 or not _available:
        return None
    cap = None
    try:
        cap = cv2.VideoCapture(_camera_index, _camera_backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        ret = False
        frame = None
        for _ in range(3):
            ret, frame = cap.read()
            
        if not ret or frame is None:
            return None
            
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buf).decode()
    except Exception as e:
        print(f"   [Vision] Capture error: {e}")
        return None
    finally:
        if cap is not None:
            cap.release()  # This now running guarantees the hardware unlocks!


def describe(image_b64: str,
             prompt: str = "Describe what you see in detail.") -> str:
    if not _vision_model:
        return "(vision model not available on this hardware tier)"
    try:
        resp = requests.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={
                "model": _vision_model,
                "messages": [{"role": "user",
                               "content": prompt,
                               "images": [image_b64]}],
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"(Vision error: {e})"


def wants_vision(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in config.VISION_KEYWORDS)
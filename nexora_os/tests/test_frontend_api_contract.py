from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"
PAGES_DIR = FRONTEND_SRC / "app" / "components" / "pages"
CLIENT = FRONTEND_SRC / "api" / "client.ts"
VISION_PAGE = PAGES_DIR / "VisionPage.tsx"


def test_frontend_pages_do_not_hardcode_dev_api_origin():
    offenders: list[str] = []
    for path in PAGES_DIR.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        if "http://127.0.0.1:7474" in text or "http://localhost:7474" in text:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_api_client_owns_the_dev_backend_default():
    text = CLIENT.read_text(encoding="utf-8")

    assert "http://127.0.0.1:7474" in text
    assert "VITE_NEXORA_API" in text
    assert "window.location.origin" in text


def test_vision_page_uses_central_api_client_for_vision_actions():
    text = VISION_PAGE.read_text(encoding="utf-8")

    assert 'from "../../../api/client"' in text
    assert "nexoraApi.visionStart()" in text
    assert "nexoraApi.visionStop()" in text
    assert "nexoraApi.visionFrame()" in text
    assert "nexoraApi.visionFrameWithMouse()" in text
    assert "nexoraApi.visionScreen(true)" in text
    assert "nexoraApi.visionScreen(false)" in text
    assert "fetch(" not in text

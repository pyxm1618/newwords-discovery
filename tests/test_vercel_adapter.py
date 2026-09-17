import importlib.util
from http.server import BaseHTTPRequestHandler
from pathlib import Path


def test_vercel_adapter_exports_handler_with_post_and_non_post_methods():
    path = Path(__file__).parents[1] / "api" / "v1" / "keyword-volume.py"
    spec = importlib.util.spec_from_file_location("keyword_volume_vercel", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert issubclass(module.handler, BaseHTTPRequestHandler)
    assert "do_POST" in module.handler.__dict__
    assert "do_GET" in module.handler.__dict__

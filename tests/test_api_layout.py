from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_all_runtime_api_code_lives_under_api_tree():
    assert not (ROOT / "src").exists()
    assert (ROOT / "api" / "v1" / "keyword-volume.py").is_file()
    assert (ROOT / "api" / "v1" / "trends.py").is_file()\n    assert (ROOT / "api" / "v1" / "trending-now.py").is_file()
    assert (ROOT / "api" / "lib").is_dir()


def test_private_api_modules_follow_vercel_helper_naming():
    helper_dir = ROOT / "api" / "lib"
    expected = {
        "_auth.py",
        "_config.py",
        "_http.py",
        "_endpoint.py",
        "_trends_endpoint.py",\n        "_trending_now_endpoint.py",\n        "_trending_now.py",
        "_google_ads.py",
        "_google_bigquery.py",
        "_keyword_volume.py",
        "_trends.py",
    }
    assert expected.issubset({path.name for path in helper_dir.glob("*.py")})
    assert all(path.name.startswith("_") for path in helper_dir.glob("*.py"))


def test_endpoint_orchestration_is_not_mixed_between_apis():
    keyword_endpoint = (ROOT / "api" / "lib" / "_endpoint.py").read_text()
    trends_endpoint = (ROOT / "api" / "lib" / "_trends_endpoint.py").read_text()

    assert "handle_keyword_volume" in keyword_endpoint
    assert "handle_trends" not in keyword_endpoint
    assert "_google_bigquery" not in keyword_endpoint
    assert "_trends" not in keyword_endpoint

    assert "handle_trends" in trends_endpoint
    assert "handle_keyword_volume" not in trends_endpoint
    assert "_google_ads" not in trends_endpoint
    assert "_keyword_volume" not in trends_endpoint

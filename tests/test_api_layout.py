from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_all_runtime_api_code_lives_under_api_tree():
    assert not (ROOT / "src").exists()
    assert (ROOT / "api" / "v1" / "keyword-volume.py").is_file()
    assert (ROOT / "api" / "v1" / "trends.py").is_file()
    assert (ROOT / "api" / "lib").is_dir()


def test_shared_api_helpers_are_private_vercel_utility_modules():
    helper_dir = ROOT / "api" / "lib"
    expected = {
        "_auth.py",
        "_config.py",
        "_endpoint.py",
        "_google_ads.py",
        "_google_bigquery.py",
        "_keyword_volume.py",
        "_trends.py",
    }
    assert expected.issubset({path.name for path in helper_dir.glob("*.py")})
    assert all(
        path.name.startswith("_")
        for path in helper_dir.glob("*.py")
    )

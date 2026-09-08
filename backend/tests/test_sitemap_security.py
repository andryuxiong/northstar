from app.workers.tasks import extract_sitemap_urls


def test_sitemap_parser_does_not_resolve_external_entities(tmp_path):
    secret_path = tmp_path / "secret.txt"
    secret_path.write_text("LOCAL_SECRET_MUST_NOT_BE_READ", encoding="utf-8")
    xml = f'''<?xml version="1.0"?>
<!DOCTYPE urlset [<!ENTITY xxe SYSTEM "{secret_path.as_uri()}">]>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>&xxe;</loc></url>
  <url><loc>https://public.example/products/widget</loc></url>
</urlset>'''

    urls = extract_sitemap_urls(xml)

    assert "LOCAL_SECRET_MUST_NOT_BE_READ" not in "".join(urls)
    assert urls == ["https://public.example/products/widget"]

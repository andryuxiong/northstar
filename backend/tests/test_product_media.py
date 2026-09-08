from types import SimpleNamespace

from app.services.product_media import product_image_url


def test_product_image_url_prefers_normalized_snapshot(tmp_path):
    snapshot = SimpleNamespace(
        images_json=["https://cdn.example.com/normalized.jpg"],
        content_hash="unused",
    )

    assert product_image_url(
        "https://shop.example/products/widget",
        snapshot,
        snapshot_dir=str(tmp_path),
    ) == "https://cdn.example.com/normalized.jpg"


def test_product_image_url_recovers_from_saved_shopify_html(tmp_path):
    content_hash = "saved-product"
    html_dir = tmp_path / "html" / "shop.example"
    html_dir.mkdir(parents=True)
    (html_dir / f"{content_hash}.html").write_text(
        """
        <html><head>
          <meta property="og:image" content="https://cdn.example.com/recovered.jpg">
          <script>var meta = {"product":{"id":7,"title":"Widget","variants":[]}};</script>
        </head></html>
        """,
        encoding="utf-8",
    )
    snapshot = SimpleNamespace(images_json=[], content_hash=content_hash)

    assert product_image_url(
        "https://shop.example/products/widget",
        snapshot,
        snapshot_dir=str(tmp_path),
    ) == "https://cdn.example.com/recovered.jpg"

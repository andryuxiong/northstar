from app.services.parsers.shopify import ShopifyParser
from app.services.parsers.generic import GenericProductParser


def test_shopify_parser_json_ld():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"Product","name":"Test Product","description":"Desc","image":"https://cdn.shopify.com/test.jpg","offers":{"price":"19.99","priceCurrency":"USD"}}
    </script>
    </head><body></body></html>
    """
    parser = ShopifyParser(html)
    data = parser.parse()
    assert data["title"] == "Test Product"
    assert data["currency"] == "USD"
    assert data["variants"][0]["price"] == 19.99
    assert data["images"] == ["https://cdn.shopify.com/test.jpg"]


def test_shopify_parser_merges_meta_product_variants_with_json_ld_images():
    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.shopify.com/fallback.jpg" />
      <script>
        var meta = {"product":{"id":123,"title":"Merged product","vendor":"Acme","variants":[{"id":1,"price":2499,"available":true}]}};
      </script>
      <script type="application/ld+json">
        {"@type":"Product","name":"Merged product","image":[{"url":"https://cdn.shopify.com/primary.jpg"}],"offers":{"price":"24.99","priceCurrency":"USD"}}
      </script>
    </head><body></body></html>
    """

    data = ShopifyParser(html).parse()

    assert data["external_id"] == "123"
    assert data["variants"][0]["price"] == 24.99
    assert data["currency"] == "USD"
    assert data["images"] == ["https://cdn.shopify.com/primary.jpg"]


def test_shopify_parser_uses_open_graph_image_when_structured_sources_omit_it():
    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.shopify.com/fallback.jpg" />
      <script>var meta = {"product":{"id":456,"title":"Fallback image","variants":[]}};</script>
    </head><body></body></html>
    """

    assert ShopifyParser(html).parse()["images"] == ["https://cdn.shopify.com/fallback.jpg"]


def test_generic_parser_meta():
    html = """
    <html><head>
    <meta property="og:title" content="Widget" />
    <meta property="og:image" content="https://example.com/a.jpg" />
    <meta property="product:price:amount" content="12.50" />
    <meta property="product:price:currency" content="USD" />
    </head><body></body></html>
    """
    parser = GenericProductParser(html)
    data = parser.parse()
    assert data["title"] == "Widget"
    assert data["variants"][0]["price"] == 12.50

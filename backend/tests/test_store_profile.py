from app.services.store_profile import analyze_store_homepage


def test_homepage_analysis_extracts_public_identity_offer_funnel_and_technology():
    html = """
    <html lang="en-CA">
      <head>
        <title>Acme Glow — Skin care made simple</title>
        <meta property="og:site_name" content="Acme Glow">
        <meta name="description" content="Clean skincare and beauty essentials.">
        <script type="application/ld+json">
          {
            "@type": "Organization",
            "name": "Acme Glow",
            "logo": "https://cdn.example.com/acme-logo.png",
            "sameAs": [
              "https://www.facebook.com/acmeglow",
              "https://www.instagram.com/acmeglow"
            ],
            "address": {"addressCountry": "CA"}
          }
        </script>
        <script src="https://cdn.shopify.com/shop.js"></script>
        <script src="https://cdn.judge.me/widget.js"></script>
        <script src="https://static.klaviyo.com/app.js"></script>
        <script src="https://areviewsapp.com/js_codes/areviews_app.js"></script>
        <script src="https://cdn.shopify.com/extensions/abc/orbe-geolocation-473/assets/app.js"></script>
        <script src="https://cdn.shopify.com/extensions/def/freegifts-206/assets/app.js"></script>
        <script src="https://widgets.vendor-example.io/storefront.js"></script>
        <script src="https://cdnjs.cloudflare.com/library.js"></script>
        <script>
          Shopify.theme = {"name":"Acme custom theme","id":12345,"schema_name":"Impact","schema_version":"7.2.0","theme_store_id":1190,"role":"main"};
          Shopify.analytics = {webPixelsConfigList: [{configuration:
            "{\"google_tag_ids\":[\"GT-ABC12345\"],\"gtag_events\":[{\"type\":\"view_item\"}]}"
          }]};
        </script>
        <script type="application/json">
          {"blocks":[
            "shopify://apps/judge-me-reviews/blocks/core/abc",
            "shopify://apps/kaching-bundles/blocks/embed/def",
            "shopify://apps/pagefly-page-builder/blocks/embed/ghi"
          ]}
        </script>
      </head>
      <body>
        <div class="sticky-add-to-cart">Add to cart</div>
        <div class="jdgm-widget">Reviews</div>
        <section>Frequently asked questions</section>
        <aside>Get 20% off today. Free shipping on orders over $50.</aside>
      </body>
    </html>
    """
    result = analyze_store_homepage("https://acmeglow.example/", html)

    assert result.brand_name == "Acme Glow"
    assert result.brand_confidence >= 0.9
    assert result.primary_country == "CA"
    assert result.primary_category == "beauty_and_personal_care"
    assert result.platform == "shopify"
    assert result.logo_url == "https://cdn.example.com/acme-logo.png"
    assert result.theme is not None
    assert result.theme["name"] == "Acme custom theme"
    assert result.theme["theme_id"] == 12345
    assert result.theme["schema_name"] == "Impact"
    assert result.theme["schema_version"] == "7.2.0"
    assert result.theme["theme_store_id"] == 1190
    assert result.theme["role"] == "main"
    assert result.theme["confidence"] == 0.98
    assert {identity.identity_type for identity in result.identities} >= {
        "brand",
        "facebook",
        "instagram",
    }
    assert {technology.key for technology in result.technologies} >= {
        "shopify",
        "judgeme",
        "klaviyo",
        "google_analytics",
        "monimo_reviews",
        "orbe_geolocation",
        "bogos",
        "kaching_bundles",
        "pagefly",
    }
    unknown_integrations = [
        technology
        for technology in result.technologies
        if technology.category == "unclassified_integration"
    ]
    assert any("vendor-example.io" in technology.label for technology in unknown_integrations)
    assert not any("cloudflare" in technology.label.lower() for technology in result.technologies)
    assert {element.key for element in result.funnel_elements} >= {
        "sticky_add_to_cart",
        "reviews",
        "faq",
        "free_shipping",
    }
    offers = {offer.offer_type: offer for offer in result.offers}
    assert offers["percentage_discount"].discount_percent == 20
    assert offers["free_shipping"].minimum_spend == 50


def test_homepage_analysis_uses_low_confidence_domain_fallback_without_claiming_more():
    result = analyze_store_homepage(
        "https://plain-widget-store.example/",
        "<html><head><title>Home</title></head><body>Welcome</body></html>",
    )

    assert result.brand_name == "Plain Widget Store"
    assert result.brand_confidence == 0.4
    assert result.primary_category is None
    assert result.primary_country is None
    assert result.offers == []
    assert result.technologies == []

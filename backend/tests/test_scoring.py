from app.db.session import SessionLocal
from app.db.base import Base
from app.db import models
from app.services.signals import compute_product_signals
from app.services.scoring import compute_product_scores
from datetime import datetime, timedelta
from uuid import uuid4


def setup_module(module):
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    db.close()


def test_scoring_pipeline():
    db = SessionLocal()
    try:
        run_id = uuid4().hex
        user = models.User(email=f"score-{run_id}@example.com", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        ws = models.Workspace(name="Default", owner_user_id=user.id)
        db.add(ws)
        db.commit()
        db.refresh(ws)
        store = models.Store(workspace_id=ws.id, domain=f"{run_id}.example.com", platform_guess=models.PlatformGuess.unknown)
        db.add(store)
        db.commit()
        db.refresh(store)
        product = models.Product(workspace_id=ws.id, store_id=store.id, canonical_url=f"https://{run_id}.example.com/p", title="Test", description="", currency="USD")
        db.add(product)
        db.commit()
        db.refresh(product)

        snap1 = models.ProductSnapshot(product_id=product.id, fetched_at=datetime.utcnow() - timedelta(days=2), title="Test", price_min=10, price_max=10, available=True, variant_count=1, images_json=[], raw_extracted_json={"variants":[{"price":10}]}, content_hash="a")
        snap2 = models.ProductSnapshot(product_id=product.id, fetched_at=datetime.utcnow(), title="Test", price_min=12, price_max=12, available=False, variant_count=2, images_json=[], raw_extracted_json={"variants":[{"price":12,"compare_at_price":20}]}, content_hash="b")
        db.add_all([snap1, snap2])
        db.commit()

        compute_product_signals(db, product.id)
        scores = compute_product_scores(db, product.id)
        assert len(scores) >= 2
        assert any(s.score_type == models.ScoreType.momentum for s in scores)
    finally:
        db.close()


def test_momentum_is_withheld_until_product_has_history():
    db = SessionLocal()
    try:
        run_id = uuid4().hex
        user = models.User(email=f"single-{run_id}@example.com", password_hash="x")
        db.add(user)
        db.flush()
        workspace = models.Workspace(name="Single snapshot", owner_user_id=user.id)
        db.add(workspace)
        db.flush()
        store = models.Store(
            workspace_id=workspace.id,
            domain=f"{run_id}.example.com",
            platform_guess=models.PlatformGuess.unknown,
        )
        db.add(store)
        db.flush()
        product = models.Product(
            workspace_id=workspace.id,
            store_id=store.id,
            canonical_url=f"https://{run_id}.example.com/p",
            title="One observation",
            currency="USD",
        )
        db.add(product)
        db.flush()
        db.add(
            models.ProductSnapshot(
                product_id=product.id,
                title=product.title,
                price_min=10,
                price_max=10,
                available=True,
                variant_count=1,
                images_json=[],
                raw_extracted_json={"variants": [{"price": 10}]},
                content_hash=run_id,
            )
        )
        db.commit()

        compute_product_signals(db, product.id)
        scores = compute_product_scores(db, product.id)
        assert all(score.score_type != models.ScoreType.momentum for score in scores)
        assert any(score.score_type == models.ScoreType.winner for score in scores)
    finally:
        db.close()

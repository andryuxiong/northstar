from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.schemas import Token, UserOut
from app.db.session import get_db
from app.db import models
from app.utils.security import create_access_token, hash_password, verify_password, get_current_user

router = APIRouter()


@router.post("/register", response_model=UserOut)
def register(email: str, password: str, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    workspace = models.Workspace(name="Default", owner_user_id=user.id)
    db.add(workspace)
    db.commit()

    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not user.password_hash or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    return Token(access_token=token)


@router.post("/local", response_model=Token)
def local_login(request: Request, db: Session = Depends(get_db)):
    """Password-free login for the loopback-only personal launcher."""
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="Local login is only available on this computer")
    user = db.query(models.User).filter(models.User.email == "local@northstar").first()
    if not user:
        user = models.User(email="local@northstar", password_hash=None)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(models.Workspace(name="Personal", owner_user_id=user.id))
        db.commit()
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user

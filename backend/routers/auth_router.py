"""认证路由（演示级登录，需求 6.2 说明）。"""
from fastapi import APIRouter, Depends

import auth
import schemas

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", summary="登录换取令牌")
def login(body: schemas.LoginIn):
    return auth.login(body.username, body.password)


@router.get("/me", summary="当前登录用户")
def me(user=Depends(auth.current_user)):
    return user
import logging
import uuid
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from tortoise.query_utils import Q

from market.core import config
from market.core.security import (
    APIKEY_HEADER_NAME,
    authenticate_admin_user,
    info_admin_user,
    create_access_token,
    get_password_hash,
    require_active_admin,
    require_super_scope_su,
    require_super_scope_su1,
    verify_password
)
from market.models.admin_user import MarketAdminUser
from market.models.const import UserScope2, UserStatus
from market.schemas.admin_user import (
    AdminUserInfo,
    AdminUserChangeStatusIn,
    AdminUserCreate,
    AdminUserIn,
    AdminUserSearchIn,
    AdminUserSearchOut,
    AdminUserUpdate,
)
from market.schemas.admin_user import UpdatePassword
from market.schemas.base import CommonOut
from market.schemas.token import AdminToken

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/user/login", response_model=AdminToken, tags=["后台——系统管理员"])
async def admin_login(schema_in: AdminUserIn, response: Response):
    """登录管理后台"""
    if schema_in.verification_code != "1234":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect verification_code",
        )
    user,user1 = await info_admin_user(schema_in.user_id, schema_in.password)
    #user = await authenticate_admin_user(schema_in.user_id, schema_in.password)
    if user:
        if user.status == UserStatus.disabled:
            raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="该用户被禁用，请联系超管解禁！！",
                    )
        #if user == 1:
        #    raise HTTPException(
        #            status_code=status.HTTP_403_FORBIDDEN,
        #            detail="密码错误",
        #            )
    if not user:
        if user1 == 1:
            raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail='密码错误')
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户名不存在，请联系超管添加用户",
             )
    access_token_expires = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"uuid": user.uuid.hex}, expires_delta=access_token_expires
    )
    # response.headers[APIKEY_HEADER_NAME] = access_token
    response.set_cookie(key=APIKEY_HEADER_NAME, value=access_token)
    return AdminToken(**user.__dict__, token=access_token)


@router.post("/user/logout", response_model=CommonOut, tags=["后台——系统管理员"])
#async def admin_logout(current_user: MarketAdminUser = Depends(require_active_admin)):
async def admin_logout():
    """注销管理后台"""
    return CommonOut()


@router.post("/user/add", response_model=CommonOut, tags=["后台——系统管理员"])
async def add_admin(
    schema_in: AdminUserCreate,
    current_user: MarketAdminUser = Depends(require_super_scope_su),
):
    """添加管理员，需要总后台超管权限"""
    if current_user.scope1 != "aq" or current_user.scope2 != UserScope2.su:
        return CommonOut(errCode=-100, errMsg="添加失败，没有权限")


    marketadminuser = await  MarketAdminUser.all()
    name_list = []
    phone_list = []
    email_list = []
    for i in marketadminuser:
        name_list.append(i.name)
        phone_list.append(i.phone)
        email_list.append(i.email)
    if name_list:
        if schema_in.name in name_list:
            return CommonOut(errCode=-1, errMsg="添加失败，请检查名字是否重复")
    if phone_list:
        if schema_in.phone in phone_list:
            return CommonOut(errCode=-1, errMsg="添加失败，请检查手机号是否重复")
    if email_list:
        if schema_in.email in email_list:
            return CommonOut(errCode=-1, errMsg="添加失败，请检查邮箱是否重复")


    data = schema_in.dict()
    data["uuid"] = uuid.uuid1()
    data["password"] = get_password_hash(data["password"], data["uuid"].hex)
    try:
        await MarketAdminUser.create(**data)
        await MarketAdminUser.filter(name=schema_in.name).update(scope2=UserScope2.simble)
    except Exception:
        logger.exception("create package failed: %s", schema_in.json())
        return CommonOut(errCode=-1, errMsg="添加失败，请检查名字是否重复")

    return CommonOut()


@router.post("/user/change_status", response_model=CommonOut, tags=["后台——系统管理员"])
async def change_admin_status(
    schema_in: AdminUserChangeStatusIn,
    current_user: MarketAdminUser = Depends(require_super_scope_su),
):
    """禁用管理员"""
    if current_user.scope1 != "aq" or current_user.scope2 != UserScope2.su:
        return CommonOut(errCode=-100, errMsg="添加失败，没有权限")
    if schema_in.status == UserStatus.deleted:
        await MarketAdminUser.filter(id=schema_in.id).delete()
    else:
        try:
            await MarketAdminUser.filter(id=schema_in.id).update(status=schema_in.status)
        except Exception:
            logger.exception("更新管理员信息失败：%s", schema_in.json())
            return CommonOut(errCode=-1, errMsg="更新失败，请检查名字是否重复")
    return CommonOut()


@router.post("/user/edit", response_model=CommonOut, tags=["后台——系统管理员"])
async def edit_admin(
    schema_in: AdminUserUpdate,
    current_user: MarketAdminUser = Depends(require_active_admin),
):
    """编辑管理员信息"""
    try:
        await MarketAdminUser.filter(id=schema_in.id).update(**schema_in.changed.dict())
    except Exception:
        logger.exception("更新管理员信息失败：%s", schema_in.json())
        return CommonOut(errCode=-1, errMsg="更新失败，请检查名字是否重复")
    return CommonOut()


@router.post("/user/update-password", response_model=CommonOut, tags=["后台——系统管理员"])
async def update_password(
            update_in: UpdatePassword, current_user: MarketAdminUser = Depends(require_active_admin)
            ):
    if not verify_password(
            update_in.old_pwd, current_user.password, current_user.uuid.hex
            ):
        raise HTTPException(status_code=400, detail="密码错误")
    user = await MarketAdminUser.get(id=current_user.id)
    user.password = get_password_hash(update_in.new_pwd, current_user.uuid.hex)
    await user.save()
    return CommonOut()


@router.post("/user/find", response_model=AdminUserSearchOut, tags=["后台——系统管理员"])
async def search_admin(
    schema_in: AdminUserSearchIn,
    current_user: MarketAdminUser = Depends(require_super_scope_su1),
):
    """根据名字和类型查询标签或者风格"""
    if current_user.scope2 == UserScope2.su:
        query = MarketAdminUser.filter(~Q(status=UserStatus.deleted))
        if schema_in.scope1:
            query = query.filter(scope1=schema_in.scope1)
        if schema_in.scope2:
            query = query.filter(scope2=schema_in.scope2)
        if schema_in.name:
            query = query.filter(name__contains=schema_in.name)
        if schema_in.phone:
            query = query.filter(phone__contains=schema_in.phone)
        if schema_in.email:
            query = query.filter(phone__contains=schema_in.email)
        total_count = await query.count()
        users = await query.order_by("name").offset(schema_in.offset).limit(schema_in.count)
        return AdminUserSearchOut(
                total=total_count, data=[AdminUserInfo(**user.__dict__) for user in users if user.scope2 != UserScope2.su]
                )
    else:
        return AdminUserSearchOut(
                        total=0, data=[]
                            )

"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class GetSysUserListRequestDto(SerializableModel):
    page_index: int | None = None
    page_size: int | None = None
    order_field: str | None = None
    order_type: str | None = None
    parent_agent_id: int | None = None
    username: str | None = None
    role_name: str | None = None
    is_total_amount: int | None = None
    is_agent: int | None = None
    is_main: int | None = None
    is_trust_user: int | None = None
    system_id: int | None = None
    is_ceshi: int | None = None
    agent_domain_name: str | None = None
    is_frozen: int | None = None
    is_stuff_white: int | None = None
    new_userid: str | None = None

@dataclass
class GetUserListForSelectRequestDto(SerializableModel):
    pass

@dataclass
class RegisterRequestDto(SerializableModel):
    user_name: str | None = None
    user_password: str | None = None
    host: str | None = None

@dataclass
class UpdatePwdRequestDto(SerializableModel):
    old_password: str | None = None
    new_password: str | None = None

@dataclass
class UserEnableOrUnEnableRequestDto(SerializableModel):
    id: int | None = None
    state: UserStatusEnum | None = None

@dataclass
class sys_user(SerializableModel):
    userid: int | None = None
    username: str | None = None
    password: str | None = None
    role_id: int | None = None
    is_ceshi: int | None = None
    user_status: UserStatusEnum | None = None
    createby: str | None = None
    edit_pwd: int | None = None
    user_key: str | None = None
    createtime: str | None = None
    last_login_time: str | None = None

__all__ = ['GetSysUserListRequestDto', 'GetUserListForSelectRequestDto', 'RegisterRequestDto', 'UpdatePwdRequestDto', 'UserEnableOrUnEnableRequestDto', 'sys_user']

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Emoji = Literal['happy','neutral','sad','surprised','angry','fearful','disgusted']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


def strong_password(v):
    if len(v) < 10 or len(v.encode('utf-8')) > 72 or not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError('密码至少10位，须含字母和数字，UTF-8编码不超过72字节')
    return v


def utc_datetime(v):
    if v.tzinfo is None:
        raise ValueError('时间必须包含时区，例如 +08:00 或 Z')
    return v.astimezone(timezone.utc).replace(tzinfo=None)


class Credentials(Input):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=72)
    @field_validator('password')
    @classmethod
    def bounded(cls, v):
        if len(v.encode('utf-8')) > 72:
            raise ValueError('密码编码长度超过72字节')
        return v


class Register(Credentials):
    username: str = Field(min_length=2,max_length=40,pattern=r'^[\w.-]+$')
    role: Literal['student','teacher','admin'] = 'student'
    email: str = Field(default='', max_length=120)
    invite_code: str = Field(default='',max_length=128)
    _strong = field_validator('password')(strong_password)


class Password(Input):
    old_password: str = Field(min_length=1,max_length=72)
    new_password: str = Field(min_length=10,max_length=64)
    _strong = field_validator('new_password')(strong_password)
    @field_validator('old_password')
    @classmethod
    def old_bounded(cls,v):
        if len(v.encode())>72: raise ValueError('密码编码长度超过72字节')
        return v


class NewCourse(Input):
    name: str = Field(min_length=1,max_length=100)
    teacher_id: int = Field(gt=0)


class NewSession(Input):
    course_id: int = Field(gt=0)
    start_at: datetime
    end_at: datetime
    class_name: str = Field(min_length=1,max_length=80)
    room: str = Field(min_length=1,max_length=80)
    _utc = field_validator('start_at','end_at')(utc_datetime)
    @model_validator(mode='after')
    def dates(self):
        if self.end_at <= self.start_at: raise ValueError('结束时间必须晚于开始时间')
        return self


class UpdateSession(NewSession):
    version: int = Field(ge=1)


class Schedule(Input):
    user_ids: list[int] = Field(max_length=500)
    version: int = Field(ge=1)
    @field_validator('user_ids')
    @classmethod
    def unique_ids(cls,v):
        if len(set(v))!=len(v) or any(x<=0 for x in v):
            raise ValueError('名单中存在重复或无效用户编号')
        return v


class ManualEmoji(Input):
    session_id: int = Field(gt=0)
    emoji: Emoji


class AIResult(Input):
    session_id: int = Field(gt=0)
    emoji: Emoji
    confidence: float = Field(ge=0,le=1,allow_inf_nan=False)
    timestamp: datetime
    device_id: str = Field(min_length=1,max_length=80)
    event_id: str = Field(min_length=1,max_length=100)
    model_version: str = Field(min_length=1,max_length=100)
    user_id: int | None = Field(default=None,gt=0)
    _utc = field_validator('timestamp')(utc_datetime)


class UserStatus(Input):
    active: bool

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Display name is required")
        return value.strip()


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return RegisterInput.clean_name(value)


class PasswordChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class PasswordForgotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class PasswordResetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(min_length=20, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str


class CsrfRead(BaseModel):
    csrf_token: str

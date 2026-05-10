import re

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


_FEATURE_KEY_PATTERN = re.compile(r"^[a-z0-9-]+$")
_PERMISSION_PATTERN = re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+$")
_FLAG_PATTERN = re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+$")


def _dedupe_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        result.append(normalized)

    return result


class NavSchema(BaseModel):
    label: str
    icon: str | None = None
    group: str | None = None
    order: int = 0


class FrontendSchema(BaseModel):
    type: str = "module"
    # Accept either an absolute URL (http(s)://...) or a same-origin path
    # (e.g. "/_mfe/asset-inventory/...") so shells can proxy MFEs same-origin.
    entryUrl: str
    integrity: str | None = None
    basePath: str = "/"

    @field_validator("entryUrl")
    @classmethod
    def entry_url_format(cls, value: str) -> str:
        if value.startswith(("http://", "https://", "/")):
            return value
        raise ValueError(
            "frontend.entryUrl must be an absolute URL or start with '/'"
        )


class BackendSchema(BaseModel):
    # Accept absolute URL or same-origin path (shell proxies APIs same-origin).
    apiBaseUrl: str

    @field_validator("apiBaseUrl")
    @classmethod
    def api_base_url_format(cls, value: str) -> str:
        if value.startswith(("http://", "https://", "/")):
            return value
        raise ValueError(
            "backend.apiBaseUrl must be an absolute URL or start with '/'"
        )


class AuthorizationSchema(BaseModel):
    requiredPermissions: list[str] = Field(default_factory=list)
    requiredFlags: list[str] = Field(default_factory=list)

    @field_validator("requiredPermissions")
    @classmethod
    def required_permissions_must_be_valid(cls, values: list[str]) -> list[str]:
        normalized = _dedupe_non_empty(values)

        for value in normalized:
            if not _PERMISSION_PATTERN.match(value):
                raise ValueError(
                    "authorization.requiredPermissions values must use '<feature>.<action>' format"
                )

        return normalized

    @field_validator("requiredFlags")
    @classmethod
    def required_flags_must_be_valid(cls, values: list[str]) -> list[str]:
        normalized = _dedupe_non_empty(values)

        for value in normalized:
            if not _FLAG_PATTERN.match(value):
                raise ValueError(
                    "authorization.requiredFlags values must use '<feature>.<flag>' format"
                )

        return normalized


class CompatibilitySchema(BaseModel):
    shellContractMin: str | None = None
    shellContractMax: str | None = None


class MetadataSchema(BaseModel):
    ownerTeam: str
    commitSha: str | None = None
    buildId: str | None = None
    releaseDate: str | None = None


class ReleaseManifestIn(BaseModel):
    manifestVersion: str = "1.0"
    featureKey: str
    displayName: str
    version: str
    environment: str
    route: str
    frontend: FrontendSchema
    backend: BackendSchema
    nav: NavSchema
    authorization: AuthorizationSchema
    compatibility: CompatibilitySchema = Field(default_factory=CompatibilitySchema)
    metadata: MetadataSchema

    @field_validator("featureKey")
    @classmethod
    def feature_key_must_be_valid(cls, value: str) -> str:
        normalized = value.strip()

        if not _FEATURE_KEY_PATTERN.match(normalized):
            raise ValueError("featureKey must contain only lowercase letters, numbers, and hyphens")

        return normalized

    @field_validator("environment")
    @classmethod
    def environment_must_be_valid(cls, value: str) -> str:
        normalized = value.strip().lower()

        if normalized not in {"local", "dev", "test", "uat", "staging", "prod", "production"}:
            raise ValueError(
                "environment must be one of local, dev, test, uat, staging, prod, production"
            )

        return normalized

    @field_validator("route")
    @classmethod
    def route_must_start_with_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("route must start with '/'")
        return value

    @model_validator(mode="after")
    def authorization_must_be_explicit(self) -> "ReleaseManifestIn":
        if not self.authorization.requiredPermissions:
            raise ValueError("authorization.requiredPermissions must not be empty")

        if not self.authorization.requiredFlags:
            raise ValueError("authorization.requiredFlags must not be empty")

        return self
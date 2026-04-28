from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Feature, Release, ReleaseStatus
from app.schemas.manifest import (
    AuthorizationSchema,
    BackendSchema,
    CompatibilitySchema,
    FrontendSchema,
    MetadataSchema,
    NavSchema,
    ReleaseManifestIn,
)


class RuntimeService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_manifests(self, environment: str) -> list[ReleaseManifestIn]:
        rows = self.db.execute(
            select(Feature, Release)
            .join(Release, Release.feature_id == Feature.id)
            .where(
                Release.environment == environment,
                Release.status == ReleaseStatus.active,
                Release.is_deleted.is_(False),
            )
            .order_by(Feature.feature_key.asc())
        ).all()

        manifests: list[ReleaseManifestIn] = []
        for feature, release in rows:
            metadata = release.metadata_json or {}
            backend_metadata = metadata.get("backend", {})
            frontend_metadata = metadata.get("frontend", {})

            manifests.append(
                ReleaseManifestIn(
                    manifestVersion=release.manifest_version,
                    featureKey=feature.feature_key,
                    displayName=feature.display_name,
                    version=release.version,
                    environment=release.environment,
                    route=release.route,
                    frontend=FrontendSchema(
                        type=frontend_metadata.get("type", "module"),
                        enabled=frontend_metadata.get("enabled", True),
                        entryUrl=release.entry_url,
                        mountFunction=frontend_metadata.get("mountFunction", "mount"),
                        integrity=metadata.get("integrity"),
                        basePath=frontend_metadata.get("basePath", release.route),
                    ),
                    backend=BackendSchema(
                        enabled=backend_metadata.get("enabled", True),
                        apiBaseUrl=release.api_base_url,
                        healthEndpoint=backend_metadata.get("healthEndpoint", "/health"),
                    ),
                    nav=NavSchema(**(release.nav_json or {})),
                    authorization=AuthorizationSchema(**(release.authorization_json or {})),
                    compatibility=CompatibilitySchema(**(release.compatibility_json or {})),
                    metadata=MetadataSchema(**(metadata or {})),
                )
            )
        return manifests
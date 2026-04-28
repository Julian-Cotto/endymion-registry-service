from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Feature, Release, ReleaseStatus
from app.db.session import SessionLocal


LOCAL_MANIFESTS = [
    {
        "feature_key": "orders",
        "display_name": "Orders",
        "owner_team": "platform",
        "version": "1.0.0",
        "environment": "local",
        "route": "/orders",
        "entry_url": "http://localhost:3200/src/bootstrap-entry.tsx",
        "api_base_url": "http://localhost:8100/api/orders",
        "nav_json": {
            "label": "Orders",
            "icon": "package",
            "group": None,
            "order": 10,
        },
        "authorization_json": {
            "requiredPermissions": ["orders.view"],
            "requiredFlags": ["orders.enabled"],
        },
        "compatibility_json": {
            "shellContractMin": "v1",
            "shellContractMax": "v1",
        },
        "metadata_json": {
            "ownerTeam": "platform",
            "frontend": {
                "type": "module",
                "enabled": True,
                "mountFunction": "mount",
                "basePath": "/orders",
            },
            "backend": {
                "enabled": True,
                "healthEndpoint": "/health",
            },
        },
    },
    {
        "feature_key": "catalog",
        "display_name": "Catalog",
        "owner_team": "platform",
        "version": "1.0.0",
        "environment": "local",
        "route": "/catalog",
        "entry_url": "http://localhost:3300/src/bootstrap-entry.tsx",
        "api_base_url": "http://localhost:8200/api/catalog",
        "nav_json": {
            "label": "Catalog",
            "icon": "boxes",
            "group": None,
            "order": 20,
        },
        "authorization_json": {
            "requiredPermissions": ["catalog.view"],
            "requiredFlags": ["catalog.enabled"],
        },
        "compatibility_json": {
            "shellContractMin": "v1",
            "shellContractMax": "v1",
        },
        "metadata_json": {
            "ownerTeam": "platform",
            "frontend": {
                "type": "module",
                "enabled": True,
                "mountFunction": "mount",
                "basePath": "/catalog",
            },
            "backend": {
                "enabled": True,
                "healthEndpoint": "/health",
            },
        },
    },
]


def upsert_feature(db: Session, item: dict) -> Feature:
    feature = (
        db.query(Feature)
        .filter(Feature.feature_key == item["feature_key"])
        .one_or_none()
    )

    if feature is None:
        feature = Feature(
            feature_key=item["feature_key"],
            display_name=item["display_name"],
            owner_team=item["owner_team"],
        )
        db.add(feature)
        db.flush()

    return feature


def upsert_active_release(db: Session, feature: Feature, item: dict) -> None:
    existing = (
        db.query(Release)
        .filter(
            Release.feature_id == feature.id,
            Release.version == item["version"],
            Release.environment == item["environment"],
        )
        .one_or_none()
    )

    # deactivate existing active
    (
        db.query(Release)
        .filter(
            Release.feature_id == feature.id,
            Release.environment == item["environment"],
            Release.status == ReleaseStatus.active,
        )
        .update({"status": ReleaseStatus.inactive})
    )

    if existing is None:
        existing = Release(
            feature_id=feature.id,
            version=item["version"],
            environment=item["environment"],
            manifest_version="1.0",
            status=ReleaseStatus.active,
            route=item["route"],                 # ✅ set BEFORE flush
            entry_url=item["entry_url"],
            api_base_url=item["api_base_url"],
            nav_json=item["nav_json"],
            authorization_json=item["authorization_json"],
            compatibility_json=item["compatibility_json"],
            metadata_json=item["metadata_json"],
            is_deleted=False,
        )
        db.add(existing)
        db.flush()
    else:
        existing.manifest_version = "1.0"
        existing.status = ReleaseStatus.active
        existing.route = item["route"]
        existing.entry_url = item["entry_url"]
        existing.api_base_url = item["api_base_url"]
        existing.nav_json = item["nav_json"]
        existing.authorization_json = item["authorization_json"]
        existing.compatibility_json = item["compatibility_json"]
        existing.metadata_json = item["metadata_json"]
        existing.is_deleted = False


def main() -> None:
    db = SessionLocal()
    try:
        for item in LOCAL_MANIFESTS:
            feature = upsert_feature(db, item)
            upsert_active_release(db, feature, item)

        db.commit()
        print("Seeded local registry features: orders, catalog")
    finally:
        db.close()


if __name__ == "__main__":
    main()
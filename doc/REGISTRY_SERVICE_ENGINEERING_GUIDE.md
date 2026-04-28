# Portal Platform — Registry Service Engineering & Development Guide

## 1. Purpose

This document defines the engineering, development, deployment, and operational standards for the **Registry Service** in the portal platform.

The registry service is a **platform-owned service** that answers one core question:

> Which feature versions are active and allowed to be loaded by the shell in a given environment?

This guide is intentionally detailed because the registry is a foundational part of the platform. It is the control point that enables independent feature deployment without requiring shell redeployment.

---

## 2. Scope

This guide covers:

- registry service purpose and boundaries
- runtime contract with the shell
- write/admin contract with CI/CD
- service architecture and code structure
- database schema and migrations
- deployment model on Azure Container Apps
- Terraform ownership boundaries
- security and Entra authentication model
- release, promotion, and rollback flow
- observability, testing, and operational guardrails

This guide does **not** define feature shell code or shared platform infrastructure in full. Shared platform artifacts belong in the common infrastructure repository.

---

## 3. Platform ownership boundaries

A critical design decision for this platform is the split between:

1. **Common platform infrastructure repository**
2. **Service or feature-specific repository**

### 3.1 Common platform repository owns shared artifacts

Examples:

- Azure Container Registry
- Azure Container Apps Environment
- Azure Database for PostgreSQL Flexible Server
- Log Analytics Workspace
- Key Vault
- shared networking
- shared DNS
- Front Door / WAF if used
- shared monitoring foundation
- shared Service Bus namespace if applicable

### 3.2 Registry repository owns only registry-specific artifacts

Examples:

- registry service source code
- registry Container App
- registry-specific role assignments
- registry configuration
- Alembic migrations for registry schema
- CI/CD workflow for registry release
- registry-specific Terraform that consumes shared outputs

### 3.3 Important rule

The registry repository must **not** create shared platform resources such as:

- ACR
- PostgreSQL server
- Container Apps Environment
- Log Analytics Workspace
- global Key Vault
- shared VNet or DNS

The registry repository may create service-scoped items if the platform governance model allows them, but the preferred model is:

- shared DB server created centrally
- registry schema/tables created by migrations in the registry service

---

## 4. Registry service purpose

The registry service stores and serves feature release metadata.

It is the source of truth for:

- feature identity
- deployed versions
- activation status
- runtime bundle URLs
- API base URLs
- shell compatibility metadata
- feature navigation metadata
- release audit trail

The registry service allows the shell to dynamically discover active features by environment.

---

## 5. What the registry does and does not do

### 5.1 What it does

- accepts release manifests from CI/CD
- validates release manifests
- stores feature and release records
- activates and deactivates releases
- returns active runtime manifests to the shell
- supports rollback by switching active release
- audits publish and activate operations

### 5.2 What it does not do

- host frontend bundles
- proxy feature APIs
- fully evaluate end-user permissions
- replace feature flags platform
- become a generic platform control plane
- own shared infrastructure foundations

---

## 6. Service boundaries and consumers

### 6.1 Shell runtime
The shell reads active manifests from the registry and then decides which features to show based on shell-owned rules such as permissions and flags.

### 6.2 Feature CI/CD pipelines
Feature pipelines publish candidate releases and may activate releases based on environment policy.

### 6.3 Platform administrators
Platform operations can activate, rollback, retire, or inspect releases.

---

## 7. High-level architecture

```text
Feature CI/CD
   |
   | publish / activate
   v
Registry Service API
   |
   +-- Manifest Validation
   +-- Release Persistence
   +-- Activation Logic
   +-- Audit Logging
   |
   v
PostgreSQL
   ^
   |
Shell Runtime
   |
   | read active manifests
   v
Dynamic feature loading
```

---

## 8. Runtime contract with the shell

The shell must never hardcode feature entry URLs.

Instead, the shell should:

1. determine current environment
2. call the runtime endpoint
3. receive all active manifests for that environment
4. filter them by shell-owned rules
5. dynamically load the feature frontend bundle

### 8.1 Runtime read endpoint

```http
GET /api/runtime/features?environment=prod
```

### 8.2 Example runtime response

```json
{
  "environment": "prod",
  "features": [
    {
      "manifestVersion": "1.0",
      "featureKey": "orders",
      "displayName": "Orders",
      "version": "1.4.2",
      "environment": "prod",
      "route": "/orders",
      "frontend": {
        "type": "module",
        "entryUrl": "https://portal-cdn.company.com/orders/1.4.2/entry.js",
        "integrity": "sha384-example",
        "basePath": "/orders/"
      },
      "backend": {
        "apiBaseUrl": "https://orders-api-prod.company.com"
      },
      "nav": {
        "label": "Orders",
        "icon": "shopping-cart",
        "group": "Operations",
        "order": 30
      },
      "authorization": {
        "requiredPermissions": ["orders.view"],
        "requiredFlags": ["orders.enabled"]
      },
      "compatibility": {
        "shellContractMin": "1.0",
        "shellContractMax": "1.x"
      },
      "metadata": {
        "ownerTeam": "operations-platform",
        "commitSha": "abc123",
        "buildId": "20260320.7",
        "releaseDate": "2026-03-20T18:02:00Z"
      }
    }
  ]
}
```

---

## 9. Write/admin contract with CI/CD

Feature pipelines do not modify shell source code. Instead, they publish release metadata to the registry.

### 9.1 Publish release

```http
POST /api/releases
```

### 9.2 Activate release

```http
POST /api/admin/features/{featureKey}/versions/{version}/activate?environment=test
```

### 9.3 Expected release flow

1. feature pipeline builds frontend and backend
2. feature pipeline deploys feature infrastructure and services
3. pipeline runs verification
4. pipeline publishes release manifest as candidate
5. pipeline or approver activates release based on policy
6. shell sees newly active release on next registry fetch

---

## 10. Release lifecycle model

Recommended release states:

- `draft`
- `candidate`
- `active`
- `inactive`
- `retired`
- `failed`

### 10.1 Meanings

- **draft** — prepared but not yet publishable
- **candidate** — deployed and registered, but not active
- **active** — currently live for shell consumption
- **inactive** — previously active or published but not current
- **retired** — no longer allowed to become active
- **failed** — deployment or post-deploy validation failed

### 10.2 Important platform rules

- publish does not imply activate
- only one active release per feature per environment
- active routes must be unique per environment
- retired releases cannot be reactivated
- runtime endpoint must return only active releases

---

## 11. Repository structure

Recommended structure:

```text
portal-registry-service/
├── REGISTRY_SERVICE_ENGINEERING_GUIDE.md
├── README.md
├── requirements.txt
├── Dockerfile
├── alembic.ini
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── schemas/
│   ├── services/
│   ├── exceptions.py
│   └── main.py
├── infra/
│   ├── providers.tf
│   ├── variables.tf
│   ├── data-platform.tf
│   ├── locals.tf
│   ├── container-app.tf
│   ├── role-assignments.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── migrations/
│   ├── env.py
│   └── versions/
├── scripts/
│   ├── build_image.sh
│   ├── deploy_registry.sh
│   ├── run_migrations.sh
│   └── smoke_test.sh
└── .github/
    └── workflows/
        └── registry-release.yml
```

---

## 12. Code architecture

### 12.1 `app/api`
Route definitions and dependency wiring.

### 12.2 `app/core`
Configuration, security, and cross-cutting concerns.

### 12.3 `app/db`
SQLAlchemy models and session setup.

### 12.4 `app/schemas`
Pydantic request and response models.

### 12.5 `app/services`
Business logic:
- validation
- release persistence
- activation
- runtime projection
- auditing

### 12.6 `migrations`
Alembic migrations for schema lifecycle.

### 12.7 `infra`
Registry-specific Terraform only.

### 12.8 `scripts`
Deployment and operational helper scripts.

---

## 13. Data model

### 13.1 `features`
Stable feature identity.

Fields:
- feature key
- display name
- owner team
- repository URL

### 13.2 `releases`
A feature version in an environment.

Fields:
- feature ID
- manifest version
- release version
- environment
- status
- route
- frontend entry URL
- backend API base URL
- nav metadata
- authorization metadata
- compatibility metadata
- release metadata
- activation time

### 13.3 `audits`
Action history.

Fields:
- action
- feature key
- version
- environment
- actor
- details JSON
- timestamp

---

## 14. Manifest contract

### 14.1 Why the manifest matters

The release manifest is the interface between feature CI/CD and the registry. It must be versioned, validated, and stable.

### 14.2 Required fields

- `manifestVersion`
- `featureKey`
- `displayName`
- `version`
- `environment`
- `route`
- `frontend.entryUrl`
- `backend.apiBaseUrl`
- `nav`
- `metadata.ownerTeam`

### 14.3 Example manifest

```json
{
  "manifestVersion": "1.0",
  "featureKey": "orders",
  "displayName": "Orders",
  "version": "1.4.2",
  "environment": "test",
  "route": "/orders",
  "frontend": {
    "type": "module",
    "entryUrl": "https://portal-cdn.company.com/orders/1.4.2/entry.js",
    "integrity": "sha384-example",
    "basePath": "/orders/"
  },
  "backend": {
    "apiBaseUrl": "https://orders-api-test.company.com"
  },
  "nav": {
    "label": "Orders",
    "icon": "shopping-cart",
    "group": "Operations",
    "order": 30
  },
  "authorization": {
    "requiredPermissions": ["orders.view"],
    "requiredFlags": ["orders.enabled"]
  },
  "compatibility": {
    "shellContractMin": "1.0",
    "shellContractMax": "1.x"
  },
  "metadata": {
    "ownerTeam": "operations-platform",
    "commitSha": "abc123",
    "buildId": "20260320.7",
    "releaseDate": "2026-03-20T18:02:00Z"
  }
}
```

---

## 15. Validation rules

The registry must reject invalid manifests.

Minimum validation:

- version must be semver
- route must start with `/`
- frontend entry URL must use HTTPS
- backend API base URL must use HTTPS
- frontend host must be in approved host list
- backend host must be in approved host list
- manifest version must be supported
- duplicate route conflicts must be prevented for active releases
- feature key scope must be allowed for the calling pipeline

Optional stronger validation:

- HEAD request or GET request confirms entry URL exists
- health endpoint confirms backend is reachable
- nav labels conform to naming standards
- compatibility range is not malformed

---

## 16. Azure hosting model

The registry service is hosted on **Azure Container Apps**, not App Service.

### 16.1 Why Container Apps

- aligns with service-oriented platform direction
- fits containerized FastAPI deployment
- supports managed identity
- supports revisions and rollback
- supports low operational overhead
- fits early project phases where App Service is not planned

### 16.2 Registry hosting recommendation

- one dedicated Container App for the registry
- Container Apps Environment owned by common infrastructure repo
- minimum 1 replica
- external ingress only if shell reads directly from browser
- internal ingress preferred if shell uses BFF or gateway later

### 16.3 Revision mode

For initial phases:
- `revision_mode = "Single"`

Later:
- can move to `Multiple` for controlled canary rollout

---

## 17. Terraform ownership model

### 17.1 Shared infra repository creates

- ACR
- Container Apps Environment
- PostgreSQL Flexible Server
- Log Analytics
- Key Vault
- network, DNS, and other common platform resources

### 17.2 Registry repository Terraform creates

- registry Container App
- registry-specific role assignments
- registry service configuration wiring

### 17.3 Registry repository should consume shared outputs

Preferred options:
- `terraform_remote_state`
- pipeline-provided variables

### 17.4 Do not duplicate shared infra creation

The registry service Terraform must not independently create shared platform foundations.

---

## 18. Security and authentication model

### 18.1 Two auth surfaces

The registry exposes two logical surfaces:

#### Runtime read API
- used by shell
- read-only
- audience dedicated to runtime
- role: `registry.runtime.read`

#### Admin/write API
- used by CI/CD and platform admins
- write/activate operations
- audience dedicated to admin
- roles:
  - `registry.release.write`
  - `registry.release.activate`

### 18.2 Entra ID model

Recommended logical identity model:

- runtime audience: `api://portal-registry-runtime`
- admin audience: `api://portal-registry-admin`

### 18.3 Feature scope

The registry should validate that a pipeline can only publish for its own feature.

Example claim:
```json
{
  "feature_keys": ["orders"]
}
```

### 18.4 Important division of responsibility

Registry authorization decides:
- may caller read runtime manifests?
- may caller publish release?
- may caller activate release for target feature?

Shell authorization decides:
- should current user see the feature in nav?
- do feature flags or claims allow rendering?

Feature API authorization decides:
- may user perform the business action?

---

## 19. CI/CD model

### 19.1 Registry service repository pipeline

Registry service pipeline should:

1. run lint and tests
2. build container image
3. push image to shared ACR
4. deploy registry Container App
5. run database migrations
6. smoke test `/health`
7. optionally smoke test runtime endpoint

### 19.2 Feature repository pipeline interaction with registry

Feature pipeline should:

1. build frontend and backend
2. deploy feature-specific artifacts
3. run feature smoke tests
4. create final manifest
5. publish candidate release to registry
6. activate release based on environment policy

---

## 20. Rollback strategy

### 20.1 Registry service rollback
Use Container Apps revisions to rollback registry application code.

### 20.2 Feature release rollback
Use registry activation to point shell back to a previous active feature release.

This is one of the biggest benefits of the registry.

---

## 21. Observability

The registry service must have:

- structured application logging
- request correlation
- audit logging for publish/activate operations
- health endpoint
- metrics if available
- revision visibility in deployment logs

Recommended metadata to include in logs:
- actor
- feature key
- version
- environment
- request ID
- operation name

---

## 22. Testing strategy

### 22.1 Unit tests
- manifest validation
- activation logic
- runtime projection logic

### 22.2 Integration tests
- release publish against test DB
- activate release and verify uniqueness rules
- runtime endpoint returns active releases only

### 22.3 Contract tests
- ensure runtime response schema stays stable
- ensure manifest input stays compatible

### 22.4 Deployment smoke tests
- `/health` returns 200
- publish candidate release in test environment
- activate test release
- runtime endpoint returns expected manifest

---

## 23. Operational guardrails

- do not activate before verification
- do not hardcode feature URLs in shell
- do not allow one feature pipeline to update another feature
- do not delete previous release metadata aggressively
- do not let runtime endpoint return candidate releases
- do not put shared infra creation in service repo Terraform

---

## 24. Local development guidance

### 24.1 Local app run
- local Postgres or dev shared Postgres
- `AUTH_DISABLED=true` allowed only for local development
- use migrations before app run
- validate sample manifests locally

### 24.2 Local startup sequence
1. create Python virtual environment
2. install requirements
3. configure `.env`
4. run Alembic migration
5. run Uvicorn
6. call `/health`

---

## 25. Production readiness checklist

- runtime/admin audience split defined
- feature scope enforcement implemented
- migration process automated
- registry app deployed on Container Apps
- ACR pull role assigned
- runtime endpoint smoke tested
- audit logging enabled
- rollback path documented
- Terraform boundary aligned to shared/common repo model

---

## 26. Summary

The registry service is the platform control point that makes independent feature deployment viable.

The most important design principles are:

1. the registry decides what is live
2. the shell discovers features dynamically through the registry
3. service repo Terraform must only own service-specific artifacts
4. shared infrastructure belongs in the common platform repo
5. publish and activate are separate actions
6. security is split between runtime reads and admin writes
7. rollback must be fast and mostly configuration-driven

This repository includes a full reference scaffold aligned to these principles.

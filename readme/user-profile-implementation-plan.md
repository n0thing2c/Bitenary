# User Health Profile Implementation Plan

## Goal

Build a user-owned health profile that stores the physiological, activity, goal,
and dietary-preference data required to personalize future recipes and meal
plans. Authentik remains the source of truth for account identity; the profile
feature does not edit usernames, email addresses, passwords, or OIDC data.

## Scope

### Backend v1

- Persist one health profile per user.
- Persist normalized allergy, dietary-restriction, taste, and disliked-food
  preferences.
- Expose authenticated APIs to load, create, update, and skip profile
  onboarding.
- Require double-submit CSRF protection for every state-changing operation.
- Keep health-profile values out of application logs and MCP audit records.
- Return an onboarding state of `NOT_STARTED`, `SKIPPED`, or `COMPLETED`.

### Frontend v1

- Add an authenticated application shell and profile routes.
- Show a three-section onboarding form for biological data, activity and goals,
  and dietary parameters.
- Allow onboarding to be skipped without prompting again on every login.
- Add a health-profile page and an edit drawer that reuse the same form schema.
- Display account identity as read-only data obtained from Authentik.

### Deferred

- BMR, AMR/TDEE, macronutrient, hydration, deficiency-risk, and meal-structure
  calculations.
- Medical diagnosis or treatment recommendations.
- Historical measurement tracking.
- Profile deletion and data-export workflows.

Derived health metrics must not be displayed until their formulas, source
references, rounding rules, and fallback behavior have been implemented and
reviewed.

## Data Model

### `users`

Add `profile_onboarding_dismissed_at TIMESTAMPTZ NULL`.

The onboarding state is derived as follows:

- A health-profile row exists: `COMPLETED`.
- No profile exists and `profile_onboarding_dismissed_at` is set: `SKIPPED`.
- Neither condition is true: `NOT_STARTED`.

### `health_profiles`

- `user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE`
- `date_of_birth DATE NOT NULL`
- `gender health_profile_gender NOT NULL`
- `weight_kg NUMERIC(6,2) NOT NULL CHECK (weight_kg > 0)`
- `height_cm NUMERIC(6,2) NOT NULL CHECK (height_cm > 0)`
- `activity_level health_profile_activity_level NOT NULL`
- `primary_goal health_profile_primary_goal NOT NULL`
- `target_weight_kg NUMERIC(6,2) NULL CHECK (target_weight_kg > 0)`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Store `date_of_birth`, not a mutable age or a year-only value.

### `health_profile_preferences`

- `preference_id UUID PRIMARY KEY`
- `user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE`
- `preference_type health_profile_preference_type NOT NULL`
- `value VARCHAR(100) NOT NULL`
- `normalized_value VARCHAR(100) NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- Unique constraint on `(user_id, preference_type, normalized_value)`.

Preference types are `ALLERGY`, `DIETARY_RESTRICTION`, `TASTE`, and `DISLIKE`.
Dietary restrictions remain separate from allergies so voluntary or cultural
constraints are not represented as medical reactions.

## Backend Design

Create a `health_profile` feature package following the existing backend
layers:

```text
health_profile/
├── delivery/        # FastAPI routes and Pydantic DTOs
├── domain/          # Entities, enums, and feature errors
├── infrastructure/  # SQLAlchemy models and repositories
├── repository/      # Repository protocols
├── service/         # Profile use cases and normalization
└── wiring.py        # FastAPI dependency assembly
```

### API

| Method | Endpoint | Behavior | Protection |
| --- | --- | --- | --- |
| `GET` | `/api/health-profile` | Return account summary, onboarding state, and optional profile | Web auth |
| `PUT` | `/api/health-profile` | Create or replace the current user's profile | Web auth + CSRF |
| `POST` | `/api/health-profile/onboarding/skip` | Persist onboarding dismissal | Web auth + CSRF |

The client never supplies a `user_id`; ownership always comes from
`CurrentUser`.

### Validation

- Date of birth must be earlier than the current date.
- Weight, height, and optional target weight must be greater than zero.
- Enum fields must use supported values.
- Preference values are trimmed, internal whitespace is collapsed, empty values
  are rejected, and values longer than 100 characters are rejected.
- Duplicate preferences are removed case-insensitively within each type.
- Saving the profile and replacing its preferences occurs in one transaction.

## Frontend Design

- Add `react-router-dom` and authenticated routes for `/profile/setup` and
  `/profile`.
- Load the health-profile envelope after web authentication completes.
- Redirect `NOT_STARTED` users to onboarding; allow `SKIPPED` and `COMPLETED`
  users to continue normally.
- Reuse one typed form model for onboarding and later editing.
- Obtain a fresh CSRF token before `PUT` and onboarding-skip requests.
- Do not render fabricated derived health metrics while the calculation engine
  is deferred.

## Test Plan

### Backend

- Domain/service validation and preference normalization.
- Onboarding-state derivation and skip behavior.
- Create and update behavior with transactional preference replacement.
- Route authentication and CSRF requirements.
- Request validation and safe response serialization.
- Owner scoping and disabled-user behavior.
- Alembic online/offline migration compatibility.
- Full backend regression suite.

### Frontend

- Loading, unauthenticated, not-started, skipped, and completed states.
- Onboarding validation, skip, initialize, update, cancel, and network errors.
- Responsive form and drawer behavior.
- Production TypeScript/Vite build.

## Delivery Order

1. Add the migration and backend domain contracts.
2. Implement SQLAlchemy persistence and service use cases.
3. Mount the authenticated HTTP API and add backend tests.
4. Add frontend routing, API types, onboarding, profile display, and editing.
5. Run regression, security, accessibility, and responsive checks.
6. Implement derived-metric calculation as a separately reviewed phase.

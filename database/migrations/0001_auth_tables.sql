BEGIN;

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'analyst',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_users_role
        CHECK (role IN ('admin', 'analyst', 'operator')),

    CONSTRAINT chk_users_status
        CHECK (status IN ('active', 'disabled'))
);

CREATE UNIQUE INDEX uq_users_email_lower
    ON users (LOWER(email));

CREATE TABLE auth_sessions (
    jti UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_auth_sessions_user_id
    ON auth_sessions(user_id);

CREATE INDEX idx_auth_sessions_expires_at
    ON auth_sessions(expires_at);

COMMIT;

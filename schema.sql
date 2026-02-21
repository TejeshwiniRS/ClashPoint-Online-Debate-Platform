CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    status          VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'banned')),
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auth0_id        TEXT UNIQUE
);

CREATE TABLE community (
    id                  SERIAL PRIMARY KEY,
    title               VARCHAR(255) NOT NULL,
    description         TEXT NOT NULL,
    start_time          TIMESTAMP NOT NULL,
    end_time            TIMESTAMP NOT NULL,
    secret_code_hash    VARCHAR(255),
    owner_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status              VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE clash (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL,
    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP NOT NULL,
    status          VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    owner_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    community_id    INTEGER REFERENCES community(id) ON DELETE CASCADE,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE arguments (
    id              SERIAL PRIMARY KEY,
    owner_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    clash_id        INTEGER NOT NULL REFERENCES clash(id) ON DELETE CASCADE,
    argument_type   VARCHAR(10) NOT NULL CHECK (argument_type IN ('for', 'against')),
    up_votes        INTEGER DEFAULT 0 CHECK (up_votes >= 0),
    down_votes      INTEGER DEFAULT 0 CHECK (down_votes >= 0),
    content         TEXT NOT NULL,
    parent_id       INTEGER REFERENCES arguments(id) ON DELETE CASCADE,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted      BOOLEAN DEFAULT FALSE
);

CREATE TABLE community_users (
    id               SERIAL PRIMARY KEY,
    community_id     INTEGER NOT NULL REFERENCES community(id) ON DELETE CASCADE,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active_member BOOLEAN DEFAULT TRUE,
    role             VARCHAR(20) DEFAULT 'member' CHECK (role IN ('owner', 'member')),
    joined_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (community_id, user_id)
);

CREATE TABLE tags (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE clash_tag (
    id          SERIAL PRIMARY KEY,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    clash_id    INTEGER NOT NULL REFERENCES clash(id) ON DELETE CASCADE,
    UNIQUE (tag_id, clash_id)
);

CREATE TABLE report (
    id              SERIAL PRIMARY KEY,
    reported_by     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason          TEXT NOT NULL,
    argument_id     INTEGER NOT NULL REFERENCES arguments(id) ON DELETE CASCADE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLASH SEARCH VECTOR
ALTER TABLE clash ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE INDEX IF NOT EXISTS idx_clash_search ON clash USING GIN (search_vector);

CREATE OR REPLACE FUNCTION clash_search_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvectorupdate
BEFORE INSERT OR UPDATE ON clash
FOR EACH ROW EXECUTE FUNCTION clash_search_trigger();

-- COMMUNITY SEARCH VECTOR
ALTER TABLE community ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE INDEX IF NOT EXISTS community_search_idx ON community USING GIN (search_vector);

CREATE OR REPLACE FUNCTION community_search_vector_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvectorupdate_community
BEFORE INSERT OR UPDATE ON community
FOR EACH ROW EXECUTE FUNCTION community_search_vector_trigger();

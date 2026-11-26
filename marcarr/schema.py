"""The database schema, one function per migration (append, never edit).

The model (docs/PLAN.md "Identity"): a **title** is a film, a show or an
episode, named by a provider id. A **video** is one source revision of a
title: the same content at a new path is the same video, a re-encode is a new
one. Every step result, tag and face hangs off a video.
"""

from __future__ import annotations

from collections.abc import Callable


def _v1() -> str:
    return """
        CREATE TABLE titles (
            id          TEXT PRIMARY KEY,      -- movie:tmdb:671, show:tvdb:79168, episode:..., plex:123
            type        TEXT NOT NULL,         -- movie | show | episode
            name        TEXT NOT NULL,
            sort_name   TEXT NOT NULL DEFAULT '',
            year        INTEGER,
            parent_id   TEXT,                  -- an episode's show
            season      INTEGER,
            episode     INTEGER,
            plex_key    TEXT,                  -- rating key: a hint, not the identity
            plex_section TEXT,
            tmdb_id     INTEGER,
            tvdb_id     INTEGER,
            imdb_id     TEXT,
            collection  TEXT,
            summary     TEXT NOT NULL DEFAULT '',
            poster      TEXT NOT NULL DEFAULT '',   -- Plex thumb path
            duration    REAL,
            file        TEXT NOT NULL DEFAULT '',   -- the file Plex points at (Marcarr's path)
            gone        INTEGER NOT NULL DEFAULT 0, -- no longer in Plex
            added_at    TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        CREATE INDEX titles_parent ON titles (parent_id, season, episode);
        CREATE INDEX titles_plex ON titles (plex_key);

        CREATE TABLE videos (
            id          TEXT PRIMARY KEY,      -- short content id
            content_key TEXT NOT NULL UNIQUE,  -- sampled hash + size + duration + layout
            title_id    TEXT NOT NULL REFERENCES titles(id) ON DELETE CASCADE,
            path        TEXT NOT NULL,         -- where it was last seen (Marcarr's view)
            edition     TEXT NOT NULL DEFAULT '',
            size        INTEGER,
            duration    REAL,
            width       INTEGER,
            height      INTEGER,
            streams     TEXT NOT NULL DEFAULT '[]',
            mtime       REAL,
            current     INTEGER NOT NULL DEFAULT 1,   -- the file the title points at now
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL
        );
        CREATE INDEX videos_title ON videos (title_id);
        CREATE INDEX videos_path ON videos (path);

        CREATE TABLE steps (
            video_id    TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            step        TEXT NOT NULL,
            state       TEXT NOT NULL,         -- done | failed | none | off | run | queued
            detail      TEXT NOT NULL DEFAULT '',
            inputs      TEXT NOT NULL DEFAULT '{}',  -- finished_at of the steps it read
            version     INTEGER NOT NULL DEFAULT 1,
            seconds     REAL,
            ai_cost     REAL NOT NULL DEFAULT 0,
            progress    REAL,
            started_at  TEXT,
            finished_at TEXT,
            PRIMARY KEY (video_id, step)
        );

        CREATE TABLE results (
            video_id   TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            step       TEXT NOT NULL,
            doc        TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (video_id, step)
        );

        CREATE TABLE scene_edits (
            video_id   TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            kind       TEXT NOT NULL,          -- cut (a boundary added) | join (one removed)
            at         REAL NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (video_id, kind, at)
        );

        CREATE TABLE casts (
            title_id   TEXT PRIMARY KEY REFERENCES titles(id) ON DELETE CASCADE,
            source     TEXT NOT NULL,
            doc        TEXT NOT NULL,          -- [{"person", "actor", "character", "photo", "order"}]
            updated_at TEXT NOT NULL
        );

        CREATE TABLE people (
            id         TEXT PRIMARY KEY,       -- ron-weasley
            actor      TEXT NOT NULL DEFAULT '',
            character  TEXT NOT NULL DEFAULT '',
            photo      TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE tags (
            id          TEXT PRIMARY KEY,      -- tag_<hex>
            video_id    TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            title_id    TEXT NOT NULL,
            tag         TEXT NOT NULL,         -- vocab id: christmas
            start       REAL NOT NULL,
            end         REAL NOT NULL,
            status      TEXT NOT NULL,         -- proposed | accepted | rejected
            source      TEXT NOT NULL,         -- person | ai:<model> | fanscut | doblarr | mcp
            confidence  REAL,
            people      TEXT NOT NULL DEFAULT '[]',
            evidence    TEXT NOT NULL DEFAULT '{"heard":[],"seen":[]}',
            summary     TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        CREATE INDEX tags_video ON tags (video_id, start);
        CREATE INDEX tags_status ON tags (status, tag);

        CREATE TABLE faces (
            id         TEXT PRIMARY KEY,
            video_id   TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            person_id  TEXT,
            at         REAL NOT NULL,
            score      REAL NOT NULL DEFAULT 0,
            box        TEXT,                   -- [x, y, w, h] in 0..1
            confirmed  INTEGER,                -- 1 yes, 0 no, NULL not looked at
            created_at TEXT NOT NULL
        );
        CREATE INDEX faces_video ON faces (video_id, at);
        CREATE INDEX faces_person ON faces (person_id);

        CREATE TABLE places (
            id         TEXT PRIMARY KEY,       -- hogwarts/great-hall
            name       TEXT NOT NULL,
            parent_id  TEXT REFERENCES places(id) ON DELETE CASCADE,
            franchise  TEXT NOT NULL DEFAULT '',
            implies    TEXT NOT NULL DEFAULT '[]',
            status     TEXT NOT NULL DEFAULT 'accepted',
            source     TEXT NOT NULL DEFAULT 'person',
            created_at TEXT NOT NULL
        );
        CREATE TABLE place_scenes (
            place_id   TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
            video_id   TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            start      REAL NOT NULL,
            end        REAL NOT NULL,
            status     TEXT NOT NULL DEFAULT 'accepted',
            source     TEXT NOT NULL DEFAULT 'person',
            created_at TEXT NOT NULL,
            PRIMARY KEY (place_id, video_id, start)
        );

        CREATE TABLE api_keys (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            key_hash   TEXT NOT NULL UNIQUE,
            prefix     TEXT NOT NULL,
            scopes     TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used  TEXT
        );

        CREATE TABLE webhooks (
            id         TEXT PRIMARY KEY,
            url        TEXT NOT NULL,
            events     TEXT NOT NULL,
            secret     TEXT NOT NULL,
            enabled    INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE webhook_calls (
            id         TEXT PRIMARY KEY,
            webhook_id TEXT NOT NULL,
            url        TEXT NOT NULL,
            event      TEXT NOT NULL,
            payload    TEXT NOT NULL,
            at         TEXT NOT NULL,
            code       INTEGER,
            error      TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE ai_usage (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            at        TEXT NOT NULL,
            video_id  TEXT,
            step      TEXT NOT NULL,
            cost      REAL NOT NULL,
            tokens    INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE kv (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE http_cache (
            key        TEXT PRIMARY KEY,
            body       TEXT NOT NULL,
            fetched_at REAL NOT NULL
        );

        CREATE TABLE jobs (
            id         TEXT PRIMARY KEY,
            kind       TEXT NOT NULL,
            title      TEXT NOT NULL DEFAULT '',
            status     TEXT NOT NULL DEFAULT 'queued',  -- queued|running|done|failed|cancelled
            progress   REAL NOT NULL DEFAULT 0,
            message    TEXT NOT NULL DEFAULT '',
            payload    TEXT NOT NULL DEFAULT '{}',
            result     TEXT NOT NULL DEFAULT '{}',
            lane       TEXT NOT NULL DEFAULT 'light',
            phase      TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX jobs_status_created ON jobs (status, created_at);
    """


def _v2() -> str:
    # A collection is a saved scene search, not a list of scenes: what it shows is
    # worked out when it is opened, so new matching scenes appear by themselves.
    return """
        CREATE TABLE collections (
            id         TEXT PRIMARY KEY,       -- col_<hex>
            name       TEXT NOT NULL,
            tags       TEXT NOT NULL DEFAULT '[]',   -- vocab ids, a scene must have all
            person     TEXT,                   -- person id, must be on screen
            q          TEXT NOT NULL DEFAULT '',     -- words in the dialogue
            signals    TEXT NOT NULL DEFAULT '[]',   -- measured signal ids, each over half the scene
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX collections_name ON collections (name COLLATE NOCASE);
    """


def _v3() -> str:
    # Custom tags ("My tags"): the person's own additions to the bundled tag list.
    # title_id NULL: the whole library; else one movie, or one show and its episodes.
    return """
        CREATE TABLE custom_tags (
            id         TEXT PRIMARY KEY,       -- slug, never a bundled id, never fc:
            name       TEXT NOT NULL,
            family     TEXT,                   -- a bundled family, or NULL (none)
            hint       TEXT NOT NULL DEFAULT '',
            see        TEXT NOT NULL DEFAULT '[]',   -- things to look for
            hear       TEXT NOT NULL DEFAULT '[]',   -- words to listen for
            title_id   TEXT,                   -- scope: NULL, a movie or a show
            retired    INTEGER NOT NULL DEFAULT 0,   -- kept on its scenes, not proposed again
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX custom_tags_name ON custom_tags (name COLLATE NOCASE);
    """


def _v4() -> str:
    # How a character is in a scene. A tag's `people` are the ones seen on screen and
    # its `mentioned` the ones only named in the dialogue. `presence` holds the rest:
    # what apps and people report outside a tag (a speaker Doblarr found, a name
    # someone heard), each with its source and the moment that shows it.
    return """
        ALTER TABLE tags ADD COLUMN mentioned TEXT NOT NULL DEFAULT '[]';
        CREATE TABLE presence (
            id         TEXT PRIMARY KEY,       -- pre_<hex>
            video_id   TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            person_id  TEXT NOT NULL,
            start      REAL NOT NULL,
            end        REAL NOT NULL,
            how        TEXT NOT NULL,          -- seen | mentioned | speaker
            at         REAL,                   -- the moment that shows it
            source     TEXT NOT NULL,          -- person | doblarr | fanscut | mcp | ai:<model>
            status     TEXT NOT NULL,          -- proposed | accepted | rejected
            note       TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX presence_video ON presence (video_id, start);
        CREATE INDEX presence_person ON presence (person_id);
    """


MIGRATIONS: list[Callable[[], str]] = [_v1, _v2, _v3, _v4]

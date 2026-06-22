-- Job Application Autopilot — SQLite Schema

CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_url         TEXT NOT NULL UNIQUE,
    job_title       TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    job_type        TEXT,
    expires         TEXT,
    relevance_score INTEGER,
    status          TEXT NOT NULL DEFAULT 'pending',
    cv_path         TEXT,
    cover_letter_path TEXT,
    contact_email   TEXT,
    email_subject   TEXT,
    sent_at         TIMESTAMP,
    follow_up_at    TIMESTAMP,
    followed_up_at  TIMESTAMP,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_status    ON applications(status);
CREATE INDEX IF NOT EXISTS idx_company   ON applications(company);
CREATE INDEX IF NOT EXISTS idx_sent_at   ON applications(sent_at);
CREATE INDEX IF NOT EXISTS idx_follow_up ON applications(follow_up_at);
-- ============================================================
--  Climate Research Management System  –  Database Setup
-- ============================================================

CREATE DATABASE IF NOT EXISTS climate_research;
USE climate_research;

-- ── Users ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100)        NOT NULL,
    email      VARCHAR(100) UNIQUE NOT NULL,
    password   VARCHAR(256)        NOT NULL,   -- store sha256 hash in production
    role       VARCHAR(50)         NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMP           DEFAULT CURRENT_TIMESTAMP
);

-- ── Climate Data ───────────────────────────────────────────
--  NOTE: app.py uses the table name  climate_data  (not climate_records).
--  This file now matches that name to prevent runtime errors.
CREATE TABLE IF NOT EXISTS climate_data (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    country     VARCHAR(100) NOT NULL,
    region      VARCHAR(100) NOT NULL,
    date        DATE         NOT NULL,
    temperature FLOAT,
    rainfall    FLOAT,
    co2         FLOAT,
    humidity    FLOAT,
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_country (country),
    INDEX idx_date    (date)
);

-- ── Sample Users ───────────────────────────────────────────
-- Passwords below are plain-text for demo convenience.
-- In production, store SHA-256 hashes instead.
INSERT INTO users (name, email, password, role) VALUES
    ('Admin User',  'admin@climate.org',  'admin123',  'admin'),
    ('Staff User',  'staff@climate.org',  'staff123',  'staff'),
    ('Viewer User', 'viewer@climate.org', 'viewer123', 'viewer')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ── Sample Climate Data ────────────────────────────────────
INSERT INTO climate_data (country, region, date, temperature, rainfall, co2, humidity) VALUES
    ('India',     'Tamil Nadu',       '2024-06-01', 38.2,  12.5, 415.2, 78),
    ('India',     'Maharashtra',      '2024-06-02', 36.1,   8.3, 413.8, 72),
    ('Brazil',    'Amazonia',         '2024-06-02', 27.8,  89.3, 398.1, 91),
    ('Brazil',    'Sao Paulo',        '2024-06-03', 24.5,  35.7, 402.4, 83),
    ('Norway',    'Oslo',             '2024-06-03', 14.1,   5.2, 385.4, 62),
    ('Australia', 'Queensland',       '2024-06-04', 41.7,   0.4, 422.8, 34),
    ('Australia', 'New South Wales',  '2024-06-05', 38.9,   1.1, 419.3, 40),
    ('Canada',    'British Columbia', '2024-06-05', 19.3,  18.9, 401.5, 70),
    ('Germany',   'Bavaria',          '2024-06-06', 21.5,   9.7, 388.3, 66),
    ('Japan',     'Tokyo',            '2024-06-06', 29.4,  22.1, 410.7, 75);
-- PostgreSQL extensions yang dibutuhkan IDEA Portal
-- Akan dijalankan otomatis saat container postgres pertama kali boot

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";       -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";         -- crypto functions (gen_random_uuid)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";          -- trigram search (utk fuzzy match NIK/nama)
CREATE EXTENSION IF NOT EXISTS "btree_gin";        -- composite GIN indexes

-- Additive only. Apply explicitly after review; never run at application startup.
BEGIN;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS revision BIGINT NOT NULL DEFAULT 0;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
CREATE TABLE IF NOT EXISTS site_delivery_sources (
  application_id INTEGER NOT NULL REFERENCES applications(id),
  provider TEXT NOT NULL CHECK (provider IN ('telegram','railway-s3','s3')),
  telegram_chat_id BIGINT,
  telegram_message_id INTEGER,
  telegram_channel_username TEXT,
  telegram_file_id TEXT,
  filename TEXT,
  size_bytes BIGINT CHECK (size_bytes IS NULL OR size_bytes > 0),
  mime_type TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (application_id, provider),
  CHECK (provider <> 'telegram' OR (
    telegram_message_id IS NOT NULL AND telegram_message_id > 0
    AND telegram_channel_username IS NOT NULL
    AND telegram_channel_username ~ '^[a-z][a-z0-9_]{4,31}$'
    AND (telegram_chat_id IS NULL OR telegram_chat_id < 0)
  )),
  CHECK (telegram_file_id IS NULL OR (length(telegram_file_id) <= 512 AND telegram_file_id ~ '^[A-Za-z0-9_-]+$'))
);
CREATE OR REPLACE FUNCTION wz_catalog_revision() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.revision := OLD.revision + 1;
  NEW.updated_at := clock_timestamp();
  RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER wz_catalog_revision BEFORE UPDATE ON applications
  FOR EACH ROW EXECUTE FUNCTION wz_catalog_revision();
CREATE OR REPLACE FUNCTION wz_delivery_revision() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  -- Both clients lock the application before changing a source. Direct metadata
  -- writes also invalidate outstanding owner revisions and download tokens.
  UPDATE applications SET updated_at=clock_timestamp() WHERE id=COALESCE(NEW.application_id,OLD.application_id);
  RETURN COALESCE(NEW,OLD);
END $$;
CREATE OR REPLACE TRIGGER wz_delivery_revision AFTER INSERT OR UPDATE OR DELETE ON site_delivery_sources
  FOR EACH ROW EXECUTE FUNCTION wz_delivery_revision();
COMMIT;

-- Схема БД учебного стенда «как реализовано разработкой».
-- Ночная сверка сравнивает её с systems/example-system/erd/client.dbml («как согласовано»).
-- Практика: добавьте сюда колонку, пересоздайте стенд и запустите scripts/drift.sh.

CREATE TYPE request_result AS ENUM ('OK', 'NOT_FOUND', 'VALIDATION_ERROR', 'DEPENDENCY_ERROR');

CREATE TABLE partner (
  id          uuid PRIMARY KEY,
  code        varchar(32)  NOT NULL UNIQUE,
  name        varchar(255) NOT NULL,
  is_active   boolean      NOT NULL DEFAULT true,
  created_at  timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE partner_request_log (
  id              bigserial PRIMARY KEY,
  partner_id      uuid           NOT NULL REFERENCES partner (id),
  operation_id    varchar(64)    NOT NULL,
  client_id_mask  varchar(14)    NOT NULL,
  result          request_result NOT NULL,
  http_status     smallint       NOT NULL,
  duration_ms     int            NOT NULL,
  correlation_id  uuid           NOT NULL,
  created_at      timestamptz    NOT NULL DEFAULT now()
);

CREATE INDEX ON partner_request_log (partner_id, created_at);
CREATE INDEX ON partner_request_log (correlation_id);

"""
Учебный стенд example-system — заменяет тестовый стенд банка на время практики.
Реализует контракт systems/example-system/api/openapi.yaml.
Только стандартная библиотека Python, данные синтетические.

Чтобы потренировать «ночную сверку», меняйте поведение здесь (например, переименуйте
поле в ответе) и смотрите, как scripts/drift.sh находит расхождение с контрактом.
"""
import json
import os
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY = os.environ.get("API_KEY", "demo-key")
CLIENT_ID = re.compile(r"^(\d{9}|\d{14})$")

CLIENTS = {
    "300000001": {
        "clientId": "300000001",
        "clientType": "LEGAL_ENTITY",
        "name": "OOO «Primer Savdo»",
        "directorGender": "FEMALE",
        "registeredAt": "2019-03-14",
    },
    "31234567890123": {
        "clientId": "31234567890123",
        "clientType": "INDIVIDUAL_ENTREPRENEUR",
        "name": "Primerov Primer",
        "directorGender": "MALE",
        "registeredAt": "2021-07-01",
    },
}

ACCOUNTS = {
    "300000001": [
        {"accountNumber": "20208000900000000001", "currency": "UZS", "isMain": True,
         "balance": {"value": "1500000.00", "currency": "UZS"}},
        {"accountNumber": "20208840900000000002", "currency": "USD", "isMain": False,
         "balance": {"value": "120.50", "currency": "USD"}},
    ],
    "31234567890123": [],
}


class Handler(BaseHTTPRequestHandler):
    server_version = "example-stand/1.0"

    def _send(self, status, body, corr):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Correlation-Id", corr)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status, code, message, corr, details=None):
        body = {"code": code, "message": message, "correlationId": corr}
        if details:
            body["details"] = details
        self._send(status, body, corr)

    def do_GET(self):
        corr = self.headers.get("X-Correlation-Id") or ""
        try:
            corr = str(uuid.UUID(corr))
        except ValueError:
            corr = str(uuid.uuid4())

        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self._send(200, {"status": "ok"}, corr)

        m = re.fullmatch(r"/v1/clients/([^/]+)(/accounts)?", path)
        if not m:
            return self._error(404, "NOT_FOUND", "Resource not found", corr)

        if self.headers.get("X-API-Key") != API_KEY:
            return self._error(401, "UNAUTHORIZED", "Invalid API key", corr)

        client_id, accounts = m.group(1), m.group(2)
        if not CLIENT_ID.match(client_id):
            return self._error(422, "VALIDATION_ERROR", "Request validation failed", corr,
                               [{"field": "clientId", "issue": "must be 9 or 14 digits"}])

        client = CLIENTS.get(client_id)
        if client is None:
            return self._error(404, "CLIENT_NOT_FOUND", "Client not found", corr)

        if accounts:
            return self._send(200, {"items": ACCOUNTS.get(client_id, [])}, corr)
        return self._send(200, client, corr)

    def _not_allowed(self):
        corr = str(uuid.uuid4())
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Content-Type", "application/json")
        data = json.dumps({"code": "METHOD_NOT_ALLOWED", "message": "Method not allowed",
                           "correlationId": corr}).encode()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def __getattr__(self, name):
        # любой метод, кроме GET (POST, TRACE, QUERY …) → 405, а не 501
        if name.startswith("do_"):
            return self._not_allowed
        raise AttributeError(name)

    def log_message(self, fmt, *args):  # короткий лог без ПДн
        print(f"{self.command} {self.path.split('/')[1:3]} -> {args[1] if len(args) > 1 else ''}", flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"example-stand listening on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

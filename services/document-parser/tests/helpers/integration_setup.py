"""Provision S3 objects and Supabase bankruptcy rows for live API tests."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from app.persistence.s3 import S3Client
from tests.helpers.integration_env import IntegrationEnv

logger = logging.getLogger(__name__)


class IntegrationProvisioner:
    def __init__(self, env: IntegrationEnv) -> None:
        self._env = env
        self._settings = env.settings
        self._s3 = S3Client()
        self._base = self._settings.supabase_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": self._settings.supabase_service_role_key,
            "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.created_bankruptcy = False
        self.bankruptcy_id: UUID | None = (
            UUID(env.bankruptcy_id) if env.bankruptcy_id else None
        )
        self._run_id = env.run_id
        self._case_number = f"ITEST-{env.run_id[:8]}"
        self.form201_s3_key = f"raw-documents/{self._case_number}/form201.pdf"
        self.matrix_s3_key = f"raw-documents/{self._case_number}/creditor_matrix.pdf"
        self.uploaded_keys: list[str] = []
        self.last_form201_document_id: UUID | None = None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: object = None,
    ) -> object:
        url = f"{self._base}/{path.lstrip('/')}"
        with httpx.Client(timeout=60.0) as client:
            response = client.request(
                method, url, headers=self._headers, params=params, json=json
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Supabase {method} {path} failed: {response.status_code} {response.text}"
                )
            if response.status_code == 204 or not response.content:
                return None
            return response.json()

    def ensure_bankruptcy(self) -> UUID:
        if self.bankruptcy_id:
            row = self._request(
                "GET",
                "bankruptcies",
                params={
                    "id": f"eq.{self.bankruptcy_id}",
                    "select": "id,case_number",
                    "limit": "1",
                },
            )
            if row:
                case_number = str(row[0].get("case_number", ""))
                if case_number and not case_number.startswith("ITEST-"):
                    logger.warning(
                        "INTEGRATION_BANKRUPTCY_ID points at non-test case_number=%s — "
                        "use ITEST-* rows or omit to auto-create",
                        case_number,
                    )
                return self.bankruptcy_id
            raise RuntimeError(
                f"INTEGRATION_BANKRUPTCY_ID={self.bankruptcy_id} not found in bankruptcies"
            )

        case_number = self._case_number
        existing = self._request(
            "GET",
            "bankruptcies",
            params={
                "case_number": f"eq.{case_number}",
                "select": "id",
                "limit": "1",
            },
        )
        if existing:
            self.bankruptcy_id = UUID(str(existing[0]["id"]))
            return self.bankruptcy_id

        payload = {
            "case_number": case_number,
            "debtor_name": "Integration Test Debtor",
            "filing_date": date.today().isoformat(),
            "court_district": "Southern District of New York",
            "chapter_type": "11",
            "state": "NY",
        }
        rows = self._request("POST", "bankruptcies", json=payload)
        if not rows:
            raise RuntimeError("Failed to create integration bankruptcy row")
        self.bankruptcy_id = UUID(str(rows[0]["id"]))
        self.created_bankruptcy = True
        logger.info("Created integration bankruptcy %s", self.bankruptcy_id)
        return self.bankruptcy_id

    def upload_pdf(self, s3_key: str, local_path: Path) -> None:
        bucket = self._settings.s3_bucket
        try:
            self._s3._client.upload_file(  # noqa: SLF001 — test provisioning only
                str(local_path),
                bucket,
                s3_key,
                ExtraArgs={"ContentType": "application/pdf"},
            )
        except Exception as exc:
            raise RuntimeError(f"S3 upload failed for {s3_key!r}: {exc}") from exc
        self.uploaded_keys.append(s3_key)
        logger.info("Uploaded %s to s3://%s/%s", local_path.name, bucket, s3_key)

    def upload_pdfs(self, form201_path: Path, matrix_path: Path) -> None:
        self.upload_pdf(self.form201_s3_key, form201_path)
        self.upload_pdf(self.matrix_s3_key, matrix_path)

    def get_document(self, document_id: UUID) -> dict | None:
        rows = self._request(
            "GET",
            "documents",
            params={
                "id": f"eq.{document_id}",
                "select": "id,s3_key,filing_type,parser_version",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return rows[0]

    def teardown(self) -> None:
        bucket = self._settings.s3_bucket
        for key in self.uploaded_keys:
            try:
                self._s3._client.delete_object(Bucket=bucket, Key=key)  # noqa: SLF001
            except Exception as exc:
                logger.warning("S3 delete %s failed: %s", key, exc)

        if self.created_bankruptcy and self.bankruptcy_id:
            try:
                self._request(
                    "DELETE",
                    "bankruptcies",
                    params={"id": f"eq.{self.bankruptcy_id}"},
                )
            except Exception as exc:
                logger.warning("Bankruptcy cleanup failed: %s", exc)


def new_run_id() -> str:
    return uuid4().hex

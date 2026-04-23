from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
import hashlib
import hmac
import json
import time
from typing import Any
from urllib import error, parse, request


class StripeClientError(RuntimeError):
    """Raised when a Stripe API request fails."""


class StripeSignatureError(ValueError):
    """Raised when a Stripe webhook signature cannot be verified."""


@dataclass(slots=True)
class StripeClient:
    secret_key: str
    webhook_secret: str | None = None
    timeout_seconds: int = 10
    api_base_url: str = "https://api.stripe.com/v1"

    def create_checkout_session(
        self,
        *,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_id: str | None,
        customer_email: str,
        user_slug: str,
        plan_key: str,
    ) -> dict[str, Any]:
        payload = {
            "mode": "subscription",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": "true",
            "billing_address_collection": "auto",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "client_reference_id": user_slug,
            "metadata[user_slug]": user_slug,
            "metadata[plan_key]": plan_key,
            "subscription_data[metadata][user_slug]": user_slug,
            "subscription_data[metadata][plan_key]": plan_key,
        }
        if customer_id:
            payload["customer"] = customer_id
        else:
            payload["customer_email"] = customer_email
            payload["customer_creation"] = "always"
        return self._post("/checkout/sessions", payload)

    def create_customer_portal_session(self, *, customer_id: str, return_url: str) -> dict[str, Any]:
        return self._post(
            "/billing_portal/sessions",
            {
                "customer": customer_id,
                "return_url": return_url,
            },
        )

    def verify_webhook(self, payload: bytes, signature_header: str, *, tolerance_seconds: int = 300) -> dict[str, Any]:
        if not self.webhook_secret:
            raise StripeSignatureError("Stripe webhook signing secret is not configured")
        if not signature_header:
            raise StripeSignatureError("Missing Stripe-Signature header")

        timestamp: int | None = None
        signatures: list[str] = []
        for part in signature_header.split(","):
            key, _, value = part.partition("=")
            if key == "t":
                try:
                    timestamp = int(value)
                except ValueError as exc:  # pragma: no cover - defensive parsing branch
                    raise StripeSignatureError("Invalid Stripe-Signature timestamp") from exc
            elif key == "v1" and value:
                signatures.append(value)

        if timestamp is None or not signatures:
            raise StripeSignatureError("Stripe-Signature is missing required fields")
        if abs(int(time.time()) - timestamp) > tolerance_seconds:
            raise StripeSignatureError("Stripe webhook signature has expired")

        signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
            raise StripeSignatureError("Stripe webhook signature verification failed")

        try:
            parsed = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise StripeSignatureError("Stripe webhook payload is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise StripeSignatureError("Stripe webhook payload must be a JSON object")
        return parsed

    def _post(self, path: str, form_payload: dict[str, str]) -> dict[str, Any]:
        body = parse.urlencode(form_payload).encode("utf-8")
        http_request = request.Request(
            url=f"{self.api_base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {self._basic_auth_token()}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            message = self._extract_error_message(payload) or f"Stripe API request failed with status {exc.code}"
            raise StripeClientError(message) from exc
        except error.URLError as exc:
            raise StripeClientError(f"Unable to reach Stripe: {exc.reason}") from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise StripeClientError("Stripe returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise StripeClientError("Stripe returned an unexpected response")
        return data

    def _basic_auth_token(self) -> str:
        return b64encode(f"{self.secret_key}:".encode("utf-8")).decode("ascii")

    @staticmethod
    def _extract_error_message(payload: str) -> str | None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        error_payload = data.get("error")
        if isinstance(error_payload, dict):
            message = error_payload.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return None

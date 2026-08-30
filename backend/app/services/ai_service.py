import json
import os
from urllib.request import Request, urlopen

from .investigation_schema import validate_provider_result


class AIService:
    """Interprets evidence; never owns financial truth or recovery authority."""

    def __init__(self):
        self.provider = os.getenv(
            "AI_PROVIDER",
            "openai" if os.getenv("OPENAI_API_KEY") else "demo"
        ).lower()

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv(
            "OPENAI_BASE_URL",
            "https://api.openai.com/v1"
        ).rstrip("/")

        self.last_meta = self._meta(
            "demo",
            "deterministic",
            True
        )

    def _meta(self, provider, model, fallback_used, reason=None):
        metadata = {
            "provider": provider,
            "model": model,
            "fallback_used": fallback_used
        }

        if reason:
            metadata["fallback_reason"] = reason

        return metadata

    def investigate(self, package):
        if self.provider != "openai" or not self.api_key:
            self.last_meta = self._meta(
                "demo",
                "deterministic",
                True,
                "missing API key or provider disabled"
            )
            return self._demo(package)

        try:
            prompt = (
                "You are BillGuard's evidence-grounded billing investigator. "
                "Return only JSON matching the schema.\n"
                "You may ONLY use facts contained in the supplied evidence package.\n"
                "If a fact is not present, say that it is unavailable.\n"
                "Do not infer financial values that are not present.\n"
                "Do not modify deterministic financial calculations.\n"
                "You must not approve recovery, execute recovery, or bypass governance.\n\n"
                + json.dumps(package, default=str)
            )

            body = {
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Return valid JSON only. "
                            "Financial values are supplied facts, not model outputs."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            }

            request = Request(
                self.base_url + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={
                    "Authorization": "Bearer " + self.api_key,
                    "Content-Type": "application/json",
                },
            )

            with urlopen(request, timeout=20) as response:
                raw = json.loads(response.read())

            content = raw["choices"][0]["message"]["content"]

            result = validate_provider_result(
                json.loads(content),
                package
            )

            self.last_meta = self._meta(
                "openai",
                self.model,
                False
            )

            return result

        except Exception as exc:
            print("OPENAI ERROR:", repr(exc))

            self.last_meta = self._meta(
                "demo",
                "deterministic",
                True,
                f"{type(exc).__name__}: {exc}"
            )

            return self._demo(package)

    def _demo(self, package):
        difference = package["comparison"]["difference"]
        leakage_type = package["case_type"]
        items = package["evidence"]["evidence_items"]

        approved = any(
            item["source"] == "amendment"
            for item in items
        )

        amount = float(difference)

        classification = (
            "CONFIRMED_LEAKAGE"
            if amount > 0 and not approved
            else "LEGITIMATE_EXCEPTION"
            if approved and amount <= 0
            else "INSUFFICIENT_EVIDENCE"
        )

        action = (
            "GENERATE_ADJUSTMENT_INVOICE"
            if classification == "CONFIRMED_LEAKAGE"
            else "STOP"
        )

        return {
            "classification": classification,
            "leakage_type": leakage_type,
            "root_cause": (
                "Deterministic evidence indicates a "
                f"{leakage_type.lower().replace('_', ' ')} variance."
            ),
            "investigation_summary": (
                "Deterministic comparison found the supplied "
                f"difference of ₹{difference}."
            ),
            "reasoning": (
                "All claims are grounded in the supplied evidence package."
            ),
            "recommended_action": action,
            "confidence": (
                0.97
                if classification == "CONFIRMED_LEAKAGE"
                else 0.95
                if approved
                else 0.60
            ),
            "recoverability": (
                0.90
                if classification == "CONFIRMED_LEAKAGE"
                else 0
            ),
            "evidence": items,
        }


__all__ = ["AIService"]
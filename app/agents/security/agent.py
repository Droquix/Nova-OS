import os
import re
import json
from datetime import datetime

PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b"
}

INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "system override",
    "you are now",
    "jailbreak",
    "developer mode",
    "dan mode",
    "bypass constraints"
]

# Audit log path
AUDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "security_audit.log")

def write_audit_log(severity: str, event_type: str, details: str):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "severity": severity,
        "event_type": event_type,
        "details": details
    }
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

class SecurityAgent:
    def __init__(self):
        # Load instructions
        instr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md")
        with open(instr_path, "r", encoding="utf-8") as f:
            self.instructions = f.read()

    def inspect_input(self, text: str) -> dict:
        """
        Validates the input, runs prompt injection checks, scrubs PII, and returns results.
        """
        # 1. Prompt Injection Check
        text_lower = text.lower()
        for keyword in INJECTION_KEYWORDS:
            if keyword in text_lower:
                write_audit_log(
                    severity="CRITICAL",
                    event_type="PROMPT_INJECTION",
                    details=f"Detected injection keyword: '{keyword}'"
                )
                return {
                    "is_safe": False,
                    "scrubbed_text": text,
                    "reason": f"Input violates security guidelines (Potential Injection: '{keyword}')."
                }

        # 2. PII Scrubbing
        scrubbed = text
        redacted_types = []
        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, scrubbed)
            if matches:
                redacted_types.append(pii_type)
                scrubbed = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", scrubbed)
        
        if redacted_types:
            write_audit_log(
                severity="WARNING",
                event_type="PII_REDACTION",
                details=f"Redacted types: {', '.join(redacted_types)}"
            )
        else:
            write_audit_log(
                severity="INFO",
                event_type="INPUT_VERIFIED",
                details="Query parsed successfully and is clean."
            )

        return {
            "is_safe": True,
            "scrubbed_text": scrubbed,
            "reason": None
        }

security_agent = SecurityAgent()

"""
Polar 웹훅 서명 검증 (Standard Webhooks / HMAC)
- POLAR_WEBHOOK_SECRET으로 요청 본문 서명 검증
"""
import hmac
import hashlib
import base64
from typing import Optional

# Standard Webhooks: 헤더 예시 "webhook-signature: t=1234567890,v1=hex_signature"
SIGNATURE_HEADER = "webhook-signature"


def verify_polar_webhook(
    body: bytes,
    headers: dict,
    secret: str,
) -> bool:
    """
    Polar 웹훅 서명 검증 (HMAC-SHA256).
    Standard Webhooks 스펙: t=timestamp,v1=signature
    secret은 Polar 대시보드에서 설정한 Webhook Secret (base64 인코딩된 값일 수 있음).
    """
    if not secret or not body:
        return False
    sig_header = None
    for k, v in headers.items():
        if k.lower() == "webhook-signature":
            sig_header = v
            break
    if not sig_header:
        return False
    # "t=1234567890,v1=abc123..." 파싱
    parts = {}
    for part in sig_header.split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            parts[k.strip()] = v.strip()
    v1 = parts.get("v1")
    if not v1:
        return False
    # 서명 생성: secret으로 body에 대해 HMAC-SHA256
    try:
        secret_bytes = secret.encode("utf-8")
        # 일부 서비스는 secret을 base64로 전달
        if len(secret) % 4 == 0 and not secret.startswith("whsec_"):
            try:
                secret_bytes = base64.b64decode(secret)
            except Exception:
                pass
        computed = hmac.new(
            secret_bytes,
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(computed, v1)
    except Exception:
        return False

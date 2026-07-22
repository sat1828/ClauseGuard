import re
import uuid


def sanitize_filename(filename: str) -> str:
    """Strip path components and dangerous characters. Never trust a client-supplied filename."""
    filename = filename.replace("\\", "/").split("/")[-1]
    filename = re.sub(r"[^A-Za-z0-9._\-]", "_", filename)
    filename = filename.strip(". ")
    return filename[:255] if filename else f"upload_{uuid.uuid4().hex}"


def build_storage_key(user_id: str, document_id: str, filename: str) -> str:
    safe_name = sanitize_filename(filename)
    return f"{user_id}/{document_id}/{safe_name}"

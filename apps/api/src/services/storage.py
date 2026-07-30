import os
from supabase import Client, create_client


def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    return create_client(url, key)


def upload_file(bucket: str, path: str, file_bytes: bytes) -> str:
    supabase = get_supabase_client()
    supabase.storage.from_(bucket).upload(path, file_bytes)
    return supabase.storage.from_(bucket).get_public_url(path)

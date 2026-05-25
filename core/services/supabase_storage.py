import uuid
from supabase import create_client
from django.conf import settings

supabase = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY
)

def upload_image(file):
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY or not settings.SUPABASE_BUCKET:
        raise RuntimeError("Supabase Storage nao esta configurado.")

    # extensão segura
    file_ext = file.name.split('.')[-1].lower()

    # nome único
    file_name = f"{uuid.uuid4()}.{file_ext}"

    # caminho dentro do bucket (opcional usar pasta)
    file_path = file_name  # ou: f"medicines/{file_name}"

    # 🔥 IMPORTANTE: resetar ponteiro do arquivo
    file.seek(0)

    # upload
    response = supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
        file_path,
        file.read(),
        {
            "content-type": file.content_type,
            "x-upsert": "true"  # evita erro se repetir nome
        }
    )

    # 🔍 opcional: debug
    if hasattr(response, "error") and response.error:
        raise RuntimeError(f"Erro no upload Supabase: {response.error}")

    # URL pública (correta)
    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{file_path}"

    return public_url


def upload_prescription(file, user_id):
    """Upload de receita (PDF) para Supabase Storage."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY or not settings.SUPABASE_BUCKET:
        raise RuntimeError("Supabase Storage nao esta configurado.")

    # nome único com user_id para organização
    file_name = f"user_{user_id}_{uuid.uuid4().hex}.pdf"

    # caminho dentro do bucket
    file_path = f"prescriptions/{file_name}"

    # resetar ponteiro do arquivo
    file.seek(0)

    # upload
    response = supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
        file_path,
        file.read(),
        {
            "content-type": "application/pdf",
            "x-upsert": "true"
        }
    )

    # tratamento de erro
    if hasattr(response, "error") and response.error:
        raise RuntimeError(f"Erro no upload de receita Supabase: {response.error}")

    # URL pública
    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{file_path}"

    return file_path

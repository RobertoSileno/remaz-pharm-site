import uuid
from supabase import create_client
from django.conf import settings

supabase = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY
)

def upload_image(file):
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
        print("Erro upload:", response.error)

    # URL pública (correta)
    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{file_path}"

    return public_url
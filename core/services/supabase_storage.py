import uuid
from pathlib import Path

from django.conf import settings
from supabase import create_client


PRESCRIPTION_REFERENCE_PREFIX = 'supabase://'
PRESCRIPTION_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}


def storage_client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise RuntimeError('Supabase Storage nao esta configurado.')
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def upload_image(file):
    if not settings.SUPABASE_BUCKET:
        raise RuntimeError('Bucket de imagens do Supabase nao esta configurado.')

    file_ext = Path(file.name).suffix.lower().lstrip('.')
    file_path = f'{uuid.uuid4()}.{file_ext}'
    file.seek(0)
    response = storage_client().storage.from_(settings.SUPABASE_BUCKET).upload(
        file_path,
        file.read(),
        {
            'content-type': file.content_type,
            'x-upsert': 'true',
        }
    )
    if hasattr(response, 'error') and response.error:
        raise RuntimeError(f'Erro no upload Supabase: {response.error}')

    return f'{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{file_path}'


def upload_prescription(file, user_id):
    """Upload a protected prescription and return its opaque storage reference."""
    bucket = settings.SUPABASE_PRESCRIPTIONS_BUCKET
    if not bucket:
        raise RuntimeError('Bucket privado de receitas nao esta configurado.')

    file_ext = Path(file.name).suffix.lower().lstrip('.')
    if file_ext not in PRESCRIPTION_EXTENSIONS:
        raise ValueError('Formato de receita nao permitido.')

    file_path = f'user_{user_id}_{uuid.uuid4().hex}.{file_ext}'
    file.seek(0)
    response = storage_client().storage.from_(bucket).upload(
        file_path,
        file.read(),
        {
            'content-type': file.content_type,
            'x-upsert': 'false',
        }
    )
    if hasattr(response, 'error') and response.error:
        raise RuntimeError(f'Erro no upload de receita Supabase: {response.error}')

    return f'{PRESCRIPTION_REFERENCE_PREFIX}{bucket}/{file_path}'


def download_prescription(reference):
    """Download a prescription referenced by a new or legacy Supabase value."""
    if reference.startswith(PRESCRIPTION_REFERENCE_PREFIX):
        bucket_and_path = reference[len(PRESCRIPTION_REFERENCE_PREFIX):]
        bucket, separator, file_path = bucket_and_path.partition('/')
        if not separator or not bucket or not file_path:
            raise ValueError('Referencia de receita invalida.')
    else:
        # Old mobile API versions saved object paths in the public image bucket.
        bucket = settings.SUPABASE_BUCKET
        file_path = reference

    if not bucket:
        raise RuntimeError('Bucket da receita nao esta configurado.')

    contents = storage_client().storage.from_(bucket).download(file_path)
    return contents, Path(file_path).name

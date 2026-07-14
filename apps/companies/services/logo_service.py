import os
import uuid

from django.core.files.storage import default_storage

from apps.catalog.domain.validators import validate_product_image
from apps.companies.models import Company


class CompanyLogoService:
    @staticmethod
    def upload(*, company: Company, image_file) -> str:
        validate_product_image(image_file)

        ext = os.path.splitext(image_file.name)[1] or ".jpg"
        filename = f"{company.id}/logo/{uuid.uuid4()}{ext}"
        saved_path = default_storage.save(filename, image_file)
        image_url = default_storage.url(saved_path)

        company.logo_url = image_url
        company.save(update_fields=["logo_url", "updated_at"])
        return image_url

    @staticmethod
    def upload_cover(*, company: Company, image_file) -> str:
        validate_product_image(image_file)

        ext = os.path.splitext(image_file.name)[1] or ".jpg"
        filename = f"{company.id}/cover/{uuid.uuid4()}{ext}"
        saved_path = default_storage.save(filename, image_file)
        image_url = default_storage.url(saved_path)

        company.cover_url = image_url
        company.save(update_fields=["cover_url", "updated_at"])
        return image_url

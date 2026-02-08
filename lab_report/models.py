import uuid
import qrcode
from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from io import BytesIO
from config.settings import SITE_URL
from config.models import BaseModel
from product.models import Product

class LabReport(BaseModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="lab_reports",
        verbose_name=_("product"),
        help_text=_("Select the product for this lab report"),
    )

    batch_number = models.CharField(
        _("batch number"),
        max_length=100,
        help_text=_("Enter the batch number for this lab report"),
    )

    # 🔐 Secure public token for QR access
    public_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    report_file = models.FileField(
        _("report file"),
        upload_to="lab_reports/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf", "docx", "xlsx"]
            )
        ],
        help_text=_("Upload the lab report file"),
    )

    report_date = models.DateField(
        _("report date"),
        help_text=_("Enter the date of the lab report"),
    )

    # 🧾 Auto-generated QR (no manual upload)
    qr_code = models.ImageField(
        _("QR code"),
        upload_to="lab_report_qr_codes/",
        blank=True,
        null=True,
        editable=False,
    )

    class Meta:
        verbose_name = _("lab report")
        verbose_name_plural = _("lab reports")
        ordering = ["-report_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "batch_number"],
                name="unique_batch_per_product",
            )
        ]

    def __str__(self):
        return f"{self.product.name} | Batch {self.batch_number}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.qr_code:
            self._generate_qr_code()

    def _generate_qr_code(self):
        """
        Generates QR code pointing to public lab report URL
        """
        url = f"{SITE_URL}/reports/{self.public_token}/"

        qr = qrcode.make(url)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")

        self.qr_code.save(
            f"{self.batch_number}_qr.png",
            ContentFile(buffer.getvalue()),
            save=False,
        )
        super().save(update_fields=["qr_code"])


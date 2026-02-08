from django.contrib import admin
from .models import LabReport

@admin.register(LabReport)
class LabReportAdmin(admin.ModelAdmin):
    list_display = ('product', 'batch_number', 'report_date', 'created_at')
    search_fields = ('product__name', 'batch_number')
    list_filter = ('report_date', 'created_at')
    ordering = ('-report_date',)
    readonly_fields = ('created_at', 'updated_at', 'public_token', 'qr_code')
    fieldsets = (
        (None, {'fields': ('product', 'batch_number', 'report_file', 'report_date')}),
        ('Auto-generated Fields', {'fields': ('public_token', 'qr_code')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

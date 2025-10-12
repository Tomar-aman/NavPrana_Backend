from django.contrib import admin
from .models import TransactionLog
# Register your models here.

@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('payment_method', 'status')
    # search_fields = ('user__username', 'amount')
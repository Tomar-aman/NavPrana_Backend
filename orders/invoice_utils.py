"""
Invoice PDF generation utility for orders
Converts HTML template to PDF using WeasyPrint
"""

import io
import logging
from datetime import datetime
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
from django.conf import settings


logger = logging.getLogger(__name__)


class InvoiceGenerator:
    """Generate professional PDF invoices from HTML template"""
    
    def __init__(self, order):
        """Initialize invoice generator with order"""
        self.order = order
    
    def generate(self):
        """Generate PDF invoice from HTML template and return as ContentFile"""
        try:
            # Prepare context for template
            context = {
                'order': self.order,
                'user': self.order.user,
                'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://navprana.com',
                'frontend_url': settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else 'https://navprana.com',
            }
            
            # Render HTML template
            html_string = render_to_string('email/send_invoice.html', context)
            
            # Convert HTML to PDF using WeasyPrint
            html_obj = HTML(string=html_string, base_url=settings.BASE_DIR)
            
            # Generate PDF
            pdf_bytes = html_obj.write_pdf()
            
            # Create ContentFile
            filename = f'invoice_{self.order.id}_{datetime.now().strftime("%Y%m%d")}.pdf'
            pdf_file = ContentFile(pdf_bytes, name=filename)
            
            logger.info(f'Invoice generated successfully for order {self.order.id}')
            
            return pdf_file
            
        except Exception as e:
            logger.error(f'Error generating invoice for order {self.order.id}: {str(e)}', exc_info=True)
            raise


def generate_invoice_pdf(order):
    """
    Utility function to generate invoice PDF
    
    Args:
        order: Order instance
        
    Returns:
        ContentFile with PDF data
    """
    generator = InvoiceGenerator(order)
    return generator.generate()

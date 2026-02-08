"""
Invoice PDF generation utility for orders
Converts HTML template to PDF using xhtml2pdf
"""

import io
import logging
from datetime import datetime
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.conf import settings
import os

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
                'seller': settings.SELLER_DETAILS,
                'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://navprana.com',
                'frontend_url': settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else 'https://navprana.com',
            }
            
            # Render HTML template (use invoice_pdf.html instead of send_invoice.html to avoid CSS variables)
            html_string = render_to_string('email/invoice_pdf.html', context)
            
            # Create PDF buffer
            pdf_buffer = io.BytesIO()
            
            # Convert HTML to PDF using xhtml2pdf
            pisa_status = pisa.CreatePDF(
                html_string,
                pdf_buffer,
                encoding='UTF-8',
                link_callback=self.link_callback  # Add this for static files
            )
            
            # Check if PDF generation was successful
            if pisa_status.err:
                logger.error(f'Error generating PDF for order {self.order.id}: {pisa_status.err}')
                raise Exception(f'PDF generation failed: {pisa_status.err}')
            
            # Get PDF data
            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.getvalue()
            
            # Create ContentFile
            filename = f'invoice_{self.order.id}_{datetime.now().strftime("%Y%m%d")}.pdf'
            pdf_file = ContentFile(pdf_bytes, name=filename)
            
            logger.info(f'Invoice generated successfully for order {self.order.id}')
            
            return pdf_file
            
        except Exception as e:
            logger.error(f'Error generating invoice for order {self.order.id}: {str(e)}', exc_info=True)
            raise
    
    def link_callback(self, uri, rel):
        """Convert relative URLs to absolute paths for PDF generation"""
        if uri.startswith('http'):
            return uri
        
        sUrl = settings.STATIC_ROOT
        sUrl = os.path.join(sUrl, uri.replace(settings.STATIC_URL, ""))
        return sUrl


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

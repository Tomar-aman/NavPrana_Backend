"""
Invoice PDF Generation Utility

Generates professional invoices for orders using ReportLab.
"""

import os
from io import BytesIO
from decimal import Decimal
from datetime import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, 
    Spacer, Image, PageBreak
)
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER


def generate_invoice_pdf(order):
    """
    Generate invoice PDF for an order
    
    Args:
        order: Order instance
        
    Returns:
        ContentFile: Generated PDF as ContentFile
    """
    buffer = BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=50,
        bottomMargin=50,
    )
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#555555'),
        spaceAfter=6
    )
    
    # =====================================================
    # HEADER SECTION
    # =====================================================
    
    # Company Logo (if exists)
    logo_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'static', 'logo.png')
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=2*inch, height=0.8*inch)
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 20))
        except:
            pass
    
    # Invoice Title
    elements.append(Paragraph("TAX INVOICE", title_style))
    elements.append(Spacer(1, 20))
    
    # =====================================================
    # COMPANY & CUSTOMER INFO
    # =====================================================
    
    # Company details on left, Invoice details on right
    company_info = [
        [
            Paragraph("<b>NavPrana</b>", heading_style),
            Paragraph(f"<b>Invoice #:</b> INV-{order.id:06d}", normal_style)
        ],
        [
            Paragraph("123 Business Street<br/>City, State 123456<br/>India<br/>Phone: +91 1234567890<br/>Email: support@navprana.com<br/>GSTIN: 29XXXXX1234X1ZX", normal_style),
            Paragraph(f"<b>Order ID:</b> {order.transaction_id or f'ORD-{order.id}'}<br/><b>Date:</b> {order.created_at.strftime('%d %B, %Y')}<br/><b>Payment Status:</b> {order.get_payment_status_display()}", normal_style)
        ]
    ]
    
    info_table = Table(company_info, colWidths=[3.5*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # =====================================================
    # BILLING & SHIPPING ADDRESS
    # =====================================================
    
    elements.append(Paragraph("Bill To / Ship To:", heading_style))
    
    address = order.address
    if address:
        address_text = f"""
        <b>{order.user.get_full_name() or order.user.username}</b><br/>
        {address.address_line1}<br/>
        {address.address_line2 + '<br/>' if address.address_line2 else ''}
        {address.city}, {address.state} - {address.postal_code}<br/>
        Phone: {address.phone_number}<br/>
        Email: {order.user.email}
        """
    else:
        address_text = f"""
        <b>{order.user.get_full_name() or order.user.username}</b><br/>
        Email: {order.user.email}
        """
    
    elements.append(Paragraph(address_text, normal_style))
    elements.append(Spacer(1, 30))
    
    # =====================================================
    # ITEMS TABLE
    # =====================================================
    
    elements.append(Paragraph("Order Items:", heading_style))
    elements.append(Spacer(1, 10))
    
    # Table headers
    items_data = [
        ['#', 'Product', 'Quantity', 'Unit Price', 'Total']
    ]
    
    # Add order items
    for idx, item in enumerate(order.items.all(), 1):
        items_data.append([
            str(idx),
            Paragraph(item.product.name, normal_style),
            str(item.quantity),
            f"₹{item.price:,.2f}",
            f"₹{(item.price * item.quantity):,.2f}"
        ])
    
    # Create items table
    items_table = Table(items_data, colWidths=[0.5*inch, 3*inch, 1*inch, 1.25*inch, 1.25*inch])
    items_table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Body styling
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # # column
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Quantity column
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),  # Price columns
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#4A90E2')),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 20))
    
    # =====================================================
    # PRICE BREAKDOWN
    # =====================================================
    
    # Align price breakdown to the right
    breakdown_data = [
        ['Subtotal:', f"₹{order.total_amount:,.2f}"],
    ]
    
    if order.discount_amount > 0:
        breakdown_data.append([
            f'Discount ({order.coupon.coupon_code if order.coupon else "Applied"}):', 
            f"- ₹{order.discount_amount:,.2f}"
        ])
    
    if order.tax_amount > 0:
        breakdown_data.append([
            f'Tax ({order.tax_percentage}%):', 
            f"₹{order.tax_amount:,.2f}"
        ])
    
    breakdown_data.append([
        Paragraph("<b>Grand Total:</b>", heading_style),
        Paragraph(f"<b>₹{order.final_amount:,.2f}</b>", heading_style)
    ])
    
    # Create breakdown table (aligned right)
    breakdown_table = Table(breakdown_data, colWidths=[4.5*inch, 1.5*inch])
    breakdown_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1a1a1a')),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#4A90E2')),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -2), 6),
    ]))
    
    elements.append(breakdown_table)
    elements.append(Spacer(1, 40))
    
    # =====================================================
    # PAYMENT DETAILS
    # =====================================================
    
    if order.payment_status == 'paid':
        elements.append(Paragraph("Payment Information:", heading_style))
        
        # Get transaction details
        transaction = order.transaction_logs.filter(status='success').first()
        if transaction:
            payment_info = f"""
            <b>Payment Method:</b> {transaction.get_payment_method_display()}<br/>
            <b>Transaction ID:</b> {transaction.transaction_order_id}<br/>
            """
            
            if transaction.gateway_payment_id:
                payment_info += f"<b>Gateway Payment ID:</b> {transaction.gateway_payment_id}<br/>"
            
            if transaction.payment_instrument_type:
                payment_info += f"<b>Payment Type:</b> {transaction.get_payment_instrument_type_display()}<br/>"
            
            if transaction.bank_reference:
                payment_info += f"<b>Bank Reference:</b> {transaction.bank_reference}<br/>"
            
            payment_info += f"<b>Payment Date:</b> {transaction.updated_at.strftime('%d %B, %Y %I:%M %p')}<br/>"
            
            elements.append(Paragraph(payment_info, normal_style))
        else:
            elements.append(Paragraph(f"<b>Status:</b> {order.get_payment_status_display()}", normal_style))
    
    elements.append(Spacer(1, 30))
    
    # =====================================================
    # FOOTER / TERMS
    # =====================================================
    
    elements.append(Paragraph("Terms & Conditions:", heading_style))
    terms_text = """
    1. Goods once sold cannot be returned or exchanged.<br/>
    2. All disputes are subject to jurisdiction only.<br/>
    3. This is a computer-generated invoice and does not require a signature.<br/>
    4. For any queries, please contact our support team.
    """
    elements.append(Paragraph(terms_text, ParagraphStyle(
        'Terms',
        parent=normal_style,
        fontSize=8,
        textColor=colors.HexColor('#888888')
    )))
    
    elements.append(Spacer(1, 30))
    
    # Thank you note
    elements.append(Paragraph(
        "<b>Thank you for your business!</b>", 
        ParagraphStyle('ThankYou', parent=heading_style, alignment=TA_CENTER, fontSize=12)
    ))
    
    # =====================================================
    # BUILD PDF
    # =====================================================
    
    doc.build(elements)
    
    # Get PDF content
    pdf_content = buffer.getvalue()
    buffer.close()
    
    # Create filename
    filename = f"invoice_{order.id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    # Return as ContentFile
    return ContentFile(pdf_content, name=filename)


def regenerate_invoice(order):
    """
    Regenerate invoice for an existing order
    
    Args:
        order: Order instance
        
    Returns:
        bool: True if successful
    """
    try:
        # Delete old invoice if exists
        if order.invoice:
            order.invoice.delete(save=False)
        
        # Generate new invoice
        pdf_file = generate_invoice_pdf(order)
        order.invoice.save(pdf_file.name, pdf_file, save=True)
        
        return True
    except Exception as e:
        print(f"Error regenerating invoice: {str(e)}")
        return False

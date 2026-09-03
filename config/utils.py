from django.conf import settings
from django.template.loader import  get_template
from django.core import mail 
from django.core.mail.backends.smtp import EmailBackend
from api_settings.models import SMTPSettings
# import requests
# from config import settings

def send_mail(subject, email_template_name, context, to_email,**kwargs):
    """
    Send a django.core.mail.EmailMultiAlternatives to to_email.
    """
    mail_setting = SMTPSettings.objects.last()
    if mail_setting:
        host = mail_setting.host
        host_user = mail_setting.username
        host_pass = mail_setting.password
        host_port = mail_setting.port
        from_mail = f"NavPrana <{mail_setting.from_email}>"
    else:
        host = settings.EMAIL_HOST
        host_user = settings.EMAIL_HOST_USER
        host_pass = settings.EMAIL_HOST_PASSWORD
        host_port = settings.EMAIL_PORT
        from_mail = f"NavPrana <{settings.EMAIL_HOST_USER}>"
    mail_obj = EmailBackend( host=host,port=host_port,  password=host_pass, username=host_user,  use_tls=True, timeout=60)
    # Email clients cannot resolve relative URLs, so templates need an absolute
    # base for images and links. Explicit context values still win.
    context = {
        'site_url': settings.SITE_URL,
        'frontend_url': settings.FRONTEND_URL,
        **context,
    }
    email_template = get_template(email_template_name).render(context)
    email_msg = mail.EmailMessage(
            subject=subject,
            body=email_template,
            from_email= from_mail if from_mail else host_user,
            to=[to_email],
           )
    if kwargs.items():
        email_msg.attach(kwargs['filename'], kwargs['file'].read(), 'application/pdf')
    email_msg.content_subtype = 'html'
    mail_obj.send_messages([email_msg])
    mail_obj.close()

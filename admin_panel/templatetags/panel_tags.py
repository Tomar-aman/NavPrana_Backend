"""
Template helpers for the panel.

Icons are inlined from a small local set rather than pulled from an icon font
or a CDN: it keeps the panel working offline and behind a strict CSP, and it
avoids the layout shift a webfont causes on first paint.
"""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..columns import format_currency, format_number


register = template.Library()


# 24×24 stroke paths, drawn on a shared viewBox so every icon lines up.
ICON_PATHS = {
    'dashboard': 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
    'cart': 'M3 3h2l.4 2M7 13h10l3-8H5.4M7 13L5.4 5M7 13l-2 4h13m-8 3a1 1 0 11-2 0 1 1 0 012 0zm8 0a1 1 0 11-2 0 1 1 0 012 0z',
    'basket': 'M5 9l3-6m8 6l-3-6M3 9h18l-1.5 10.5A2 2 0 0117.5 21h-11a2 2 0 01-2-1.5L3 9zm7 4v4m4-4v4',
    'box': 'M21 8l-9-5-9 5m18 0l-9 5m9-5v8l-9 5m0-8L3 8m9 5v8M3 8v8l9 5',
    'layers': 'M12 3l9 5-9 5-9-5 9-5zm9 9l-9 5-9-5m18 4l-9 5-9-5',
    'users': 'M17 20v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2M9.5 8a3.5 3.5 0 11-7 0 3.5 3.5 0 017 0zM22 20v-2a4 4 0 00-3-3.87M16 4.13a4 4 0 010 7.75',
    'user': 'M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M16 7a4 4 0 11-8 0 4 4 0 018 0z',
    'ticket': 'M15 5v2m0 4v2m0 4v2M5 5h14a2 2 0 012 2v3a2 2 0 000 4v3a2 2 0 01-2 2H5a2 2 0 01-2-2v-3a2 2 0 000-4V7a2 2 0 012-2z',
    'star': 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
    'flask': 'M9 3h6M10 3v6L4.5 18a2 2 0 001.7 3h11.6a2 2 0 001.7-3L14 9V3M7.5 14h9',
    'book': 'M4 19.5A2.5 2.5 0 016.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z',
    'image': 'M3 5a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5zm3.5 4.5a1.5 1.5 0 103 0 1.5 1.5 0 00-3 0zM21 15l-5-5L5 21',
    'mail': 'M4 4h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2zm0 2l8 6 8-6',
    'inbox': 'M22 12h-6l-2 3h-4l-2-3H2m20 0l-3.5-7A2 2 0 0016.7 4H7.3a2 2 0 00-1.8 1L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6z',
    'phone': 'M22 16.9v3a2 2 0 01-2.2 2 19.8 19.8 0 01-8.6-3.1 19.5 19.5 0 01-6-6A19.8 19.8 0 012.1 4.2 2 2 0 014.1 2h3a2 2 0 012 1.7c.1 1 .4 1.9.7 2.8a2 2 0 01-.5 2.1L8.1 9.9a16 16 0 006 6l1.3-1.2a2 2 0 012.1-.5c.9.3 1.8.6 2.8.7a2 2 0 011.7 2z',
    'map-pin': 'M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 1118 0zm-6 0a3 3 0 11-6 0 3 3 0 016 0z',
    'help-circle': 'M12 22a10 10 0 100-20 10 10 0 000 20zm-2.4-12.5a2.5 2.5 0 014.9.8c0 1.7-2.5 2.5-2.5 2.5M12 17h.01',
    'link': 'M10 13a5 5 0 007.5.5l3-3a5 5 0 00-7-7l-1.8 1.7M14 11a5 5 0 00-7.5-.5l-3 3a5 5 0 007 7l1.7-1.7',
    'credit-card': 'M2 7a2 2 0 012-2h16a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V7zm0 4h20',
    'settings': 'M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5v.2a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z',
    'shield': 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
    'history': 'M3 3v5h5M3.05 13a9 9 0 105-8.5L3 8m9-1v5l4 2',
    'refresh': 'M23 4v6h-6M1 20v-6h6M3.5 9a9 9 0 0114.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0020.5 15',
    'chart': 'M3 3v18h18M7 15l3-4 3 3 5-7',
    'rupee': 'M6 3h12M6 8h12M15.5 3c0 4-2.5 5-5.5 5h-4l8 13',
    'truck': 'M1 3h15v13H1zM16 8h4l3 3v5h-7V8zM5.5 21a2 2 0 100-4 2 2 0 000 4zm13 0a2 2 0 100-4 2 2 0 000 4z',
    'alert': 'M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L14.7 3.9a2 2 0 00-3.4 0zM12 9v4m0 4h.01',
    'bell': 'M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0',
    'search': 'M11 19a8 8 0 100-16 8 8 0 000 16zm10 2l-4.35-4.35',
    'plus': 'M12 5v14M5 12h14',
    'download': 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3',
    'filter': 'M22 3H2l8 9.5V19l4 2v-8.5L22 3z',
    'chevron-left': 'M15 18l-6-6 6-6',
    'chevron-right': 'M9 18l6-6-6-6',
    'chevron-down': 'M6 9l6 6 6-6',
    'chevron-up': 'M18 15l-6-6-6 6',
    'x': 'M18 6L6 18M6 6l12 12',
    'check': 'M20 6L9 17l-5-5',
    'trash': 'M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14zM10 11v6M14 11v6',
    'edit': 'M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.1 2.1 0 013 3L12 15l-4 1 1-4 9.5-9.5z',
    'eye': 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zm11 3a3 3 0 100-6 3 3 0 000 6z',
    'logout': 'M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9',
    'key': 'M21 2l-2 2m-7.6 7.6a5 5 0 11-7 7 5 5 0 017-7zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3',
    'menu': 'M3 12h18M3 6h18M3 18h18',
    'sun': 'M12 17a5 5 0 100-10 5 5 0 000 10zM12 1v2m0 18v2M4.2 4.2l1.4 1.4m12.8 12.8l1.4 1.4M1 12h2m18 0h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
    'moon': 'M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z',
    'external': 'M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3',
    'file': 'M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9l-7-7zm0 0v7h7',
    'clock': 'M12 22a10 10 0 100-20 10 10 0 000 20zm0-16v6l4 2',
    'inbox-empty': 'M4 4h16v16H4zM4 12h5l2 3h2l2-3h5',
}


@register.simple_tag
def panel_icon(name, size=18, css_class=''):
    """Inline SVG icon. Unknown names fall back to a neutral box."""
    path = ICON_PATHS.get(name) or ICON_PATHS['box']
    return format_html(
        '<svg class="icon {}" width="{}" height="{}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true" focusable="false">'
        '<path d="{}"/></svg>',
        css_class, size, size, path,
    )


@register.filter
def rupees(value):
    """₹ with Indian digit grouping."""
    return format_currency(value)


@register.filter
def thousands(value):
    return format_number(value)


@register.filter
def percent_display(value):
    """Signed one-decimal percentage, or an em dash when there is no baseline."""
    if value is None:
        return '—'
    return f'{value:+.1f}%'


@register.filter
def field_errors_text(field):
    return ' '.join(str(error) for error in field.errors)


@register.simple_tag
def bar_width(value, maximum):
    """Percentage width for a horizontal bar, clamped to 0–100."""
    try:
        value, maximum = float(value or 0), float(maximum or 0)
    except (TypeError, ValueError):
        return '0'
    if maximum <= 0:
        return '0'
    return f'{max(0.0, min(100.0, value / maximum * 100)):.2f}'


@register.filter
def initials(user):
    """One or two letters for the avatar bubble."""
    first = (getattr(user, 'first_name', '') or '').strip()
    last = (getattr(user, 'last_name', '') or '').strip()
    if first or last:
        return (first[:1] + last[:1]).upper() or first[:1].upper()
    email = (getattr(user, 'email', '') or '').strip()
    return email[:1].upper() or '?'


@register.filter
def display_name(user):
    name = f'{getattr(user, "first_name", "")} {getattr(user, "last_name", "")}'.strip()
    return name or getattr(user, 'email', '') or 'Administrator'


@register.simple_tag(takes_context=True)
def active_class(context, key, css_class='is-active'):
    return css_class if context.get('panel_nav_key') == key else ''


@register.simple_tag
def donut_segments(items):
    """Turn ``[{'value': n, ...}]`` into stroke offsets for an SVG donut.

    The maths lives here rather than in the template so the chart markup stays
    readable and the template does no arithmetic.
    """
    total = sum(item['value'] for item in items) or 1
    circumference = 2 * 3.141592653589793 * 42  # r = 42 in the chart's viewBox
    segments, offset = [], 0.0
    for item in items:
        fraction = item['value'] / total
        length = fraction * circumference
        segments.append(
            {
                **item,
                'dash': f'{length:.3f} {circumference - length:.3f}',
                'offset': f'{-offset:.3f}',
                'percent': round(fraction * 100, 1),
            }
        )
        offset += length
    return segments


@register.simple_tag
def sum_values(items):
    return sum(item['value'] for item in items)


@register.filter
def get_item(mapping, key):
    """``dict[key]`` for templates; returns '' when absent."""
    try:
        return mapping.get(key, '')
    except AttributeError:
        return ''

"""
Shipping partners and their public tracking pages.

Adding a courier = one entry here + a migration for the updated
``choices`` on ``Order.courier``.
"""

COURIERS = {
    'delhivery': {
        'label': 'Delhivery',
        'tracking_url': 'https://www.delhivery.com/track/package/{awb}',
    },
    'xpressbees': {
        'label': 'Xpressbees',
        'tracking_url': 'https://www.xpressbees.com/shipment/tracking?awbNo={awb}',
    },
    'amazon_shipping': {
        'label': 'Amazon Shipping',
        'tracking_url': 'https://track.amazon.in/tracking/{awb}',
    },
    'bluedart': {
        'label': 'Blue Dart',
        'tracking_url': 'https://www.bluedart.com/tracking?trackFor=0&trackNo={awb}',
    },
    'dtdc': {
        'label': 'DTDC',
        'tracking_url': 'https://www.dtdc.in/tracking/shipment-tracking.asp?strCnno={awb}',
    },
    'ecom_express': {
        'label': 'Ecom Express',
        'tracking_url': 'https://ecomexpress.in/tracking/?awb_field={awb}',
    },
    'shadowfax': {
        'label': 'Shadowfax',
        'tracking_url': 'https://tracker.shadowfax.in/#/tracking/{awb}',
    },
    'india_post': {
        'label': 'India Post',
        'tracking_url': 'https://www.indiapost.gov.in/_layouts/15/DOP.Portal.Tracking/TrackConsignment.aspx?ID={awb}',
    },
}

# Ready for ``models.CharField(choices=...)``
COURIER_CHOICES = tuple((code, meta['label']) for code, meta in COURIERS.items())


def get_courier(code):
    """Registry entry for ``code``, or an empty placeholder if unknown."""
    return COURIERS.get(code, {'label': '', 'tracking_url': ''})


def build_tracking_url(code, awb):
    """Public tracking URL for an AWB, or '' when either piece is missing."""
    template = get_courier(code).get('tracking_url', '')
    if not template or not awb:
        return ''
    return template.format(awb=awb.strip())

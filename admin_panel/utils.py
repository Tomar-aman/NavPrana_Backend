"""Small helpers shared by the panel views."""

from django.http import QueryDict
from django.utils.http import url_has_allowed_host_and_scheme


#: Page sizes a user may pick from. Anything else falls back to the resource
#: default, so ``?per_page=1000000`` cannot be used to exhaust memory.
PAGE_SIZES = (25, 50, 100)


def merged_query(params, **overrides) -> str:
    """``params`` re-encoded with ``overrides`` applied.

    A value of ``None`` drops the key. Always returns a leading ``?`` (or an
    empty string), so templates can use it directly in an ``href``.
    """
    query = QueryDict(mutable=True)
    query.update({key: value for key, value in params.items() if value not in (None, '')})

    for key, value in overrides.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value

    encoded = query.urlencode()
    return f'?{encoded}' if encoded else ''


def drop_params(params, keys) -> str:
    """Re-encode ``params`` without ``keys``."""
    return merged_query(params, **{key: None for key in keys})


def resolve_page_size(params, default: int) -> int:
    raw = params.get('per_page')
    try:
        candidate = int(raw)
    except (TypeError, ValueError):
        return default
    return candidate if candidate in PAGE_SIZES else default


def safe_redirect_target(request, fallback: str) -> str:
    """Validate a ``?next=`` value before redirecting to it.

    Without this check an attacker could hand a staff member a panel link that
    bounces them to an external look-alike after a successful action.
    """
    candidate = request.POST.get('next') or request.GET.get('next') or ''
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def csv_value(cell) -> str:
    """Flatten a rendered cell for a spreadsheet column."""
    if cell.is_empty:
        return ''
    if cell.kind in ('image', 'file'):
        return cell.url or ''
    # Prefer the untruncated text when the display value was shortened.
    return cell.title or cell.display

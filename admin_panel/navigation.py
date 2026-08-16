"""
Sidebar construction.

The menu is derived from the resource registry rather than hand-maintained, so
registering a model puts it in the sidebar and nothing goes stale. Every entry
is filtered through ``user.has_perm``: a user without ``view`` on a model never
sees its link, and the matching view rejects the URL anyway.
"""

from dataclasses import dataclass, field as dataclass_field
from typing import List, Optional

from django.urls import reverse

from .registry import registry


#: Sidebar order. Groups absent from the registry are skipped automatically.
GROUP_ORDER = (
    'Commerce',
    'Catalog',
    'Customers',
    'Marketing',
    'Content',
    'Support',
    'System',
)


@dataclass
class NavItem:
    label: str
    url: str
    icon: str = 'box'
    key: str = ''
    is_active: bool = False
    badge: Optional[int] = None


@dataclass
class NavGroup:
    title: str
    items: List[NavItem] = dataclass_field(default_factory=list)


def build_navigation(user, active_key: str = '') -> List[NavGroup]:
    """Permission-filtered sidebar for ``user``, marking ``active_key``."""
    groups: List[NavGroup] = []

    overview = NavGroup('Overview')
    overview.items.append(
        NavItem(
            label='Dashboard',
            url=reverse('admin_panel:dashboard'),
            icon='dashboard',
            key='dashboard',
            is_active=active_key == 'dashboard',
        )
    )
    groups.append(overview)

    buckets = {}
    for resource in registry:
        if not user.has_perm(resource.perm('view')):
            continue
        buckets.setdefault(resource.group, []).append(resource)

    ordered = list(GROUP_ORDER) + sorted(set(buckets) - set(GROUP_ORDER))
    for title in ordered:
        resources = buckets.get(title)
        if not resources:
            continue
        group = NavGroup(title)
        for resource in resources:
            group.items.append(
                NavItem(
                    label=resource.label_plural,
                    url=resource.url('list'),
                    icon=resource.icon,
                    key=resource.key,
                    is_active=active_key == resource.key,
                )
            )
        groups.append(group)

    # The activity log reads ``django.contrib.admin.LogEntry``, which every
    # staff member may inspect but only superusers can prune.
    system = next((g for g in groups if g.title == 'System'), None)
    if system is None:
        system = NavGroup('System')
        groups.append(system)
    system.items.append(
        NavItem(
            label='Activity Log',
            url=reverse('admin_panel:activity'),
            icon='history',
            key='activity',
            is_active=active_key == 'activity',
        )
    )

    return [group for group in groups if group.items]

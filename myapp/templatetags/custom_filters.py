from django import template
from urllib.parse import quote

register = template.Library()

@register.filter
def urlencode(value):
    return quote(str(value))

@register.filter
def split(value, delimiter):
    """
    Splits the string by the given delimiter and returns a list.
    Usage: value|split:","
    """
    if not isinstance(value, str):
        value = str(value)
    return value.split(delimiter)

@register.filter
def filter_by_type(queryset, doc_type):
    """
    Filters a queryset by document_type and returns the count.
    Usage: queryset|filter_by_type:"PDF"
    """
    if queryset is None:
        return 0
    return queryset.filter(document_type=doc_type).count()

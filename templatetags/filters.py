from django import template
register = template.Library()

# @register.filter
# def get_item(dictionary, key):
#     return dictionary.get(key)


# @register.filter
# def index(sequence, idx):
#     try:
#         return sequence[idx]
#     except (IndexError, TypeError):
#         return None

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def index(sequence, position):
    try:
        return sequence[position]
    except (IndexError, TypeError):
        return None

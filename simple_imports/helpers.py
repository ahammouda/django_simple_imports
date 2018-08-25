#
# def get_modifier(filter_value):
#     if isinstance(filter_value,str):
#         return '__iexact'
#     return ''
#
#
# def update_kvs(kvs):
#     new_dict = {}
#     for k,v in kvs.items():
#         k = "{}{}".format(k, get_modifier(v))   #: TODO: Eventually grab this from a type dict
#         new_dict[k] = v
#     return new_dict
from typing import *
from datetime import date,datetime
from dateutil.parser import parse as parsedt
from decimal import Decimal
from django.db.models import Model

def get_typed_value(datatype,value):

    if datatype == date:
        return parsedt(value).date()
    if datatype == datetime:
        return parsedt(value)
    if datatype == Decimal:
        return Decimal(value)
    if datatype == float:
        return float(value)

    return value #: Returns string or object content as is

from django.db.models import Model,ManyToManyField
from django.db.models.fields.related_descriptors import ManyToManyDescriptor

def is_many_to_many(field: str, model: Model):
    if isinstance(getattr(model,field), ManyToManyField) or \
            isinstance(getattr(model,field),ManyToManyDescriptor):
        return True
    else:
        return False



#: Note right now this is not being used anywhere, but
#: it is an interesting aside on the use of many to many fields
def filter_objects_exactly_by_m2m(m2m_objects: List[Model], reverse_attribute)->List[Model]:
    """
    :param m2m_objects: A list of objects to which are related to another object, by it's `reverse_attribute`
    :param reverse_attribute:
    e.g.  Image.tag --m2m--> Tag // image = reverse_attribute of Tag, and m2m_objects would be all the tags

    :return: A list of all the m2m _from_ objects associated by the m2m_objects ('to' objects)
    """
    #: TODO: What were you trying to say with this?
    # This works only when the associated list of the m2m field is a unique superset of other objects
    # If you want to filter the fields that ONLY have the m2m_objects input (and no more), this will fail
    sets = []
    reverse_attribute = f'{reverse_attribute}_set'
    for o in m2m_objects:
        reverse_manager = getattr(o,reverse_attribute, None)

        if not reverse_manager:
            raise RuntimeError(f'Attribute {reverse_attribute} is not available on these m2m objects.')

        sets.append(
            set([io for io in reverse_manager.all()])
        )
    return list(set.intersection(sets))
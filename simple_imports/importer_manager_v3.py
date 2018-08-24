from collections import defaultdict
import functools
from typing import *
from copy import deepcopy

from django.db.models import Model
from django.db.models.fields.related_descriptors import ManyToManyDescriptor
from django.db.models import Q,QuerySet,Model,ManyToManyField

from . import lookup_helpers

from .model_importer import ModelImporter

class RecordData(object):
    """Stores queried object from the database and associated query, and helper metadata (possible object)
    object associated with the query isn't present in the system.
    """
    def __init__(self, query: Q = None, available: bool = False):
        self.query: Q = query
        self.available: bool = available
        self.object: Model = None


class ImporterManager(object):
    """
    (Docstring from v2)
    An importer manager's only job is to get related objects or flags if the objects don't exist.
    (it is strictly lazy as in it only collects objects at the end) <- this may have some limitations.
              --> Try to architect s.t. you can swap such a manager out.

    The add_kv() function transitions a state machine, and increments the main data structure (self.kvs)

    self.kvs is used to populated self.object_row_map which is the data structure accessed from outside this model


    Some invariants:
    *  A row will have more than 1 dictionary entry, if and only if, an importer depending on its associated manager
       depends on it through a m2m relationship

    Termination conditions (of external algorithm in system_importer):
    *  Every row/col in the kvs table has a corresponding value associated with every field in:
              - self.importer.required_fields
              - self.importer.dependent_imports
    """

    #: TODO: This is repeated in the SystemImporter class, and used in a way you want to depricate
    @staticmethod
    def is_many_to_many(field: str, model: Model):
        if isinstance(getattr(model,field), ManyToManyField) or \
                isinstance(getattr(model,field),ManyToManyDescriptor):
            return True
        else:
            return False

    def __init__(self, importer: ModelImporter=None, create: bool=False, is_m2m: bool=False):
        #: How this manager is used outside itself depends less on the importer and hence the model, but more on
        #: its reverse relations
        self.importer = importer

        self.create = create

        self.kvs = defaultdict(list)
        self.objs: QuerySet = None

        self.is_m2m = is_m2m

        self.m2m_field: DefaultDict[str,bool] = defaultdict(bool)
        for key in self.importer.dependent_imports.keys():
            if self.is_many_to_many(key, self.importer.model):
                self.m2m_field[key] = True

        #: (Maybe log every row, indicating if there is no error)
        #: If a given row as an error, it will get logged here: error types:
        #:       * validation error:{missing-field,typing issue}
        #:       * object with given parameters not found
        self.errors: Dict[int,Dict[str,str]] = {} #: Typing subject to change

        #self.object_row_map: Dict[int,List[Dict]] = {} #: Maps row to one or more elements of RecordData
        self.object_row_map: Dict[int,List[RecordData]] = defaultdict(list) #: Maps row to one or more elements of RecordData

    # def finished_required_fields(self):
    #     ready = True
    #
    #     if self.importer.required_fields:
    #         for rf in self.importer.required_fields:
    #             if rf not in self.kvs[self.current_row][self.current_col].keys():
    #                 ready=False
    #     return ready
    #
    # def update_kvs_straight(self, field_name, value: Any):
    #     """
    #     :param field_name:
    #     :param value:
    #     """
    #     self.current_row = 0 # STUB <-- specified outside of here
    #     self.current_col = 0 # STUB <-- specified outside of here
    #     self.kvs[self.current_row][self.current_col].update({field_name:value})
    #
    #     if self.is_m2m and self.finished_required_fields():
    #         self.current_col += 1
    #     elif self.finished_required_fields():
    #         self.current_row += 1

    def update_kvs(self, field_name: str, value, row: int, col: int=0):
        """
        Leaky abstraction -- definitely depends on some knowledge of how this is invoked (row/col specification)

        Previous approach - state machine approach seemed you could depend only on the ModelImporter input,
        and knowledge over whether this is a m2m object

        Other approaches????
        """
        typed_value = lookup_helpers.get_typed_value(
            self.importer.field_types[field_name],value
        )

        # For many to many filters
        if self.m2m_field[field_name] and not self.create:
            #: TODO: This branch needs some testing
            #:       --> e.g. need an image with multiple tags
            field_name = f'{field_name}__in'

        #: Edge case for m2m_field
        if self.m2m_field[field_name] and type(typed_value) != list:
            typed_value = [typed_value]

        #: self.kvs is either being populated by object values referenced in a m2m relationship or NOT
        #: If NOT => col == 0 always, and after the first append, you'll simply be updating self.kvs[row][0]
        if self.kvs[row] and col < len(self.kvs[row]):
            self.kvs[row][col].update({field_name: typed_value})
        else:
            self.kvs[row].append({field_name: typed_value})

    def get_latest_row(self):
        #: This is incremented externally, because it is from that perspective that it will be known whether
        #: one is managing something that is many to many or not
        return max(self.kvs.keys())

    def get_available_rows(self) -> Dict[int,List[RecordData]]:
        """Find all available objects given the key/values that have been provided thus far.

        Populates `self.object_row_map`
        This method is currently the only one actually making trips to the database

        :returns: {row <-> List[RecordData],...} pairs.  This returned dictionary can be queried directly or through
                  the methods outlined below.
        """
        if not self.kvs:
            return None

        if len(self.object_row_map.keys()) > 0:
            raise RuntimeError('This Method has already been called.  Retreive data through it\'s getter methods')

        #: Building up query object for filtering, and object_row_map to map the results to each clause in the query
        query = Q(**self.kvs[0][0])
        self.object_row_map[0].append(RecordData(query=Q(**self.kvs[0][0])))

        #: Store a query for each column in the list of kvs
        for kv in self.kvs[0][1:]:
            query |= Q(**kv)
            self.object_row_map[0].append(RecordData(query=Q(**kv)))

        for row in range(1,self.get_latest_row()):
            for kv in self.kvs[row]: #: For each column
                query |= Q(**kv)
                self.object_row_map[row].append(RecordData(query=Q(**kv)))

        self.objs = self.importer.model.objects.filter(query)

        #: With self.objs, go back through and collect each objects
        for row,record_list in self.object_row_map.items():

            for col,rec in enumerate(record_list):

                obj = self.objs.filter(rec.query).first()
                self.object_row_map[row][col].available = True if obj else False
                self.object_row_map[row][col].object = obj

        return self.object_row_map

    def get_objects_from_rows(self) -> List[Model]:
        """
        This is really going to be for the 'root' object (i.e. the object actually getting imported).

        Therefore if a set of ImporterManagers are being used for both dependent data and the object that's being
        created, this function will _only_ be called for the object being created
        TODO: Maybe put this logic outside of ImporterManager then
        """
        if not self.create:
            raise ValueError('This should only be called for model managers associated with new objects, '
                             'not dependent objects')

        #: Check for m2m fields first:
        m2m_keys = []

        for k,v in self.kvs[0][0].items():
            if self.m2m_field[k]:
                m2m_keys.append(k)
        m2m_objects = defaultdict(dict)

        objects = []
        #: Collect objects; if any have many to many fields, document them
        for row in range( self.get_latest_row() + 1 ):

            #: If there are any many to many fields, store each list object, and remove them from the main object
            #:    for an initial create.
            for k in m2m_keys:

                m2m_objects[row]['objs'] = defaultdict(dict)

                m2m_objects[row]['objs'][k] = deepcopy(self.kvs[row][0][k])
                del self.kvs[row][0][k]

            if m2m_keys:
                m2m_objects[row]['query'] = Q(**self.kvs[row][0])

            objects.append(
                self.importer.model(**self.kvs[row][0])
            )

        if m2m_keys:
            self.importer.model.objects.bulk_create(objects)
            queries = [m2m_objects[row]['query'] for row in m2m_objects.keys()]

            query = queries.pop()
            for q in queries:
                query |= q

            objects = []
            pk_objects = self.importer.model.objects.filter(query)

            for row in m2m_objects.keys():

                obj = pk_objects.filter(m2m_objects[row]['query']).first()
                for k in m2m_keys:
                    #: USER BE WARNED:  Each one of these operations requires a trip to the database
                    getattr(obj,k).set(m2m_objects[row]['objs'][k])

                objects.append(
                    obj
                )

        #: Returns either, a list of uncreated objects, or a list of created objects, with m2m attached and saved
        return objects

    def get_objs_and_meta(self, row: int) -> List[RecordData]:
        """ Queries `self.object_row_map` by row
        :param row:
        :return: a list of records for the queried row
        """
        return self.object_row_map[row]

    def get_object_or_list(self, row: int) -> List[Model] or Model:
        """Helper method for most cases that don't want to unpack data returned by `get_objs_and_meta`
        :param row:
        :return: single object if only one filtered, otherwise a list of the objects collected from the given row
        """
        objs = [e.object for e in self.object_row_map[row] if e.available]
        return objs if len(objs) > 1 else objs[0]
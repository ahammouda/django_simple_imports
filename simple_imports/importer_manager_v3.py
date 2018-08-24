from collections import defaultdict

from typing import *
from copy import deepcopy

from django.db.models import Model
from django.db.models import Q,QuerySet,Model

from . import helpers

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
    """Stores key,value pairs needed to get or create objects from/in a relational database in `self.kvs`, then
    If self.create is False:
          populates `self.object_row_map` with data dependent on what is retrieved, and assuming
    If self.create is True:
          returns objects initialized with self.kvs data to be inserted into a relation database

    -Some invariants-
      *  A row will have more than 1 dictionary entry, if and only if, an importer depending on its associated manager
         depends on it through a m2m relationship and self.is_m2m

      *  not (self.is_m2m && self.create)

      *  If `self.object_row_map` is non-empty ==>
              Every row/col in the kvs table has a corresponding value associated with every field in:
               - self.importer.required_fields
               - self.importer.dependent_imports
         See `self.update_kvs` for TODO on this count
    """

    def __init__(self, importer: ModelImporter=None, create: bool=False, is_m2m: bool=False):
        #: How this manager is used outside itself depends less on the importer and hence the model, but more on
        #: its reverse relations
        self.importer = importer

        self.create = create

        self.kvs = defaultdict(list)
        self.objects: QuerySet = None

        #: If this is True for a field, then this.importer.model will be retrieved filtering on its m2m field
        #:  with an __in=[value_0,value_1,...] (>>)
        self.m2m_field: DefaultDict[str,bool] = defaultdict(bool)
        for key in self.importer.dependent_imports.keys():
            if helpers.is_many_to_many(key, self.importer.model):
                self.m2m_field[key] = True

                if self.create:
                    raise RuntimeError('Cannot currently create objects that have a m2m dependency.')

        self.is_m2m = is_m2m #: Isn't used internally <-- how about externally??

        #: (Maybe log every row, indicating if there is no error)
        #: If a given row as an error, it will get logged here: error types:
        #:       * validation error:{missing-field,typing issue}
        #:       * object with given parameters not found
        self.errors: Dict[int,Dict[str,str]] = {} #: Typing subject to change

        #: Maps row to one or more elements of RecordData
        self.object_row_map: Dict[int,List[RecordData]] = defaultdict(list)

    def update_kvs(self, field_name: str, value, row: int, col: int=0):
        """N.B: - This is definitely a leaky abstraction -- this method represents the way in which this class
        is driven after initialization.  For each row of a read csv file

        REQUIRES:
        * external invocation of this method should populate all of the
          `self.importer.required_fields` and `self.importer.dependent_imports`
          before `self.get_available_rows` is called, or any of the data getter methods queried

        TODO: This requirement isn't yet enforced
        """
        typed_value = helpers.get_typed_value(
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

        if self.object_row_map:
            raise RuntimeError('This Method has already been called.  Retreive data through it\'s getter methods')

        #: Build up cumulative query for hitting the database once, and track each records cumulative contribution
        #: to the overall query
        query = None
        for row in range(self.get_latest_row() + 1):
            for col, kv in enumerate(self.kvs[row]):

                if query is None:
                    query = Q(**kv)
                else:
                    query |= Q(**kv)

                self.object_row_map[row].append(RecordData(query=Q(**kv)))

        self.objects = self.importer.model.objects.filter(query)

        #: With self.objects, go back through and collect each objects
        for row,record_list in self.object_row_map.items():

            for col,rec in enumerate(record_list):

                obj = self.objects.filter(rec.query).first()
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
        :return: * single object if only one filtered, otherwise a list of the objects collected from the given row
             OR  * empty list if there are now objects found with the existing row
        """
        objs = [e.object for e in self.object_row_map[row] if e.available]
        return objs if len(objs) > 1 or not objs else objs[0]
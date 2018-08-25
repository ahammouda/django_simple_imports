from typing import Dict, List, Tuple
from collections import defaultdict

from django.db import models
from django.db.models.fields.related_descriptors import ManyToManyDescriptor

from dotdict import DotDict

from .sorter import Sorter
from .model_importer import ModelImporter
from .importer_manager import ImporterManager

import pdb

#: TODO: Document the necessity of these being differently
M2M_DELIMITER = ';'
# I think this is unnecesary, if you want multiple fields to be specifiable,
# you need to put them in separate chuncks of 'a;a;a;a , b;b;b;b'
M2M_FIELD_DELIMITER = '|'
DEFAULT_DELIMITER = ','

class SystemImporter:

    def __init__(self, importers: List[ModelImporter], csvfilepath: str):
        """

        :param importers:   This must include all necessary importers needed for all dependencies to be met
                            (i.e. Must be the transitive closure of necessary dependencies)
        :param csvfilepath:
        """
        self.importers = importers

        #: Initialize dependency structure of imports
        self.graph = []
        """:type:list[DotDict]"""

        self.sorted_vertices: List[DotDict] = []

        self._construct_adjacency_graph()
        self._topologically_sort_graph()

        #: Initialize csv reading state machines (managers)
        self.managers = []
        """:type:list[ImportManager]"""

        self.importers_to_manager: Dict[ModelImporter,ImporterManager] = {}
        """:type:dict[ModelImporter:ImportManager]"""

        self.importers_to_verticies: Dict[ModelImporter,DotDict[str, object]] = {}

        self.create_model = None
        """:type:models.Model"""

        self._initialize_managers()

        #: Setup csv input fields and mappings back to managers
        self.csv_import_format = ""
        """:type:str"""

        self.location_to_importer = {}
        """:type:dict[int,ModelImporter]"""

        self.location_to_csv_field = {}
        """:type:dict[int,str]"""

        self.csv_import_format = self._get_import_fields()

        self.new_objects: List[models.Model] = []


        self.candidate_objects: List[models.Model] = []

        self.lines = []
        """:list[str]"""

        if csvfilepath:
            self.file_path = csvfilepath

            with open(self.file_path, 'r') as f:
                self.lines = f.readlines()

        else:
            raise RuntimeError("Must provide a file with data in the format: {}".format(self.csv_import_format))


    def _construct_adjacency_graph(self):

        for i,vertex in enumerate(self.importers):
            self.graph.append(DotDict({
                'id': i,
                'Adj': [],
                'p': None,
                'color': "WHITE",
                'd': 0,
                'f': 0,
                'importer': vertex,
                #: Discloses whether this vertex in the graph is m2m to any others (will be set by vertices with
                #: dependent imports back to it)
                'is_m2m': False
            }))

        #: Once this for loop is complete, circle back and add to the Adjacencies
        for vertex in self.graph:

            #: Should return a dictionary
            neighbors = vertex.importer.dependent_imports

            if not neighbors:
                continue

            for field,importer in neighbors.items(): #: This is deterministic and therefore the results are.
                inner_vertex = next((x for x in self.graph if x.importer==importer),None)
                assert inner_vertex is not None
                vertex.Adj.append(self.graph[inner_vertex.id])

                #: Tell the vertex that it is many-2-many with respect to itself
                #: TODO: use this from the helpers file if it's still necesary
                if self.is_many_to_many(field,vertex.importer.model):
                    self.graph[inner_vertex.id].is_m2m = True

    def _topologically_sort_graph(self):
        sorter = Sorter()
        sorter.dfs(self.graph)
        self.sorted_vertices = sorter.sorted_vertices

    def _initialize_managers(self):
        for i,v in enumerate(self.sorted_vertices):
            #: N.B: This Assume that only one model type is being created for each import (everything else defines getters
            #:      for FK fields or fields of the new object)
            if i == len(self.sorted_vertices)-1:
                create = True
            else:
                create = False

            self.managers.append(
                ImporterManager(v.importer,create=create)
            )
            self.importers_to_manager[v.importer] = self.managers[i]

            self.importers_to_verticies[v.importer] = v

        #: TODO: Check whether any dependent_importer fields in self.sorted_vertices[-1].importer are m2m, and
        #:       throw an error if they are
        self.create_model = self.sorted_vertices[-1].importer.model

    def _get_import_fields(self):
        fields = ""
        count = 0; #: TODO: Move to enumerated field
        for v in self.sorted_vertices:
            if v.importer.required_fields is None:
                continue

            for field in v.importer.required_fields:

                self.location_to_importer[count] = v.importer

                self.location_to_csv_field[count] = field

                fields = f'{fields}{field},'
                count+=1

        return fields

    def is_many_to_many(self, field: str, model: models.Model):
        if isinstance(getattr(model,field),models.ManyToManyField) or \
                isinstance(getattr(model,field),ManyToManyDescriptor):
            return True
        else:
            return False

    def import_data(self):
        #: TODO: Make it so you don't need to assume there's no header
        # Loop 1: Extract data from file, and prep importer managers to pull related data from disk
        for row,line in enumerate(self.lines):

            fields = line.split(DEFAULT_DELIMITER)

            #: Iterate accross row of csv file
            for i,value in enumerate(fields):
                _field = self.location_to_csv_field[i]
                _importer = self.location_to_importer[i]

                #region Handle Parsing out M2M relationships if present
                if self.importers_to_verticies[_importer].is_m2m:

                    m2m_refs = value.split(M2M_DELIMITER)
                    for col,ref in enumerate(m2m_refs):
                        self.importers_to_manager[_importer].update_kvs( #: Added
                            field_name=_field, value=ref, row=row, col=col
                        )

                #endregion
                else:
                    self.importers_to_manager[_importer].update_kvs(
                        _field, value.replace('\n',''), row=row
                    )

        #: TODO: Maybe combine loop 2 and 3 <-- there separation is maybe only useful for readability
        # Loop 2: Get all the related data from for the leaf nodes of the dependency tree
        for i,vertex in enumerate(self.sorted_vertices):

            if vertex.importer.dependent_imports is not None:
                break;

            else:
                self.importers_to_manager[
                    vertex.importer
                ].get_available_rows()

        # Loop 3: Work your way up the dependency tree
        for i,vertex in enumerate(self.sorted_vertices):

            if vertex.importer.dependent_imports is None:
                continue

            for fname, _importer in vertex.importer.dependent_imports.items():

                _manager = self.importers_to_manager[_importer]

                for row in range(_manager.get_latest_row() + 1): #range is exclusive of upper bound
                    #: Get objects, or log an error (TODO - check for errors as below - maybe put the task in a function)
                    objects = self.importers_to_manager[_importer].get_objs(row=row)
                    if len(objects)>1:
                        self.importers_to_manager[vertex.importer].update_kvs(
                            field_name=fname, value=objects, row=row
                        )
                    else:
                        self.importers_to_manager[vertex.importer].update_kvs(
                            field_name=fname, value=objects[0], row=row
                        )

            #: Now that your dependencies should be satisfied, get data from disk to enable the next row
            if not self.importers_to_manager[ vertex.importer ].create:
                self.importers_to_manager[ vertex.importer ].get_available_rows()

    def store_data(self):
        self.create_model.objects.bulk_create(self.new_objects)

    def get_new_objects(self):
        self.importers_to_manager[ self.sorted_vertices[-1].importer ].get_objects_from_rows()
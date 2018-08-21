import random,string

from django.test import TestCase
from django.contrib.auth.models import User

from ..simple_imports.importer_manager_v2 import ImporterManager
from ..tests_app.importers import UserImporter


class TestImporterManager(TestCase):

    def setUp(self):
        #: The user model is used in these examples for no particular reason other than, it has no dependencies
        self.n_objs = 4

        #: Create tests for a manager that returns objects related by a foreignkey
        self.usernames = []
        for i in range(self.n_objs):
            uname = ''.join(random.choices(population=string.ascii_uppercase+string.ascii_uppercase,k=4))
            User.objects.create(
                username = uname, email=f'{uname}@gmail.com', first_name = 'Foo', last_name = 'manchu'
            )
            self.usernames.append(uname)

    def test_all_objects_returned(self):
        manager = ImporterManager(importer=UserImporter())
        for name in self.usernames:
            manager.add_kv(field_name='username',value=name)
            manager.increment_row()

        manager.get_available_rows()
        for i in range(self.n_objs):
            objs = manager.get_objs(i) #: Returns a list of objects only if manytomany
            self.assertEqual(objs[0]['available'], True)
            self.assertIsNotNone(objs[0]['obj'])
            self.assertIsInstance(objs[0]['obj'],User)
            self.assertIsNotNone(objs[0]['query'])

        del manager

    def test_many_to_many_structure(self):
        #: Note, this follows the same pattern as test_all_objects_returned(), except the row is incemented 2xs
        #: this simulates the way the manager will be invoked in the case of ManyToMany relationships
        manager = ImporterManager(importer=UserImporter())

        manager.add_kv(field_name='username',value=self.usernames[0])
        manager.add_kv(field_name='username',value=self.usernames[1])
        manager.increment_row()

        manager.add_kv(field_name='username',value=self.usernames[2])
        manager.add_kv(field_name='username',value=self.usernames[3])
        manager.increment_row()

        manager.get_available_rows()

        for i in range(2):
            objs = manager.get_objs(i)
            for j in range(2):
                self.assertEqual(objs[j]['available'], True)
                self.assertIsNotNone(objs[j]['obj'])
                self.assertIsInstance(objs[j]['obj'], User)
                self.assertIsNotNone(objs[j]['query'])

        del manager

    def test_partial_objects_returned(self):
        missing_index = 2
        User.objects.filter(username=self.usernames[missing_index]).delete()

        manager = ImporterManager(importer=UserImporter())
        for name in self.usernames:
            manager.add_kv(field_name='username',value=name)
            #: For every set of fields, increment the row
            manager.increment_row()

        manager.get_available_rows()
        for i in range(self.n_objs):
            objs = manager.get_objs(i) #: Returns a list of objects only if manytomany
            if i==missing_index:
                self.assertEqual(objs[0]['available'], False)
                self.assertIsNone(objs[0]['obj'])
                self.assertIsNotNone(objs[0]['query'])
                continue

            self.assertEqual(objs[0]['available'], True)
            self.assertIsNotNone(objs[0]['obj'])
            self.assertIsInstance(objs[0]['obj'],User)
            self.assertIsNotNone(objs[0]['query'])

        del manager

    def test_multiple_fields_for_m2m(self):
        #: TODO: Given some standard for reading in multiple fields for a m2m object
        pass

    def test_validate_logs_error(self):
        pass

    def test_(self):
        pass
import random,string

from typing import *

from django.test import TestCase
from .factory import create_multiple_users

from ..simple_imports.importer_manager_v3 import ImporterManager,RecordData

from django.contrib.auth.models import User
from ..tests_app.models import UserProfile,Company
from ..tests_app.importers import UserImporter,UserProfileImporter,CompanyImporter


class TestImporterManager(TestCase):

    def setUp(self):
        self.n_objs = 4

        self.usernames: List[str] = None
        self.users: List[User] = None
        self.user_profiles: List[UserProfile] = None
        self.company: Company = None

        #: Create users as before and ADD UserProfile
        self.usernames, self.users, self.user_profiles, self.company = create_multiple_users(self.n_objs)

    def test_single_object_create(self):
        manager = ImporterManager(importer=UserImporter(),create=True)

        self.assertNotIn('foo1', self.usernames)
        self.assertNotIn('foo2', self.usernames)
        manager.update_kvs(field_name='username',value='foo1',row=0)
        manager.update_kvs(field_name='username',value='foo2',row=1)

        users = manager.get_objects_from_rows()
        for i in range(2):
            self.assertIsNone(getattr(users[i], 'pk'))
            self.assertIsInstance(users[i], User)

        self.assertIsNotNone(
            User.objects.bulk_create(users)
        )

    def test_nondependent_object_get(self):
        """Given object without dependency, use it's importerManager to get available data
        """
        manager = ImporterManager(importer=UserImporter())
        for row,name in enumerate(self.usernames):
            manager.update_kvs(field_name='username',value=name,row=row)

        manager.get_available_rows()
        for i in range(self.n_objs):
            objs: List[RecordData] = manager.get_objs_and_meta(i) #: Returns a list of objects only if manytomany
            self.assertEqual(objs[0].available, True)
            self.assertIsNotNone(objs[0].object)
            self.assertIsInstance(objs[0].object, User)
            self.assertIsNotNone(objs[0].query)

        del manager

    def test_partial_nondependent_object_get(self):
        """Given object without dependency, use it's importerManager to get available data, and assert that
        after deleting a given user, we can still query the meta-data returned by the ImporterManger
        """
        MISSING_INDEX = 2
        User.objects.filter(username=self.usernames[MISSING_INDEX]).delete()

        manager = ImporterManager(importer=UserImporter())
        for row,name in enumerate(self.usernames):
            manager.update_kvs(field_name='username',value=name,row=row)

        manager.get_available_rows()
        for i in range(self.n_objs):
            objs: List[RecordData] = manager.get_objs_and_meta(i) #: Returns a list of objects only if manytomany
            if i==MISSING_INDEX:
                self.assertEqual(objs[0].available, False)
                self.assertIsNone(objs[0].object)
                self.assertIsNotNone(objs[0].query)
                continue

            self.assertEqual(objs[0].available, True)
            self.assertIsNotNone(objs[0].object)
            self.assertIsInstance(objs[0].object, User)
            self.assertIsNotNone(objs[0].query)

        del manager

    def test_dependent_object_import(self):
        """Ensures any object with an analagous dependency relationship to
                            UserProfile --> User  && UserProfile --> Company
         can filter based on it's related import kvs
        """
        # Initialize Importers
        up_manager = ImporterManager(importer=UserProfileImporter())
        company_manger = ImporterManager(importer=CompanyImporter())
        user_manager = ImporterManager(importer=UserImporter())

        # Populate leaf models of dependency tree with kv data
        for row,name in enumerate(self.usernames):
            user_manager.update_kvs(field_name='username', value=name, row=row)
            company_manger.update_kvs(field_name='natural_id', value=self.company.natural_id, row=row)

        #: Retrieve data associated with kv data
        user_manager.get_available_rows()
        company_manger.get_available_rows()

        #: Populate data up the dependency tree with retrieved rows
        for row in range(self.n_objs):
            up_manager.update_kvs('company', company_manger.get_object_or_list(row), row=row)
            up_manager.update_kvs('user', user_manager.get_object_or_list(row), row=row)

        #: Retrieve data associated with models depended upon
        up_manager.get_available_rows()

        #: Test corresponding UserProfile has been returned
        for row in range(self.n_objs):
            objs = up_manager.get_objs_and_meta(row) #: Returns a list of objects only if manytomany, o/w just 1

            self.assertEqual(objs[0].available, True)
            self.assertIsNotNone(objs[0].object)
            self.assertIsInstance(objs[0].object, UserProfile)
            self.assertIsNotNone(objs[0].query)

            self.assertEqual(objs[0].object.user.username, self.usernames[row])

    def test_partial_dependent_object_import(self):
        pass

    def test_twice_dependent_object_import(self):
        """
        Tag --> UserProfile --> User
        """
        pass

    def test_partial_twice_dependent_object_import(self):
        """
        Tag --> UserProfile --> User
        """
        pass

    def test_m2m_dependent_object_import(self):
        """
        Image (m)--(m)> Tag --> UserProfile --> User
        """
        pass

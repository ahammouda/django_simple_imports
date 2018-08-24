import random,string

from typing import *

from django.test import TestCase
from .factory import create_multiple_users

from ..simple_imports.importer_manager_v3 import ImporterManager

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
        # Initialize ImporterManger for single object
        # add a couple rows of data
        # get available rows (uncreated)
        # <-- TODO: This test should go in another Testing class (which isn't setup with the same richness as currently
        pass

    def test_nondependent_object_get(self):
        """Given object without dependency, use it's importerManager to get available data
        """
        manager = ImporterManager(importer=UserImporter())
        for row,name in enumerate(self.usernames):
            manager.update_kvs(field_name='username',value=name,row=row)

        manager.get_available_rows()
        for i in range(self.n_objs):
            objs = manager.get_objs_and_meta(i) #: Returns a list of objects only if manytomany
            self.assertEqual(objs[0]['available'], True)
            self.assertIsNotNone(objs[0]['obj'])
            self.assertIsInstance(objs[0]['obj'], UserImporter.model)
            self.assertIsNotNone(objs[0]['query'])

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
            objs = manager.get_objs_and_meta(i) #: Returns a list of objects only if manytomany
            if i==MISSING_INDEX:
                self.assertEqual(objs[0]['available'], False)
                self.assertIsNone(objs[0]['obj'])
                self.assertIsNotNone(objs[0]['query'])
                continue

            self.assertEqual(objs[0]['available'], True)
            self.assertIsNotNone(objs[0]['obj'])
            self.assertIsInstance(objs[0]['obj'],User)
            self.assertIsNotNone(objs[0]['query'])

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

        user_manager.get_available_rows()
        company_manger.get_available_rows()

        for row in range(self.n_objs):
            up_manager.update_kvs('company', company_manger.get_objs(row)[0], row=row)
            up_manager.update_kvs('user', user_manager.get_objs(row)[0], row=row)

        up_manager.get_available_rows()

        #: Test corresponding UserProfile has been returned
        for row in range(self.n_objs):
            objs = up_manager.get_objs_and_meta(row) #: Returns a list of objects only if manytomany, o/w just 1

            self.assertEqual(objs[0]['available'], True)
            self.assertIsNotNone(objs[0]['obj'])
            self.assertIsInstance(objs[0]['obj'], UserProfile)
            self.assertIsNotNone(objs[0]['query'])

            self.assertEqual(objs[0]['obj'].user.username, self.usernames[row])

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

from typing import *

from django.test import TestCase
from .factory import create_multiple_users, create_tags_images, create_base_models

from ..simple_imports.importer_manager import ImporterManager,RecordData

from django.contrib.auth.models import User
from ..tests_app.models import UserProfile,Company,Image,Tag
from ..tests_app.importers import UserImporter,UserProfileImporter,CompanyImporter,ImageImporter,TagImporter


class TestImporterManager(TestCase):
    #: TODO: Might want to break this up into multiple test files:
    #                e.g. importer_manager/test_m2m.py, importer_manager/test_dependent.py, etc

    def setUp(self):
        self.n_objs = 4

        self.usernames: List[str] = None
        self.users: List[User] = None
        self.user_profiles: List[UserProfile] = None
        self.company: Company = None

        #: Create users as before and ADD UserProfile
        self.usernames, self.users, self.user_profiles, self.company = create_multiple_users(self.n_objs)

        #: self.images = [grass, sun];   self.tags = [blue, yellow, green]
        self.images, self.tags = create_tags_images(self.user_profiles[0],self.company)

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

        e.g. see factory.create_tags_images for the creation of the below items
              --> We'll assert that populating related data on the m2m field
                     -> constructs the expect
                     -> retrieves the correct results
                     -> doesn't retrieve the incrorrect results
        Image.pk   Image.name     Tag.name
        i         grass        -  green
        i         grass        -  blue
        k         sun          -  yellow
        l         grass
        m         sun
        """
        user_profile: UserProfile = self.user_profiles[0] # See self.setUp()

        # ************ First Handle generating the Tags/Images Synthetically Through the Importer ************
        # Initialize Importers
        image_manager = ImporterManager(importer=ImageImporter())
        tag_manager = ImporterManager(importer=TagImporter())
        up_manager = ImporterManager(importer=UserProfileImporter())
        company_manger = ImporterManager(importer=CompanyImporter())
        user_manager = ImporterManager(importer=UserImporter())

        # Populate leaf models of dependency tree with kv data
        for row,image in enumerate(self.images):
            user_manager.update_kvs(field_name='username', value=user_profile.user.username, row=row)
            company_manger.update_kvs(field_name='natural_id', value=self.company.natural_id, row=row)

        #: Retrieve data associated with kv data
        user_manager.get_available_rows()
        company_manger.get_available_rows()

        #: Populate data up the dependency tree with retrieved rows
        for row,image in enumerate(self.images):
            up_manager.update_kvs('company', company_manger.get_object_or_list(row), row=row)
            up_manager.update_kvs('user', user_manager.get_object_or_list(row), row=row)

        #: Retrieve data associated with models depended upon
        up_manager.get_available_rows()

        tag_manager.update_kvs('slug', 'blue', row=0, col=0)
        tag_manager.update_kvs('slug', 'green', row=0, col=1)
        tag_manager.update_kvs('company', company_manger.get_object_or_list(0), row=0, col=0)
        tag_manager.update_kvs('created_by', up_manager.get_object_or_list(0), row=0, col=0)

        tag_manager.update_kvs('slug', 'yellow', row=1, col=0)
        tag_manager.update_kvs('company', company_manger.get_object_or_list(1), row=1, col=0)
        tag_manager.update_kvs('created_by', up_manager.get_object_or_list(1), row=1, col=0)

        #: Retrieve associate intermediate data
        tag_manager.get_available_rows()

        for row,image in enumerate(self.images):
            image_manager.update_kvs('path', image.path, row=row)
            image_manager.update_kvs('name', image.name, row=row)
            image_manager.update_kvs('tag', tag_manager.get_object_or_list(row), row=row)
            image_manager.update_kvs('company', company_manger.get_object_or_list(row), row=row)

        image_manager.get_available_rows()

        self.assertNotEqual(image_manager.get_object_or_list(0), [])
        self.assertIsInstance(image_manager.get_object_or_list(0), Image)

        self.assertNotEqual(image_manager.get_object_or_list(1), [])
        self.assertIsInstance(image_manager.get_object_or_list(1), Image)

    def test_m2m_dependent_object_import_precision(self): #: TODO: Come up with a better name
        """
        Image (m)--(m)> Tag --> UserProfile --> User

        e.g. see factory.create_tags_images for the creation of the below items
              --> We'll assert that populating related data on the m2m field
                     -> constructs the expect
                     -> retrieves the correct results
                     -> doesn't retrieve the incrorrect results
        Image.pk   Image.name     Tag.name     company     user
        i         grass        -  green           x         y
        i         grass        -  blue            x         y
        k         sun          -  yellow          x         y
        l         grass        -  green           q         l
        m         sun          -  green           q         l
        """
        other_company = Company.objects.create(name='Other Co', natural_id='oc')
        _,other_user_profile = create_base_models(username='other', company=other_company)

        #: Create same named tags <-- assert later that they do not get filtered out as they are from a different
        #:                            company
        blue = Tag.objects.create(
            company=other_company,
            created_by=other_user_profile,
            name='blue',
            slug='blue',
            rank=0
        )
        green = Tag.objects.create(
            company=other_company,
            created_by=other_user_profile,
            name='green',
            slug='green',
            rank=2
        )

        user_profile: UserProfile = self.user_profiles[0] # See self.setUp()

        # ************ First Handle generating the Tags/Images Synthetically Through the Importer ************
        # Initialize Importers
        image_manager = ImporterManager(importer=ImageImporter())
        tag_manager = ImporterManager(importer=TagImporter())
        up_manager = ImporterManager(importer=UserProfileImporter())
        company_manger = ImporterManager(importer=CompanyImporter())
        user_manager = ImporterManager(importer=UserImporter())

        # Populate leaf models of dependency tree with kv data
        for row,image in enumerate(self.images):
            user_manager.update_kvs(field_name='username', value=user_profile.user.username, row=row)
            company_manger.update_kvs(field_name='natural_id', value=self.company.natural_id, row=row)

        #: Retrieve data associated with kv data
        user_manager.get_available_rows()
        company_manger.get_available_rows()

        #: Populate data up the dependency tree with retrieved rows
        for row,image in enumerate(self.images):
            up_manager.update_kvs('company', company_manger.get_object_or_list(row), row=row)
            up_manager.update_kvs('user', user_manager.get_object_or_list(row), row=row)

        #: Retrieve data associated with models depended upon
        up_manager.get_available_rows()

        tag_manager.update_kvs('slug', 'blue', row=0, col=0)
        tag_manager.update_kvs('slug', 'green', row=0, col=1)
        #: Anyway to avoid pushing these redundant kvs accross a row (??)
        tag_manager.update_kvs('company', company_manger.get_object_or_list(0), row=0, col=0)
        # tag_manager.update_kvs('company', company_manger.get_object_or_list(0), row=0, col=1)
        tag_manager.update_kvs('created_by', up_manager.get_object_or_list(0), row=0, col=0)
        # tag_manager.update_kvs('created_by', up_manager.get_object_or_list(0), row=0, col=1)

        tag_manager.update_kvs('slug', 'yellow', row=1, col=0)
        tag_manager.update_kvs('company', company_manger.get_object_or_list(1), row=1, col=0)
        tag_manager.update_kvs('created_by', up_manager.get_object_or_list(1), row=1, col=0)

        #: Retrieve associate intermediate data
        tag_manager.get_available_rows()

        self.assertEqual(len(tag_manager.get_object_or_list(0)), 2)
        for tag in tag_manager.get_object_or_list(0):
            self.assertEqual(tag.company_id, self.company.id)
            self.assertNotEqual(tag.company_id, other_company.id)

        self.assertIsInstance(tag_manager.get_object_or_list(1), Tag)
from typing import *
import random,string
import os

# Create your tests here.
from django.test import TestCase


from ..tests_app.models import Tag
from .factory import create_base_models


class TestSystemImporter(TestCase):

    def setUp(self):
        """Initialize dependent data for Image model and generate csv file to be used for Image row bulk-creation.
        """
        outdir = os.getcwd()

        user,company,up = create_base_models()

        foo_image_path = '/home/ubuntu/site/uploads/images/'
        self.outpath = os.path.join(outdir,'test_data.csv')
        self.tags: List[Tag] = []
        with open(self.outpath,'w+') as f:
            for i in range(20):
                self.tags.append(
                    Tag(
                        company=company,
                        created_by=up,
                        rank=i,
                        slug=''.join(random.choices(population=string.ascii_uppercase+string.ascii_uppercase,k=4))
                    )
                )
            slugs = f'{self.tags[0].slug}'

            for tag in self.tags[1:]:
                slugs = f'{slugs};{tag.slug}'

                f.write(f'{user.username},{company.natural_id},'
                        f'{slugs},{foo_image_path},foo_{i}.png\n')

        Tag.objects.bulk_create(self.tags)

    def test_foo(self):
        #: TODO: Really need to setup the code to load a large number of initial rows
        #: Then manually iterate through each row, adding kvs to importer_manager_v2 successively manually
        #: Then assert that they have the expected number of rows.
        #: Assert it loads the correct number of related objects

        #: Then put rows in csv without corresponding model, and assert it 'fails' gracefully, logging unfound
        #: related data

        #: Then separate set of tests for SystemImporter, and make a couple assertions about how things work
        #: * ordering of topo-sort
        #: * several sets of tests for structure of data structures used for mapping data out of csv file
        self.assertAlmostEquals(True,True)
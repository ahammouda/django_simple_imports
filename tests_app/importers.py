from collections import OrderedDict

from django.db import models

from ..simple_imports.model_importer import ModelImporter

from django.contrib.auth.models import User
from .models import Company,UserProfile,Tag,Image

class CompanyImporter(ModelImporter):
    model = Company

    field_types = {
        'natural_id': str
    }

    required_fields = ('natural_id',)


class UserImporter(ModelImporter):
    model = User

    field_types = {
        'username': str
    }

    required_fields = ('username',)


class UserProfileImporter(ModelImporter):
    model = UserProfile

    field_types = {
        'user': models.Model,
        'company': models.Model
    }

    dependent_imports = OrderedDict({
        'user': UserImporter,
        'company': CompanyImporter
    })


class TagImporter(ModelImporter):
    model = Tag

    field_types = {
        'slug':str,
        'created_by': models.Model,
        'company': models.Model,
    }

    required_fields = ('slug',)

    dependent_imports = OrderedDict({
        'created_by': UserProfileImporter,
        'company': CompanyImporter
    })


class ImageImporter(ModelImporter):
    model = Image

    field_types = {
        'path': str,
        'name': str,
        'tag': models.Model,
        'company': models.Model
    }

    required_fields = ('path','name',)

    dependent_imports = OrderedDict({
        'tag' : TagImporter,
        'company': CompanyImporter
    })


# ********* For simple examples *********
# from .models import ExampleBaseModel,ExampleManyToManyModel
#
# class ExampleBaseImporter(ModelImporter):
#     model = ExampleBaseModel
#
#     required_fields = ('slug',)
#
#
# class ExampleM2MImporter(ModelImporter):
#     model = ExampleManyToManyModel
#
#     required_fields = ('slug',)
#
#     dependent_imports = OrderedDict({
#         'base_relation': ExampleBaseModel
#     })

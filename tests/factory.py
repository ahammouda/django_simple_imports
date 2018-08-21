from django.contrib.auth.models import User

from ..tests_app.models import UserProfile,Company,Tag

def create_base_models():
    user = User.objects.create(
        username = 'foomanchu', email='foomanchu@gmail.com', first_name = 'Foo', last_name = 'manchu'
    )
    company = Company.objects.create(
        name = 'Foo Folk Tagging', natural_id = 'fft'
    )
    up = UserProfile.objects.create(
        user=user,
        company = company
    )
    print(f'Created {user.username} for company {company.name}.')
    return user,company,up

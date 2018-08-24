import random,string

from django.contrib.auth.models import User

from ..tests_app.models import UserProfile,Company,Tag

def create_base_models(username: str, company: Company):
    """Create and  return associated User and UserProfile objects given username, company

    :param username:
    :param company:
    :return: Tuple[User,UserProfile]
    """
    user = User.objects.create(
        username = username, email=f'{username}@gmail.com', first_name = 'Foo', last_name = 'manchu'
    )
    up = UserProfile.objects.create(
        user=user,
        company = company
    )
    print(f'Created {user.username} for company {company.name}.')
    return user,up

def get_usernames(n_objs: int):
    pass


def create_multiple_users(n_objs: int):
    """Create random users for foo company, and return all objects and

    :param n_objs: number of dummy users to create
    :return: Tuple[List[str],List[User],List[UserProfile],List[Company]]
    """
    company = Company.objects.create(
        name = 'Foo Folk Tagging', natural_id = 'fft'
    )
    usernames = []
    users = []
    user_profiles = []
    for i in range(n_objs):
        uname = ''.join(random.choices(population=string.ascii_uppercase+string.ascii_uppercase,k=4))
        user,up = create_base_models(uname, company)
        usernames.append(uname)
        users.append(user)
        user_profiles.append(up)

    return usernames,users,user_profiles,company
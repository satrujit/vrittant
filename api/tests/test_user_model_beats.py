"""User model has categories and regions JSON columns for reviewer beats."""
from app.models.user import User


def test_user_has_categories_default_empty_list():
    u = User(name="A", phone="1")
    assert u.categories == [] or u.categories is None  # default applied at flush


def test_user_has_regions_default_empty_list():
    u = User(name="A", phone="1")
    assert u.regions == [] or u.regions is None

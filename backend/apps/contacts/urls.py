"""
URLs para o módulo de contatos
"""

from rest_framework.routers import DefaultRouter
from .views import ContactViewSet, TagViewSet, ContactListViewSet, ContactImportViewSet

router = DefaultRouter()
router.register(r'contacts', ContactViewSet, basename='contact')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'lists', ContactListViewSet, basename='contact-list')
router.register(r'imports', ContactImportViewSet, basename='contact-import')

urlpatterns = router.urls

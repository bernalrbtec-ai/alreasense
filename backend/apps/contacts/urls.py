from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.contacts.views import ContactViewSet, ContactGroupViewSet

router = DefaultRouter()
router.register(r'contacts', ContactViewSet, basename='contact')
router.register(r'groups', ContactGroupViewSet, basename='contact-group')

urlpatterns = [
    path('', include(router.urls)),
]


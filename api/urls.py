from django.urls import path

from api.views import receber_leituras

urlpatterns = [
    path('leituras/', receber_leituras, name='api_leituras'),
]

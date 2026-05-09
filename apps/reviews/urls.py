from django.urls import path
from . import views

urlpatterns = [
    path("", views.CreateReviewView.as_view(), name="review-create"),
    path("driver/<int:driver_id>/", views.DriverReviewListView.as_view(), name="driver-reviews"),
]

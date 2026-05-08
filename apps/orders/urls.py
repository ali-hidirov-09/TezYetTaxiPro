from django.urls import path
from . import views

urlpatterns = [
    # Mijoz
    path("estimate/", views.EstimatePriceView.as_view(), name="order-estimate"),
    path("", views.OrderListCreateView.as_view(), name="order-list-create"),
    path("<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("<int:pk>/cancel/", views.OrderCancelView.as_view(), name="order-cancel"),

    # Haydovchi
    path("driver/available/", views.DriverAvailableOrdersView.as_view(), name="driver-available"),
    path("driver/my/", views.DriverMyOrdersView.as_view(), name="driver-my-orders"),
    path("<int:pk>/accept/", views.OrderAcceptView.as_view(), name="order-accept"),
    path("<int:pk>/start/", views.OrderStartView.as_view(), name="order-start"),
    path("<int:pk>/complete/", views.OrderCompleteView.as_view(), name="order-complete"),

    # Admin
    path("admin/all/", views.AdminOrderListView.as_view(), name="admin-order-list"),
]

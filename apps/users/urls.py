from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Auth
    path("auth/send-otp/", views.SendOtpView.as_view(), name="send-otp"),
    path("auth/verify-otp/", views.VerifyOtpLoginView.as_view(), name="verify-otp"),
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # Profile
    path("me/", views.MeView.as_view(), name="me"),

    # Driver
    path("driver/profile/", views.DriverProfileView.as_view(), name="driver-profile"),
    path("driver/location/", views.DriverLocationView.as_view(), name="driver-location"),

    # Admin
    path("admin/users/", views.AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<int:user_id>/toggle-active/", views.AdminToggleUserActiveView.as_view(), name="admin-user-toggle"),
    path("admin/drivers/", views.AdminDriverListView.as_view(), name="admin-driver-list"),
    path("admin/drivers/create/", views.AdminCreateDriverView.as_view(), name="admin-driver-create"),
]

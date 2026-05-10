import logging
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import DriverProfile
from .otp_service import generate_otp, verify_otp, get_remaining_seconds, is_blocked
from .permissions import IsAdminUser, IsDriver
from .serializers import (
    SendOtpSerializer, VerifyOtpSerializer, RegisterSerializer,
    UserProfileSerializer, DriverProfileSerializer, DriverLocationSerializer,
    CreateDriverSerializer, AdminUserListSerializer,
)
from .sms_service import send_otp_sms

User = get_user_model()
logger = logging.getLogger(__name__)


def _get_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "role": user.role,
    }


class SendOtpView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="OTP yuborish",
        description=(
            "Telefon raqamga SMS kod yuboradi.\n\n"
            "- `is_registered: true` → `/auth/verify-otp/`\n"
            "- `is_registered: false` → `/auth/register/`\n\n"
            "Har 60 sekundda bir marta."
        ),
        request=SendOtpSerializer,
        responses={
            200: OpenApiResponse(description="{ detail, is_registered }"),
            400: OpenApiResponse(description="Validatsiya xatosi"),
            429: OpenApiResponse(description="Juda tez yoki bloklangan"),
            503: OpenApiResponse(description="SMS xizmati ishlamayapti"),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = SendOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        # Brute-force blokmi?
        if is_blocked(phone):
            return Response(
                {"detail": "Juda ko'p noto'g'ri urinish. Iltimos 2 daqiqadan keyin qayta urinib ko'ring."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            code = generate_otp(phone)
        except Exception:
            logger.exception("Redis ulanish xatosi — generate_otp")
            return Response(
                {"detail": "Xizmat vaqtincha mavjud emas. Iltimos keyinroq urinib ko'ring."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if code is None:
            remaining = get_remaining_seconds(phone)
            return Response(
                {"detail": f"Iltimos {remaining} soniya kuting."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not send_otp_sms(phone, code):
            return Response(
                {"detail": "SMS yuborishda xato. Iltimos keyinroq urinib ko'ring."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            "detail": "Kod yuborildi.",
            "is_registered": User.objects.filter(phone=phone).exists(),
        })


class VerifyOtpLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Kirish — OTP tasdiqlash",
        request=VerifyOtpSerializer,
        responses={
            200: OpenApiResponse(description="{ access, refresh, role }"),
            400: OpenApiResponse(description="Kod noto'g'ri yoki muddati o'tgan"),
            404: OpenApiResponse(description="Foydalanuvchi topilmadi"),
            429: OpenApiResponse(description="Juda ko'p noto'g'ri urinish"),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        if is_blocked(phone):
            return Response(
                {"detail": "Juda ko'p noto'g'ri urinish. 2 daqiqadan keyin qayta urinib ko'ring."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            valid = verify_otp(phone, code)
        except Exception:
            logger.exception("Redis ulanish xatosi — verify_otp")
            return Response(
                {"detail": "Xizmat vaqtincha mavjud emas."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not valid:
            return Response(
                {"detail": "Kod noto'g'ri yoki muddati o'tgan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response(
                {"detail": "Foydalanuvchi topilmadi. Avval ro'yxatdan o'ting."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        return Response(_get_tokens(user))


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Ro'yxatdan o'tish",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description="{ access, refresh, role }"),
            400: OpenApiResponse(description="Validatsiya xatosi yoki OTP noto'g'ri"),
            429: OpenApiResponse(description="OTP bloklangan"),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        full_name = serializer.validated_data["full_name"]
        code = serializer.validated_data["code"]

        if is_blocked(phone):
            return Response(
                {"detail": "Juda ko'p noto'g'ri urinish. 2 daqiqadan keyin qayta urinib ko'ring."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            valid = verify_otp(phone, code)
        except Exception:
            logger.exception("Redis ulanish xatosi — register verify_otp")
            return Response(
                {"detail": "Xizmat vaqtincha mavjud emas."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not valid:
            return Response(
                {"detail": "Kod noto'g'ri yoki muddati o'tgan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            phone=phone,
            full_name=full_name,
            role="client",
            is_active=True,
        )

        logger.info(f"Yangi mijoz ro'yxatdan o'tdi: ...{phone[-4:]}")
        return Response(_get_tokens(user), status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Chiqish (Logout)",
        description="Refresh tokenni bekor qiladi.",
        tags=["Auth"],
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "refresh token yuborilishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Token noto'g'ri yoki allaqachon bekor qilingan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"detail": "Muvaffaqiyatli chiqildi."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Mening profilim", responses={200: UserProfileSerializer}, tags=["Profile"])
    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

    @extend_schema(summary="Profilni tahrirlash", request=UserProfileSerializer,
                   responses={200: UserProfileSerializer}, tags=["Profile"])
    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DriverProfileView(APIView):
    permission_classes = [IsDriver]

    @extend_schema(summary="Haydovchi profili", responses={200: DriverProfileSerializer}, tags=["Driver"])
    def get(self, request):
        return Response(DriverProfileSerializer(request.user.driver_profile).data)


class DriverLocationView(APIView):
    permission_classes = [IsDriver]

    @extend_schema(
        summary="Joylashuvni yangilash",
        request=DriverLocationSerializer,
        responses={200: OpenApiResponse(description="Yangilandi")},
        tags=["Driver"],
    )
    def patch(self, request):
        serializer = DriverLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = request.user.driver_profile
        profile.current_lat = serializer.validated_data["lat"]
        profile.current_lon = serializer.validated_data["lon"]

        update_fields = ["current_lat", "current_lon"]
        if "is_available" in serializer.validated_data:
            profile.is_available = serializer.validated_data["is_available"]
            update_fields.append("is_available")

        profile.save(update_fields=update_fields)
        return Response({"detail": "Joylashuv yangilandi."})


class AdminCreateDriverView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Yangi haydovchi qo'shish",
        request=CreateDriverSerializer,
        responses={201: DriverProfileSerializer},
        tags=["Admin"],
    )
    def post(self, request):
        serializer = CreateDriverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        logger.info(f"Yangi haydovchi: ...{profile.user.phone[-4:]}")
        return Response(DriverProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class AdminDriverListView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Barcha haydovchilar",
        responses={200: DriverProfileSerializer(many=True)},
        tags=["Admin"],
    )
    def get(self, request):
        profiles = DriverProfile.objects.select_related("user").order_by("-created_at")
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(profiles, request)
        return paginator.get_paginated_response(DriverProfileSerializer(page, many=True).data)


class AdminUserListView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Barcha foydalanuvchilar",
        responses={200: AdminUserListSerializer(many=True)},
        tags=["Admin"],
    )
    def get(self, request):
        users = User.objects.order_by("-created_at")
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(users, request)
        return paginator.get_paginated_response(AdminUserListSerializer(page, many=True).data)


class AdminToggleUserActiveView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Bloklash / blokdan chiqarish",
        responses={200: OpenApiResponse(description="{ detail, is_active }")},
        tags=["Admin"],
    )
    def post(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "Foydalanuvchi topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        state = "faollashtirildi" if user.is_active else "bloklandi"
        return Response({"detail": f"Foydalanuvchi {state}.", "is_active": user.is_active})

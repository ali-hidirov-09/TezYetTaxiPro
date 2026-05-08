from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import DriverProfile

User = get_user_model()


class SendOtpSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        value = value.strip()
        if not value.startswith("+"):
            raise serializers.ValidationError(
                "Telefon raqami + bilan boshlanishi kerak. Masalan: +77001234567"
            )
        if not value[1:].isdigit():
            raise serializers.ValidationError(
                "Telefon raqamida faqat raqamlar bo'lishi kerak."
            )
        if not (11 <= len(value) <= 16):
            raise serializers.ValidationError("Telefon raqami noto'g'ri formatda.")
        return value


class VerifyOtpSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(min_length=6, max_length=6)

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Kod faqat raqamlardan iborat bo'lishi kerak.")
        return value


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    full_name = serializers.CharField(max_length=100)
    code = serializers.CharField(min_length=6, max_length=6)

    def validate_phone(self, value):
        value = value.strip()
        if not value.startswith("+"):
            raise serializers.ValidationError("Telefon raqami + bilan boshlanishi kerak.")
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "Bu telefon raqami allaqachon ro'yxatdan o'tgan."
            )
        return value

    def validate_full_name(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Ism kamida 3 ta harf bo'lishi kerak.")
        return value

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Kod faqat raqamlardan iborat bo'lishi kerak.")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "role", "created_at"]
        read_only_fields = ["id", "phone", "role", "created_at"]


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)

    class Meta:
        model = DriverProfile
        fields = [
            "id", "user", "car_model", "car_number", "car_color",
            "is_available", "current_lat", "current_lon",
            "rating", "total_trips", "created_at",
        ]
        read_only_fields = ["id", "user", "rating", "total_trips", "created_at"]


class DriverLocationSerializer(serializers.Serializer):
    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lon = serializers.DecimalField(max_digits=9, decimal_places=6)
    is_available = serializers.BooleanField(required=False)


class CreateDriverSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(write_only=True)
    full_name = serializers.CharField(write_only=True)

    class Meta:
        model = DriverProfile
        fields = ["phone", "full_name", "car_model", "car_number", "car_color"]

    def validate_phone(self, value):
        value = value.strip()
        if not value.startswith("+"):
            raise serializers.ValidationError("Telefon raqami + bilan boshlanishi kerak.")
        return value

    def create(self, validated_data):
        phone = validated_data.pop("phone")
        full_name = validated_data.pop("full_name")

        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={"full_name": full_name, "role": "driver", "is_active": True},
        )

        if not created:
            if user.role != "driver":
                raise serializers.ValidationError(
                    {"phone": "Bu foydalanuvchi boshqa rolda ro'yxatdan o'tgan."}
                )
            if hasattr(user, "driver_profile"):
                raise serializers.ValidationError(
                    {"phone": "Bu haydovchining profili allaqachon mavjud."}
                )

        return DriverProfile.objects.create(user=user, **validated_data)


class AdminUserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "role", "is_active", "created_at"]
        read_only_fields = fields

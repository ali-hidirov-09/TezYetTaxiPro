from rest_framework import serializers
from .models import Order


class EstimatePriceSerializer(serializers.Serializer):
    from_lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    from_lon = serializers.DecimalField(max_digits=9, decimal_places=6)
    to_lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    to_lon = serializers.DecimalField(max_digits=9, decimal_places=6)


class CreateOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "from_address", "from_lat", "from_lon",
            "to_address", "to_lat", "to_lon",
            "comment",
        ]

    def validate(self, attrs):
        if (
            attrs["from_lat"] == attrs["to_lat"]
            and attrs["from_lon"] == attrs["to_lon"]
        ):
            raise serializers.ValidationError(
                "Ketish va borish manzili bir xil bo'lishi mumkin emas."
            )
        return attrs


class OrderSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.full_name", read_only=True)
    client_phone = serializers.CharField(source="client.phone", read_only=True)
    driver_name = serializers.SerializerMethodField()
    driver_phone = serializers.SerializerMethodField()
    driver_car = serializers.SerializerMethodField()
    driver_car_color = serializers.SerializerMethodField()
    driver_rating = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "client_name", "client_phone",
            "driver_name", "driver_phone", "driver_car",
            "driver_car_color", "driver_rating",
            "from_address", "from_lat", "from_lon",
            "to_address", "to_lat", "to_lon",
            "distance_km", "estimated_price", "final_price",
            "status", "status_display", "comment",
            "created_at", "accepted_at", "completed_at",
        ]
        read_only_fields = fields

    def get_driver_name(self, obj):
        return obj.driver.user.full_name if obj.driver else None

    def get_driver_phone(self, obj):
        return obj.driver.user.phone if obj.driver else None

    def get_driver_car(self, obj):
        if obj.driver:
            return f"{obj.driver.car_model} — {obj.driver.car_number}"
        return None

    def get_driver_car_color(self, obj):
        return obj.driver.car_color if obj.driver else None

    def get_driver_rating(self, obj):
        return float(obj.driver.rating) if obj.driver else None


class OrderListSerializer(serializers.ModelSerializer):
    """Ro'yxat uchun — yengil versiya."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "from_address", "to_address",
            "estimated_price", "final_price",
            "status", "status_display", "created_at",
        ]
        read_only_fields = fields

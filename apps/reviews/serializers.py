from rest_framework import serializers
from .models import Review


class CreateReviewSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ReviewSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "client_name", "rating", "comment", "created_at"]
        read_only_fields = fields

    def get_client_name(self, obj):
        parts = obj.client.full_name.split()
        return parts[0] if parts else "Mijoz"

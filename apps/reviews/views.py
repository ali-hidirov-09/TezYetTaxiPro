import logging
from django.db import transaction
from django.db.models import Avg
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from apps.users.models import DriverProfile
from apps.users.permissions import IsClient
from apps.orders.models import Order
from .models import Review
from .serializers import CreateReviewSerializer, ReviewSerializer

logger = logging.getLogger(__name__)


class CreateReviewView(APIView):
    permission_classes = [IsClient]

    @extend_schema(
        summary="Haydovchiga baho berish",
        description=(
            "1–5 gacha baho. Shartlar:\n"
            "- Order `completed` holatida bo'lishi shart\n"
            "- Faqat shu orderning mijozi baho bera oladi\n"
            "- Har bir order uchun faqat bitta baho"
        ),
        request=CreateReviewSerializer,
        responses={
            201: ReviewSerializer,
            400: OpenApiResponse(description="Safar yakunlanmagan yoki boshqa xato"),
            403: OpenApiResponse(description="Bu buyurtma sizga tegishli emas"),
            404: OpenApiResponse(description="Buyurtma topilmadi"),
            409: OpenApiResponse(description="Allaqachon baho berilgan"),
        },
        examples=[
            OpenApiExample(
                "Misol",
                value={"order_id": 1, "rating": 5, "comment": "Zo'r haydovchi!"},
                request_only=True,
            )
        ],
        tags=["Reviews"],
    )
    def post(self, request):
        serializer = CreateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]

        with transaction.atomic():

            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=order_id
            )

            if order.client != request.user:
                return Response({"detail": "Ruxsat yo'q."}, status=403)
            if order.status != Order.STATUS_COMPLETED:
                return Response({"detail": "Faqat yakunlangan safar."}, status=400)
            if hasattr(order, "review"):
                return Response({"detail": "Allaqachon baho berilgan."}, status=409)

            if order.driver is None:
                return Response(
                    {"detail": "Bu buyurtmada haydovchi topilmadi."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            driver = order.driver
            if driver is None:
                return Response({"detail": "Haydovchi topilmadi."}, status=400)

            review = Review.objects.create(
                order=order,
                client=request.user,
                driver=order.driver,
                rating=serializer.validated_data["rating"],
                comment=serializer.validated_data.get("comment", ""),
            )

            avg = Review.objects.filter(driver=order.driver).aggregate(avg=Avg("rating"))["avg"]
            order.driver.rating = round(avg, 2)
            order.driver.save(update_fields=["rating"])

        logger.info(f"Review yaratildi: order #{order.pk}, driver #{order.driver.pk}, rating={review.rating}")
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class DriverReviewListView(APIView):
    """
    Haydovchiga berilgan baholar.
    AllowAny — frontend haydovchi profilida ko'rsatish uchun.
    client_name da faqat ism (familiya emas) — maxfiylik saqlanadi.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Haydovchi reytinglari",
        responses={200: OpenApiResponse(
            description="{ driver_id, driver_name, rating, total_reviews, next, previous, results[] }"
        )},
        tags=["Reviews"],
    )
    def get(self, request, driver_id):
        driver = get_object_or_404(
            DriverProfile.objects.select_related("user"), pk=driver_id
        )

        reviews = (
            Review.objects
            .filter(driver=driver)
            .select_related("client")
            .order_by("-created_at")
        )

        total = reviews.count()

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(reviews, request)

        return paginator.get_paginated_response({
            "driver_id": driver_id,
            "driver_name": driver.user.full_name,
            "rating": float(driver.rating),
            "total_reviews": total,
            "reviews": ReviewSerializer(page, many=True).data,
        })

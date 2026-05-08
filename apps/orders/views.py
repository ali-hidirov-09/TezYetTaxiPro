import logging
from django.db import transaction, DatabaseError, OperationalError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter,
)
from drf_spectacular.types import OpenApiTypes

from apps.users.permissions import IsClient, IsDriver, IsAdminUser
from .models import Order
from .serializers import (
    CreateOrderSerializer,
    EstimatePriceSerializer,
    OrderSerializer,
    OrderListSerializer,
)
from . import services

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = [
    Order.STATUS_PENDING,
    Order.STATUS_ACCEPTED,
    Order.STATUS_IN_PROGRESS,
]


class EstimatePriceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Narx taxmini",
        description="Koordinatalar asosida taxminiy narx va masofani qaytaradi.\n\nFormula: `300 + (km × 100)` tenge.",
        request=EstimatePriceSerializer,
        responses={200: OpenApiResponse(description="{ distance_km, estimated_price }")},
        examples=[
            OpenApiExample(
                "Sayram → Shymkent",
                value={"from_lat": "42.308800", "from_lon": "69.737200",
                       "to_lat": "42.340000", "to_lon": "69.600000"},
                request_only=True,
            )
        ],
        tags=["Orders"],
    )
    def post(self, request):
        serializer = EstimatePriceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        result = services.estimate_route(
            float(d["from_lat"]), float(d["from_lon"]),
            float(d["to_lat"]), float(d["to_lon"]),
        )
        return Response(result)


class OrderListCreateView(APIView):
    permission_classes = [IsClient]

    @extend_schema(
        summary="Mening buyurtmalarim",
        responses={200: OrderListSerializer(many=True)},
        tags=["Orders"],
    )
    def get(self, request):
        orders = (
            Order.objects
            .filter(client=request.user)
            .only("id", "from_address", "to_address",
                  "estimated_price", "final_price", "status", "created_at")
        )
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(orders, request)
        return paginator.get_paginated_response(OrderListSerializer(page, many=True).data)

    @extend_schema(
        summary="Yangi buyurtma",
        request=CreateOrderSerializer,
        responses={
            201: OrderSerializer,
            400: OpenApiResponse(description="Validatsiya xatosi"),
            409: OpenApiResponse(description="Aktiv buyurtma allaqachon bor"),
        },
        tags=["Orders"],
    )
    def post(self, request):
        if Order.objects.filter(client=request.user, status__in=ACTIVE_STATUSES).exists():
            return Response(
                {"detail": "Sizda aktiv buyurtma mavjud. Avval uni yakunlang yoki bekor qiling."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        estimate = services.estimate_route(
            float(d["from_lat"]), float(d["from_lon"]),
            float(d["to_lat"]), float(d["to_lon"]),
        )

        order = Order.objects.create(
            client=request.user,
            estimated_price=estimate["estimated_price"],
            distance_km=estimate["distance_km"],
            **d,
        )

        logger.info(f"Yangi buyurtma #{order.pk} yaratildi")
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Buyurtma tafsiloti",
        responses={200: OrderSerializer},
        tags=["Orders"],
    )
    def get(self, request, pk):
        order = get_object_or_404(
            Order.objects.select_related("client", "driver__user"), pk=pk
        )

        if request.user.role == "client" and order.client != request.user:
            return Response({"detail": "Topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        if request.user.role == "driver":
            if order.driver is None or order.driver.user != request.user:
                return Response({"detail": "Topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        return Response(OrderSerializer(order).data)


class OrderCancelView(APIView):
    permission_classes = [IsClient]

    @extend_schema(
        summary="Buyurtmani bekor qilish",
        responses={
            200: OpenApiResponse(description="Bekor qilindi"),
            400: OpenApiResponse(description="Bu holatda bekor qilib bo'lmaydi"),
        },
        tags=["Orders"],
    )
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, client=request.user)

        if not order.can_be_cancelled:
            return Response(
                {"detail": f"'{order.get_status_display()}' holatidagi buyurtmani bekor qilib bo'lmaydi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        services.cancel_order(order)
        return Response({"detail": "Buyurtma bekor qilindi."})


class DriverAvailableOrdersView(APIView):
    permission_classes = [IsDriver]

    @extend_schema(
        summary="Mavjud buyurtmalar (haydovchi)",
        responses={200: OrderListSerializer(many=True)},
        tags=["Driver"],
    )
    def get(self, request):
        orders = (
            Order.objects
            .filter(status=Order.STATUS_PENDING)
            .order_by("-created_at")
        )
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(orders, request)
        return paginator.get_paginated_response(OrderListSerializer(page, many=True).data)


class DriverMyOrdersView(APIView):
    permission_classes = [IsDriver]

    @extend_schema(
        summary="Mening safarlarim (haydovchi)",
        responses={200: OrderListSerializer(many=True)},
        tags=["Driver"],
    )
    def get(self, request):
        orders = (
            Order.objects
            .filter(driver=request.user.driver_profile)
            .only("id", "from_address", "to_address", "final_price", "status", "created_at")
        )
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(orders, request)
        return paginator.get_paginated_response(OrderListSerializer(page, many=True).data)


class OrderAcceptView(APIView):
    permission_classes = [IsDriver]

    @extend_schema(
        summary="Buyurtmani qabul qilish",
        responses={
            200: OpenApiResponse(description="{ detail, order_id }"),
            400: OpenApiResponse(description="Allaqachon qabul qilingan"),
            409: OpenApiResponse(description="Boshqa haydovchi qabul qilyapti"),
        },
        tags=["Driver"],
    )
    def post(self, request, pk):
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update(nowait=True).get(pk=pk)
            except Order.DoesNotExist:
                return Response(
                    {"detail": "Buyurtma topilmadi."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            except (DatabaseError, OperationalError):
                return Response(
                    {"detail": "Buyurtma hozir boshqa haydovchi tomonidan qabul qilinyapti. Qayta urining."},
                    status=status.HTTP_409_CONFLICT,
                )

            if not order.can_be_accepted:
                return Response(
                    {"detail": "Bu buyurtma allaqachon qabul qilingan yoki mavjud emas."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            services.accept_order(order, request.user.driver_profile)

        return Response({"detail": "Buyurtma qabul qilindi.", "order_id": order.pk})


class OrderStartView(APIView):
    permission_classes = [IsDriver]

    @extend_schema(
        summary="Safarni boshlash",
        responses={
            200: OpenApiResponse(description="Safar boshlandi"),
            400: OpenApiResponse(description="Noto'g'ri holat"),
        },
        tags=["Driver"],
    )
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, driver=request.user.driver_profile)

        if not order.can_be_started:
            return Response(
                {"detail": "Safarni boshlash uchun buyurtma 'accepted' holatida bo'lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        services.start_order(order)
        return Response({"detail": "Safar boshlandi."})


class OrderCompleteView(APIView):
    permission_classes = [IsDriver]

    @extend_schema(
        summary="Safarni yakunlash",
        responses={
            200: OpenApiResponse(description="{ detail, final_price, distance_km }"),
            400: OpenApiResponse(description="Noto'g'ri holat"),
        },
        tags=["Driver"],
    )
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, driver=request.user.driver_profile)

        if not order.can_be_completed:
            return Response(
                {"detail": "Safarni yakunlash uchun 'in_progress' holatida bo'lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        services.complete_order(order)
        return Response({
            "detail": "Safar yakunlandi.",
            "final_price": order.final_price,
            "distance_km": float(order.distance_km),
        })


class AdminOrderListView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Barcha buyurtmalar (admin)",
        parameters=[
            OpenApiParameter(
                name="status", type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="pending | accepted | in_progress | completed | cancelled",
                required=False,
            )
        ],
        responses={200: OrderSerializer(many=True)},
        tags=["Admin"],
    )
    def get(self, request):
        qs = Order.objects.select_related("client", "driver__user").order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(OrderSerializer(page, many=True).data)

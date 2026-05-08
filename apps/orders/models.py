from django.db import models
from django.conf import settings


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Haydovchi kutilmoqda"),
        (STATUS_ACCEPTED, "Haydovchi qabul qildi"),
        (STATUS_IN_PROGRESS, "Safar boshlandi"),
        (STATUS_COMPLETED, "Safar tugadi"),
        (STATUS_CANCELLED, "Bekor qilindi"),
    ]

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    driver = models.ForeignKey(
        "users.DriverProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    from_address = models.TextField()
    from_lat = models.DecimalField(max_digits=9, decimal_places=6)
    from_lon = models.DecimalField(max_digits=9, decimal_places=6)

    to_address = models.TextField()
    to_lat = models.DecimalField(max_digits=9, decimal_places=6)
    to_lon = models.DecimalField(max_digits=9, decimal_places=6)

    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    estimated_price = models.PositiveIntegerField(default=0)  # tenge
    final_price = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PENDING, db_index=True,
    )
    comment = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders"
        verbose_name = "Buyurtma"
        verbose_name_plural = "Buyurtmalar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} | {self.client} | {self.status}"

    @property
    def can_be_cancelled(self):
        return self.status in (self.STATUS_PENDING, self.STATUS_ACCEPTED)

    @property
    def can_be_accepted(self):
        return self.status == self.STATUS_PENDING

    @property
    def can_be_started(self):
        return self.status == self.STATUS_ACCEPTED

    @property
    def can_be_completed(self):
        return self.status == self.STATUS_IN_PROGRESS

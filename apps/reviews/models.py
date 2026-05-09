from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings


class Review(models.Model):
    """
    Har bir yakunlangan safar uchun faqat bitta review.
    OneToOneField bu qoidani DB darajasida ta'minlaydi.
    """

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="review",
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="given_reviews",
    )
    driver = models.ForeignKey(
        "users.DriverProfile",
        on_delete=models.CASCADE,
        related_name="received_reviews",
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews"
        verbose_name = "Reyting"
        verbose_name_plural = "Reytinglar"

    def __str__(self):
        return f"Order #{self.order_id} — {self.rating}⭐"

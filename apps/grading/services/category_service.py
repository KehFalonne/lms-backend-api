from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.grading.models import GradeCategory, GradeItem


class CategoryService:

    @staticmethod
    @transaction.atomic
    def set_weights(*, course_offering_id, weights: list[dict]) -> list[GradeCategory]:
        # Coerce incoming weights to Decimal
        coerced = [
            {
                "name": str(w["name"]).strip(),
                "weight": Decimal(str(w["weight"])),
                "position": int(w.get("position", idx)),
            }
            for idx, w in enumerate(weights, start=1)
        ]

        total = sum((w["weight"] for w in coerced), start=Decimal("0"))
        if total != Decimal("100"):
            raise ValidationError(
                {"weights": [f"Category weights must sum to 100%. Got {total}%."]}
            )

        existing_names = {w["name"] for w in coerced}
        GradeCategory.objects.filter(
            course_offering_id=course_offering_id,
        ).exclude(name__in=existing_names).delete()

        categories = []
        for w in coerced:
            cat, _ = GradeCategory.objects.update_or_create(
                course_offering_id=course_offering_id,
                name=w["name"],
                defaults={"weight": w["weight"], "position": w["position"]},
            )
            categories.append(cat)
        return categories

    @staticmethod
    def check_weights_balanced(course_offering_id) -> bool:
        from django.db.models import Sum

        total = GradeCategory.objects.filter(
            course_offering_id=course_offering_id
        ).aggregate(t=Sum("weight"))["t"]
        return total == Decimal("100")

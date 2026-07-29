from django.db import models


class State(models.Model):
    # usa o código oficial do IBGE como chave
    id = models.PositiveSmallIntegerField(primary_key=True)
    name = models.CharField(max_length=50)
    acronym = models.CharField(max_length=2, unique=True)

    class Meta:
        db_table = "states"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.acronym})"


class City(models.Model):
    # município também fica com o código oficial do IBGE
    id = models.PositiveIntegerField(primary_key=True)
    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="cities",
        db_column="state_id",
    )
    name = models.CharField(max_length=100)
    normalized_name = models.CharField(max_length=100, db_index=True)

    class Meta:
        db_table = "cities"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["state", "normalized_name"],
                name="uniq_city_state_normalized_name",
            ),
        ]
        indexes = [
            models.Index(fields=["state", "name"], name="cities_state_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.state.acronym})"

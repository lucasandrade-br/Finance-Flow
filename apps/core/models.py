from django.db import models


class ModeloBase(models.Model):
    """Modelo base abstrato com auditoria de criação e atualização."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

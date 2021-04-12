from django.db import models
from django.utils.translation import ugettext_lazy as _

class HelpTagItem(object):
    def __init__(self, title, body, path, group="Filters", position=None, examples=None, img=None):
        self.title = title
        self.body = body
        self.examples = examples
        self.group = group
        self.img = img
        self.path = path
        self.position = position

class FavoriteReports(models.Model):
    favorite_report_id = models.AutoField(
        primary_key=True,
        db_column="favorite_report_id",
        verbose_name="favorite_report_id",
        help_text="favorite_report number",
    )
    user_id = models.IntegerField(
        null=False,
        blank=False,
        db_column='user_id',
        verbose_name="user id",
        help_text="user id"
    )
    form_id = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        help_text="Form code report identification")
    name = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        help_text="Name of the favorite report")
    field_name = models.CharField(
        max_length=100,
        null=False,
        db_column="field_name",
        verbose_name="field_name",
        help_text="id/name of the field",
    )
    field_value = models.TextField(
        null=False,
        db_column="field_value",
        verbose_name="field_value",
        help_text="value of the field",
    )

    report_db = models.CharField(
        max_length=255,
        verbose_name="Report database name",
        null=True,
        blank=True
    )

    class Meta:
        db_table = "favorite_reports"

import django_filters

from documents.models import Document


class DocumentFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr="icontains")
    uploaded_by = django_filters.CharFilter(field_name="uploaded_by__username")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Document
        fields = ["title", "uploaded_by", "created_after", "created_before"]

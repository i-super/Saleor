import bleach
from django import forms
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.forms.models import ModelChoiceIterator
from django.forms.widgets import CheckboxSelectMultiple
from django.utils.text import slugify
from django.utils.translation import pgettext_lazy
from django_prices.forms import MoneyField
from mptt.forms import TreeNodeChoiceField

from ...core.taxes import include_taxes_in_prices, zero_money
from ...core.weight import WeightField
from ...extensions.manager import get_extensions_manager
from ...product.models import (
    Attribute,
    AttributeValue,
    Category,
    Collection,
    Product,
    ProductImage,
    ProductType,
    ProductVariant,
    VariantImage,
)
from ...product.tasks import (
    update_product_minimal_variant_price_task,
    update_variants_names,
)
from ...product.thumbnails import create_product_thumbnails
from ...product.utils.attributes import (
    associate_attribute_values_to_instance,
    generate_name_for_variant,
)
from ..forms import (
    ModelChoiceOrCreationField,
    MoneyModelForm,
    OrderedModelMultipleChoiceField,
)
from ..seo.fields import SeoDescriptionField, SeoTitleField
from ..seo.utils import prepare_seo_description
from ..widgets import RichTextEditorWidget
from . import ProductBulkAction
from .utils import get_product_tax_rate
from .widgets import ImagePreviewWidget


def make_money_field():
    return MoneyField(
        available_currencies=settings.AVAILABLE_CURRENCIES,
        min_values=[zero_money()],
        max_digits=settings.DEFAULT_MAX_DIGITS,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES,
        required=False,
    )


class RichTextField(forms.CharField):
    """A field for rich text editor, providing backend sanitization."""

    widget = RichTextEditorWidget

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.help_text = pgettext_lazy(
            "Help text in rich-text editor field",
            "Select text to enable text-formatting tools.",
        )

    def to_python(self, value):
        tags = settings.ALLOWED_TAGS or bleach.ALLOWED_TAGS
        attributes = settings.ALLOWED_ATTRIBUTES or bleach.ALLOWED_ATTRIBUTES
        styles = settings.ALLOWED_STYLES or bleach.ALLOWED_STYLES
        value = super().to_python(value)
        value = bleach.clean(value, tags=tags, attributes=attributes, styles=styles)
        return value


class ProductTypeSelectorForm(forms.Form):
    """Form that allows selecting product type."""

    product_type = forms.ModelChoiceField(
        queryset=ProductType.objects.all(),
        label=pgettext_lazy("Product type form label", "Product type"),
        widget=forms.RadioSelect,
        empty_label=None,
    )


class ProductTypeForm(forms.ModelForm):
    tax_rate = forms.ChoiceField(
        required=False, label=pgettext_lazy("Product type tax rate type", "Tax rate")
    )
    weight = WeightField(
        label=pgettext_lazy("ProductType weight", "Weight"),
        help_text=pgettext_lazy(
            "ProductVariant weight help text",
            "Default weight that will be used for calculating shipping"
            " price for products of that type.",
        ),
    )
    product_attributes = forms.ModelMultipleChoiceField(
        queryset=Attribute.objects.none(),
        required=False,
        label=pgettext_lazy(
            "Product type attributes", "Attributes common to all variants."
        ),
    )
    variant_attributes = forms.ModelMultipleChoiceField(
        queryset=Attribute.objects.none(),
        required=False,
        label=pgettext_lazy(
            "Product type attributes", "Attributes specific to each variant."
        ),
    )

    class Meta:
        model = ProductType
        exclude = []
        labels = {
            "name": pgettext_lazy("Item name", "Name"),
            "has_variants": pgettext_lazy("Enable variants", "Enable variants"),
            "is_shipping_required": pgettext_lazy(
                "Shipping toggle", "Require shipping"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        manager = get_extensions_manager()
        self.fields["tax_rate"].choices = [
            (tax.code, tax.description) for tax in manager.get_tax_rate_type_choices()
        ]
        variant_attrs_qs = product_attrs_qs = Attribute.objects.all()

        if self.instance.pk:
            product_attrs_initial = (
                self.instance.product_attributes.all().product_attributes_sorted()
            )
            variant_attrs_initial = (
                self.instance.variant_attributes.all().variant_attributes_sorted()
            )
        else:
            product_attrs_initial = []
            variant_attrs_initial = []

        self.fields["product_attributes"].queryset = product_attrs_qs
        self.fields["variant_attributes"].queryset = variant_attrs_qs
        self.fields["product_attributes"].initial = product_attrs_initial
        self.fields["variant_attributes"].initial = variant_attrs_initial

    def clean(self):
        data = super().clean()
        has_variants = self.cleaned_data["has_variants"]
        product_attr = set(self.cleaned_data.get("product_attributes", []))
        variant_attr = set(self.cleaned_data.get("variant_attributes", []))
        if not has_variants and variant_attr:
            msg = pgettext_lazy(
                "Product type form error", "Product variants are disabled."
            )
            self.add_error("variant_attributes", msg)
        if product_attr & variant_attr:
            msg = pgettext_lazy(
                "Product type form error",
                "A single attribute can't belong to both a product " "and its variant.",
            )
            self.add_error("variant_attributes", msg)

        if not self.instance.pk:
            return data

        self.check_if_variants_changed(has_variants)
        variant_attr_ids = [attr.pk for attr in variant_attr]
        update_variants_names.delay(self.instance.pk, variant_attr_ids)
        return data

    def check_if_variants_changed(self, has_variants):
        variants_changed = self.fields["has_variants"].initial != has_variants
        if variants_changed:
            query = self.instance.products.all()
            query = query.annotate(variants_counter=Count("variants"))
            query = query.filter(variants_counter__gt=1)
            if query.exists():
                msg = pgettext_lazy(
                    "Product type form error",
                    "Some products of this type have more than " "one variant.",
                )
                self.add_error("has_variants", msg)

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        new_product_attrs = self.cleaned_data.get("product_attributes", [])
        new_variant_attrs = self.cleaned_data.get("variant_attributes", [])
        instance.product_attributes.set(new_product_attrs)
        instance.variant_attributes.set(new_variant_attrs)
        return instance


class AttributesMixin:
    """Form mixin that dynamically adds attribute fields."""

    available_attributes = Attribute.objects.none()

    def prepare_fields_for_attributes(self):
        initial_attrs = self.instance.attributes

        for attribute in self.available_attributes:

            attribute_rel = initial_attrs.filter(
                assignment__attribute_id=attribute.pk
            ).first()
            initial = None if attribute_rel is None else attribute_rel.values.first()

            field_defaults = {
                "label": attribute.name,
                "required": False,
                "initial": initial,
            }

            if attribute.has_values():
                field = ModelChoiceOrCreationField(
                    queryset=attribute.values.all(), **field_defaults
                )
            else:
                field = forms.CharField(**field_defaults)

            self.fields[attribute.get_formfield_name()] = field

    def iter_attribute_fields(self):
        """In use in templates to retrieve the attributes input fields."""
        for attr in self.available_attributes:
            yield self[attr.get_formfield_name()]

    def save_attributes(self):
        assert self.instance.pk is not None, "The instance must be saved first"

        for attr in self.available_attributes:
            value = self.cleaned_data.pop(attr.get_formfield_name())

            # Skip if no value was supplied for that attribute
            if not value:
                continue

            # If the passed attribute value is a string, create the attribute value.
            if not isinstance(value, AttributeValue):
                value = AttributeValue.objects.create(
                    attribute_id=attr.pk, name=value, slug=slugify(value)
                )

            associate_attribute_values_to_instance(self.instance, attr, value)


class ProductForm(MoneyModelForm, AttributesMixin):
    tax_rate = forms.ChoiceField(
        required=False,
        label=pgettext_lazy("Product tax rate type", "Tax rate"),
        help_text=pgettext_lazy(
            "Help text for the tax rate field over the product update/create form",
            (
                "Make sure you have enabled a VAT provider and fetched the rates if "
                "needed by the plugin."
            ),
        ),
    )
    category = TreeNodeChoiceField(
        queryset=Category.objects.all(), label=pgettext_lazy("Category", "Category")
    )
    collections = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Collection.objects.all(),
        label=pgettext_lazy("Add to collection select", "Collections"),
    )
    description = RichTextField(
        label=pgettext_lazy("Description", "Description"), required=True
    )
    weight = WeightField(
        required=False,
        label=pgettext_lazy("ProductType weight", "Weight"),
        help_text=pgettext_lazy(
            "Product weight field help text",
            "Weight will be used to calculate shipping price, "
            "if empty, equal to default value used on the ProductType.",
        ),
    )
    price = make_money_field()

    class Meta:
        model = Product
        exclude = [
            "attributes",
            "product_type",
            "updated_at",
            "description_json",
            "price_amount",
            "currency",
            "minimal_variant_price_amount",
        ]
        labels = {
            "name": pgettext_lazy("Item name", "Name"),
            "publication_date": pgettext_lazy(
                "Availability date", "Publish product on"
            ),
            "is_published": pgettext_lazy("Product published toggle", "Published"),
            "charge_taxes": pgettext_lazy(
                "Charge taxes on product", "Charge taxes on this product"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = get_extensions_manager()
        product_type = self.instance.product_type
        self.initial["tax_rate"] = get_product_tax_rate(self.instance, self.manager)
        self.available_attributes = product_type.product_attributes.prefetch_related(
            "values"
        ).product_attributes_sorted()
        self.prepare_fields_for_attributes()
        self.fields["collections"].initial = Collection.objects.filter(
            products__name=self.instance
        )
        self.fields["seo_description"] = SeoDescriptionField(
            extra_attrs={
                "data-bind": self["description"].auto_id,
                "data-materialize": self["description"].html_name,
            }
        )
        self.fields["seo_title"] = SeoTitleField(
            extra_attrs={"data-bind": self["name"].auto_id}
        )
        tax_rate_field = self.fields["tax_rate"]
        tax_rate_field.choices = [
            (tax.code, tax.description)
            for tax in self.manager.get_tax_rate_type_choices()
        ]

        if not tax_rate_field.choices:
            tax_rate_field.disabled = True

        if include_taxes_in_prices():
            self.fields["price"].label = pgettext_lazy(
                "Currency gross amount", "Gross price"
            )
        else:
            self.fields["price"].label = pgettext_lazy(
                "Currency net amount", "Net price"
            )

        if not product_type.is_shipping_required:
            del self.fields["weight"]
        else:
            self.fields["weight"].widget.attrs[
                "placeholder"
            ] = product_type.weight.value

        self.fields["price"].required = True

    def clean_seo_description(self):
        seo_description = prepare_seo_description(
            seo_description=self.cleaned_data["seo_description"],
            html_description=self.data["description"],
            max_length=self.fields["seo_description"].max_length,
        )
        return seo_description

    def save(self, commit=True):
        assert commit is True, "Commit is required to build the M2M structure"

        with transaction.atomic():
            super().save()

            self.save_attributes()
            self.instance.collections.clear()

            for collection in self.cleaned_data["collections"]:
                self.instance.collections.add(collection)

            tax_rate = self.cleaned_data.get("tax_rate")
            if tax_rate:
                self.manager.assign_tax_code_to_object_meta(self.instance, tax_rate)

        update_product_minimal_variant_price_task.delay(self.instance.pk)
        return self.instance


class ProductVariantForm(MoneyModelForm, AttributesMixin):
    weight = WeightField(
        required=False,
        label=pgettext_lazy("ProductVariant weight", "Weight"),
        help_text=pgettext_lazy(
            "ProductVariant weight help text",
            "Weight will be used to calculate shipping price. "
            "If empty, weight from Product or ProductType will be used.",
        ),
    )
    price_override = make_money_field()
    cost_price = make_money_field()

    class Meta:
        model = ProductVariant
        fields = [
            "sku",
            "price_override",
            "weight",
            "quantity",
            "cost_price",
            "track_inventory",
        ]
        labels = {
            "sku": pgettext_lazy("SKU", "SKU"),
            "quantity": pgettext_lazy("Integer number", "Number in stock"),
            "track_inventory": pgettext_lazy(
                "Track inventory field", "Track inventory"
            ),
        }
        help_texts = {
            "track_inventory": pgettext_lazy(
                "product variant handle stock field help text",
                "Automatically track this product's inventory",
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.product.pk:
            self.fields["price_override"].widget.attrs[
                "placeholder"
            ] = self.instance.product.price.amount
            qs = self.instance.product.product_type.variant_attributes
            self.available_attributes = qs.prefetch_related(
                "values"
            ).variant_attributes_sorted()
            self.prepare_fields_for_attributes()

        if include_taxes_in_prices():
            self.fields["price_override"].label = pgettext_lazy(
                "Override price", "Selling gross price override"
            )
            self.fields["cost_price"].label = pgettext_lazy(
                "Currency amount", "Cost gross price"
            )
        else:
            self.fields["price_override"].label = pgettext_lazy(
                "Override price", "Selling net price override"
            )
            self.fields["cost_price"].label = pgettext_lazy(
                "Currency amount", "Cost net price"
            )

        if not self.instance.product.product_type.is_shipping_required:
            del self.fields["weight"]
        else:
            self.fields["weight"].widget.attrs["placeholder"] = (
                getattr(self.instance.product.weight, "value", None)
                or self.instance.product.product_type.weight.value
            )

    @transaction.atomic
    def save(self, commit=True):
        assert commit is True, "Commit is required to build the M2M structure"

        # We need to save first to create the attribute mapping
        # and then to update the price cache
        super().save()

        self.save_attributes()

        self.instance.name = generate_name_for_variant(self.instance)
        self.instance.save(update_fields=["name"])

        update_product_minimal_variant_price_task.delay(self.instance.product_id)
        return self.instance


class CachingModelChoiceIterator(ModelChoiceIterator):
    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        for obj in self.queryset:
            yield self.choice(obj)


class CachingModelChoiceField(forms.ModelChoiceField):
    def _get_choices(self):
        if hasattr(self, "_choices"):
            return self._choices
        return CachingModelChoiceIterator(self)

    choices = property(_get_choices, forms.ChoiceField._set_choices)


class VariantBulkDeleteForm(forms.Form):
    items = forms.ModelMultipleChoiceField(queryset=ProductVariant.objects)

    def delete(self):
        items = ProductVariant.objects.filter(pk__in=self.cleaned_data["items"])
        items.delete()


class ProductImageForm(forms.ModelForm):
    use_required_attribute = False
    variants = forms.ModelMultipleChoiceField(
        queryset=ProductVariant.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = ProductImage
        exclude = ("product", "sort_order")
        labels = {
            "image": pgettext_lazy("Product image", "Image"),
            "alt": pgettext_lazy("Description", "Description"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.image:
            self.fields["image"].widget = ImagePreviewWidget()

    def save(self, commit=True):
        image = super().save(commit=commit)
        create_product_thumbnails.delay(image.pk)
        return image


class VariantImagesSelectForm(forms.Form):
    images = forms.ModelMultipleChoiceField(
        queryset=VariantImage.objects.none(),
        widget=CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.variant = kwargs.pop("variant")
        super().__init__(*args, **kwargs)
        self.fields["images"].queryset = self.variant.product.images.all()
        self.fields["images"].initial = self.variant.images.all()

    def save(self):
        images = []
        self.variant.images.clear()
        for image in self.cleaned_data["images"]:
            images.append(VariantImage(variant=self.variant, image=image))
        VariantImage.objects.bulk_create(images)


class AttributeForm(forms.ModelForm):
    class Meta:
        model = Attribute
        fields = ["name", "slug"]
        labels = {
            "name": pgettext_lazy("Product display name", "Display name"),
            "slug": pgettext_lazy("Product internal name", "Internal name"),
        }


class AttributeValueForm(forms.ModelForm):
    class Meta:
        model = AttributeValue
        fields = ["attribute", "name"]
        widgets = {"attribute": forms.widgets.HiddenInput()}
        labels = {"name": pgettext_lazy("Item name", "Name")}

    def save(self, commit=True):
        self.instance.slug = slugify(self.instance.name)
        return super().save(commit=commit)


class ReorderAttributeValuesForm(forms.ModelForm):
    ordered_values = OrderedModelMultipleChoiceField(
        queryset=AttributeValue.objects.none()
    )

    class Meta:
        model = Attribute
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields["ordered_values"].queryset = self.instance.values.all()

    def save(self):
        for order, value in enumerate(self.cleaned_data["ordered_values"]):
            value.sort_order = order
            value.save()
        return self.instance


class ReorderProductImagesForm(forms.ModelForm):
    ordered_images = OrderedModelMultipleChoiceField(
        queryset=ProductImage.objects.none()
    )

    class Meta:
        model = Product
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields["ordered_images"].queryset = self.instance.images.all()

    def save(self):
        for order, image in enumerate(self.cleaned_data["ordered_images"]):
            image.sort_order = order
            image.save()
        return self.instance


class UploadImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ("image",)
        labels = {"image": pgettext_lazy("Product image", "Image")}

    def __init__(self, *args, **kwargs):
        product = kwargs.pop("product")
        super().__init__(*args, **kwargs)
        self.instance.product = product

    def save(self, commit=True):
        image = super().save(commit=commit)
        create_product_thumbnails.delay(image.pk)
        return image


class ProductBulkUpdate(forms.Form):
    """Perform one selected bulk action on all selected products."""

    action = forms.ChoiceField(choices=ProductBulkAction.CHOICES)
    products = forms.ModelMultipleChoiceField(queryset=Product.objects.all())

    def save(self):
        action = self.cleaned_data["action"]
        if action == ProductBulkAction.PUBLISH:
            self._publish_products()
        elif action == ProductBulkAction.UNPUBLISH:
            self._unpublish_products()

    def _publish_products(self):
        self.cleaned_data["products"].update(is_published=True)

    def _unpublish_products(self):
        self.cleaned_data["products"].update(is_published=False)

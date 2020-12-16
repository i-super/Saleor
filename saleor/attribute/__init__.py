class AttributeInputType:
    """The type that we expect to render the attribute's values as."""

    DROPDOWN = "dropdown"
    MULTISELECT = "multiselect"
    FILE = "file"
    REFERENCE = "reference"

    CHOICES = [
        (DROPDOWN, "Dropdown"),
        (MULTISELECT, "Multi Select"),
        (FILE, "File"),
        (REFERENCE, "Reference"),
    ]
    # list of the input types that can be used in variant selection
    ALLOWED_IN_VARIANT_SELECTION = [DROPDOWN]


class AttributeType:
    PRODUCT_TYPE = "product-type"
    PAGE_TYPE = "page-type"

    CHOICES = [(PRODUCT_TYPE, "Product type"), (PAGE_TYPE, "Page type")]


class AttributeEntityType:
    PAGE = "page"

    CHOICES = [(PAGE, "Page")]

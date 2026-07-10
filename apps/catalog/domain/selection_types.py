from dataclasses import dataclass

from apps.catalog.models import Option, OptionGroup, ProductOptionGroup


@dataclass(frozen=True)
class SelectedOptionEntry:
    option: Option
    quantity: int
    group: OptionGroup
    link: ProductOptionGroup

"""
models/__init__.py
==================
Imports all ORM models so that SQLAlchemy's metadata registry is populated
when init_db() calls Base.metadata.create_all().
"""

from backend_anti_gravity.app.models.auth import Role, User, UserRole  # noqa: F401
from backend_anti_gravity.app.models.inventory import (  # noqa: F401
    Inventory,
    InventoryMovement,
    Product,
    ProductSupplier,
)
from backend_anti_gravity.app.models.procurement import (  # noqa: F401
    ProcurementDecision,
    PurchaseOrder,
    Supplier,
)
from backend_anti_gravity.app.models.logistics import Shipment, ServiceableCity  # noqa: F401
from backend_anti_gravity.app.models.analytics import (  # noqa: F401
    KpiDefinition,
    Review,
    Return,
    Sale,
)

# Keep backward-compatible alias
ProductReview = Review

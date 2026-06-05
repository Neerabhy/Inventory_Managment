"""
models/__init__.py
==================
Imports all ORM models so that SQLAlchemy's metadata registry is populated
when init_db() calls Base.metadata.create_all().
"""

from .auth import Role, User, UserRole  # noqa: F401
from .inventory import (  # noqa: F401
    Inventory,
    InventoryMovement,
    Product,
    ProductSupplier,
)
from .procurement import (  # noqa: F401
    ProcurementDecision,
    PurchaseOrder,
    Supplier,
)
from .logistics import InboundOrder, ServiceableCity, Shipment  # noqa: F401
from .analytics import (  # noqa: F401
    AiInsightCache,
    KpiDefinition,
    Return,
    ReturnHistory,
    Review,
    Sale,
)
from .predictions import (  # noqa: F401
    InventoryReorderPlan,
    ReturnRiskPrediction,
    SalesFeature,
    SalesForecast,
    VendorRecommendation,
)

# Keep backward-compatible alias
ProductReview = Review

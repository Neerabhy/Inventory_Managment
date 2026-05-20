from app.core.database import Base
from app.models.auth import User
from app.models.inventory import Product, Inventory, InventoryMovement
from app.models.procurement import Supplier, ProductSupplier, WarehouseSupplier, PurchaseOrder, ProcurementDecision
from app.models.logistics import Warehouse, ServiceableCity, Shipment
from app.models.analytics import Customer, Sales, ReturnRecords, Review, KpiDefinition

# Exporting components to ensure visibility by Alembic or application initialization tools
__all__ = [
    "Base",
    "User",
    "Product",
    "Inventory",
    "InventoryMovement",
    "Supplier",
    "ProductSupplier",
    "WarehouseSupplier",
    "PurchaseOrder",
    "ProcurementDecision",
    "Warehouse",
    "ServiceableCity",
    "Shipment",
    "Customer",
    "Sales",
    "ReturnRecords",
    "Review",
    "KpiDefinition",
]
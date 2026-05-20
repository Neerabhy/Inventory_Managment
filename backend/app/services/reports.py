import pandas as pd
import io
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.analytics import Sales, ReturnRecords

class ReportGenerator:
    """Enterprise report streaming engine using Pandas."""
    
    @staticmethod
    async def generate_sales_csv(db: AsyncSession) -> io.BytesIO:
        """Extracts sales history and converts to a downloadable CSV byte stream."""
        result = await db.execute(select(Sales))
        sales_records = result.scalars().all()
        
        # Convert SQLAlchemy models to dictionaries
        data = [{
            "Invoice Number": s.invoice_number,
            "Product ID": s.product_id,
            "Customer ID": s.customer_id,
            "Quantity": s.quantity_sold,
            "Revenue": s.revenue_generated,
            "Sale Date": s.sale_date.strftime("%Y-%m-%d %H:%M:%S")
        } for s in sales_records]
        
        if not data:
            # Fallback empty dataframe structure
            df = pd.DataFrame(columns=["Invoice Number", "Product ID", "Customer ID", "Quantity", "Revenue", "Sale Date"])
        else:
            df = pd.DataFrame(data)
            
        # Write to memory buffer
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        
        # Convert string buffer to bytes buffer for FastAPI StreamingResponse
        byte_stream = io.BytesIO(stream.getvalue().encode('utf-8'))
        return byte_stream
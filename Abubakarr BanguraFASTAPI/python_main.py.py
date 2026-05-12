from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import asyncio
import uvicorn

# ========== Type Annotated Models ==========
class Book(BaseModel):
    id: int
    title: str
    author: str
    category: str
    available: bool

class BorrowRequest(BaseModel):
    user_id: str
    book_id: int

class ReturnRequest(BaseModel):
    user_id: str
    book_id: int

class BorrowRecord(BaseModel):
    user_id: str
    book_id: int
    borrow_date: datetime
    due_date: datetime

class FineResponse(BaseModel):
    user_id: str
    total_fine: float
    overdue_books: List[Dict]

# ========== Mock Database ==========
books_db: Dict[int, Book] = {
    1: Book(id=1, title="Python Programming", author="John Smith", category="Programming", available=True),
    2: Book(id=2, title="Data Science 101", author="Jane Doe", category="Data", available=False),
    3: Book(id=3, title="API Design", author="Bob Lee", category="Web", available=True),
}

borrow_records: List[BorrowRecord] = []
fines_db: Dict[str, float] = {}

# Helper function
def calculate_fine(due_date: datetime) -> float:
    days_overdue = (datetime.now() - due_date).days
    return max(0, days_overdue * 0.50)  # 50 cents per day

# ========== FastAPI App ==========
app = FastAPI(title="Limkokwing Library API", description="Basic API for library management")

# 1. GET /books - Search books
@app.get("/books", response_model=List[Book])
async def search_books(
    title: Optional[str] = Query(None, description="Search by title"),
    author: Optional[str] = Query(None, description="Search by author"),
    category: Optional[str] = Query(None, description="Search by category")
) -> List[Book]:
    """Search for books by title, author, or category"""
    await asyncio.sleep(0.1)  # Simulate async DB call
    
    results = list(books_db.values())
    
    if title:
        results = [b for b in results if title.lower() in b.title.lower()]
    if author:
        results = [b for b in results if author.lower() in b.author.lower()]
    if category:
        results = [b for b in results if category.lower() in b.category.lower()]
    
    return results

# 2. POST /borrow - Borrow a book (async with lock simulation)
@app.post("/borrow")
async def borrow_book(request: BorrowRequest) -> Dict:
    """Borrow a book asynchronously"""
    await asyncio.sleep(0.2)  # Simulate async operation
    
    if request.book_id not in books_db:
        raise HTTPException(status_code=404, detail="Book not found")
    
    book = books_db[request.book_id]
    if not book.available:
        raise HTTPException(status_code=400, detail="Book already borrowed")
    
    # Update availability
    book.available = False
    books_db[request.book_id] = book
    
    # Create borrow record
    due_date = datetime.now() + timedelta(days=14)
    borrow_records.append(BorrowRecord(
        user_id=request.user_id,
        book_id=request.book_id,
        borrow_date=datetime.now(),
        due_date=due_date
    ))
    
    return {"message": "Book borrowed successfully", "due_date": due_date.isoformat()}

# 3. POST /return - Return a book
@app.post("/return")
async def return_book(request: ReturnRequest) -> Dict:
    """Return a borrowed book and calculate fine if overdue"""
    await asyncio.sleep(0.2)
    
    # Find borrow record
    record = None
    for r in borrow_records:
        if r.user_id == request.user_id and r.book_id == request.book_id:
            record = r
            break
    
    if not record:
        raise HTTPException(status_code=404, detail="No borrow record found")
    
    # Calculate fine
    fine = calculate_fine(record.due_date)
    if fine > 0:
        fines_db[request.user_id] = fines_db.get(request.user_id, 0) + fine
    
    # Remove record and make book available
    borrow_records.remove(record)
    books_db[request.book_id].available = True
    
    return {"message": "Book returned", "fine": fine}

# 4. GET /users/{user_id}/fines - Track fines
@app.get("/users/{user_id}/fines", response_model=FineResponse)
async def get_user_fines(user_id: str) -> FineResponse:
    """Get overdue books and total fines for a user"""
    await asyncio.sleep(0.1)
    
    overdue_books = []
    for record in borrow_records:
        if record.user_id == user_id and datetime.now() > record.due_date:
            days_overdue = (datetime.now() - record.due_date).days
            overdue_books.append({
                "book_id": record.book_id,
                "days_overdue": days_overdue
            })
    
    return FineResponse(
        user_id=user_id,
        total_fine=fines_db.get(user_id, 0),
        overdue_books=overdue_books
    )

# Simulate multiple users borrowing at the same time
@app.post("/simulate_concurrent")
async def simulate_concurrent_borrows() -> Dict:
    """Demonstrate async handling of multiple users"""
    
    async def borrow_for_user(user_id: str, book_id: int):
        try:
            result = await borrow_book(BorrowRequest(user_id=user_id, book_id=book_id))
            return f"{user_id}: {result['message']}"
        except HTTPException as e:
            return f"{user_id}: Failed - {e.detail}"
    
    # Simulate 3 users borrowing simultaneously
    tasks = [
        borrow_for_user("U001", 1),
        borrow_for_user("U002", 3),
        borrow_for_user("U003", 1)  # This will fail because book 1 is taken
    ]
    
    results = await asyncio.gather(*tasks)
    return {"concurrent_results": results}

# ========== Run Server ==========
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
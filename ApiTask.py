from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from datetime import date as dt_date
from pydantic import BaseModel
from typing import List, Optional

DATABASE_URL = "sqlite:///./expenses.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
app = FastAPI()

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    category = Column(String, index=True)
    amount = Column(Float, index=True)
    date = Column(Date, default=dt_date.today)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ExpenseCreate(BaseModel):
    title: str
    category: str
    amount: float
    date: Optional[dt_date] = None

class ExpenseUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[dt_date] = None

class ExpenseResponse(BaseModel):
    id: int
    title: str
    category: str
    amount: float
    date: dt_date
    class Config:
        from_attributes = True

@app.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    exp_date = expense.date or dt_date.today()
    db_expense = Expense(title=expense.title, category=expense.category, amount=expense.amount, date=exp_date)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/expenses", response_model=List[ExpenseResponse], status_code=status.HTTP_200_OK)
def get_expenses(category: Optional[str] = None, sort: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Expense)
    if category:
        query = query.filter(Expense.category.ilike(f"%{category}%"))
    if sort == "amount":
        query = query.order_by(Expense.amount)
    elif sort == "date":
        query = query.order_by(Expense.date)
    expenses = query.all()
    if not expenses:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT, detail="No expenses found")
    return expenses

@app.get("/expenses/summary", status_code=status.HTTP_200_OK)
def get_summary(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit
    result = (
        db.query(Expense.category, func.sum(Expense.amount).label("total_amount"))
        .group_by(Expense.category)
        .offset(offset)
        .limit(limit)
        .all()
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT, detail="No data found")
    return [{"category": r[0], "total_amount": r[1]} for r in result]

@app.put("/expenses/{id}", response_model=ExpenseResponse, status_code=status.HTTP_202_ACCEPTED)
def update_expense(id: int, expense: ExpenseUpdate, db: Session = Depends(get_db)):
    db_expense = db.query(Expense).filter(Expense.id == id).first()
    if not db_expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.title is not None:
        db_expense.title = expense.title
    if expense.category is not None:
        db_expense.category = expense.category
    if expense.amount is not None:
        db_expense.amount = expense.amount
    if expense.date is not None:
        db_expense.date = expense.date
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.delete("/expenses/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(id: int, db: Session = Depends(get_db)):
    db_expense = db.query(Expense).filter(Expense.id == id).first()
    if not db_expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    db.delete(db_expense)
    db.commit()
    return

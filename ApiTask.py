from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, func
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from pydantic import BaseModel, ConfigDict
import datetime
from typing import Optional, List

DATABASE_URL = "sqlite:///./expenses.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    category = Column(String, index=True)
    amount = Column(Float)
    date = Column(Date, default=datetime.date.today)

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
    date: Optional[datetime.date] = None

class ExpenseResponse(BaseModel):
    id: int
    title: str
    category: str
    amount: float
    date: datetime.date
    model_config = ConfigDict(from_attributes=True)

class ExpenseUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[datetime.date] = None

class SummaryResponse(BaseModel):
    category: str
    total_amount: float
    model_config = ConfigDict(from_attributes=True)

@app.post("/expenses/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    new_expense = Expense(
        title=expense.title,
        category=expense.category,
        amount=expense.amount,
        date=expense.date or datetime.date.today()
    )
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    return new_expense

@app.get("/expenses/", response_model=List[ExpenseResponse], status_code=status.HTTP_200_OK)
def get_expenses(category: Optional[str] = None, sort: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Expense)
    if category:
        query = query.filter(Expense.category == category)
    if sort == "amount":
        query = query.order_by(Expense.amount)
    elif sort == "date":
        query = query.order_by(Expense.date)
    expenses = query.all()
    if not expenses:
        raise HTTPException(status_code=404, detail="No expenses found")
    return expenses

@app.get("/expenses/{expense_id}", response_model=ExpenseResponse, status_code=status.HTTP_200_OK)
def get_expense_by_id(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense

@app.put("/expenses/{expense_id}", response_model=ExpenseResponse, status_code=status.HTTP_200_OK)
def update_expense(expense_id: int, expense: ExpenseUpdate, db: Session = Depends(get_db)):
    db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for field, value in expense.dict(exclude_unset=True).items():
        setattr(db_expense, field, value)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(db_expense)
    db.commit()
    return

@app.get("/expenses/summary", response_model=List[SummaryResponse], status_code=status.HTTP_200_OK)
def get_summary(db: Session = Depends(get_db)):
    summary = db.query(
        Expense.category,
        func.sum(Expense.amount).label("total_amount")
    ).group_by(Expense.category).all()
    if not summary:
        raise HTTPException(status_code=404, detail="No data available for summary")
    return [{"category": s[0], "total_amount": s[1]} for s in summary]

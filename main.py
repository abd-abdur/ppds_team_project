# main.py

from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    Text,
    JSON,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from typing import List, Optional
import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment variables.")

# Create the SQLAlchemy engine using MySQL dialect
engine = create_engine(DATABASE_URL, echo=True)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# SQLAlchemy Models
class Users(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    user_ip = Column(String(255))
    location = Column(String(255))
    preferences = Column(JSON, nullable=True)
    date_joined = Column(DateTime, server_default=func.now())
    
    wardrobe_items = relationship("WardrobeItems", back_populates="owner", cascade="all, delete-orphan")
    outfits = relationship("Outfit", back_populates="user", cascade="all, delete-orphan")
    e_commerce_products = relationship("ECommerceProduct", back_populates="user", cascade="all, delete-orphan")

# Additional SQLAlchemy models (WardrobeItems, Outfit, WeatherData, Fashion, ECommerceProduct) would be defined similarly.

# Create all tables
Base.metadata.create_all(bind=engine)

# Pydantic Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    location: Optional[str] = None
    preferences: Optional[List[str]] = None

    class Config:
        from_attributes = True  # Pydantic v2 replacement for orm_mode


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserResponse(UserBase):
    user_id: int
    date_joined: datetime

    class Config:
        from_attributes = True


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize FastAPI app
app = FastAPI(
    title="LazYdrobe API",
    description="API for LazYdrobe Wardrobe Management Application",
    version="1.0.0"
)


# Utility Functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# API Routes

## Users Endpoints

@app.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    hashed_pwd = hash_password(user.password)
    db_user = Users(
        username=user.username,
        email=user.email,
        password=hashed_pwd,
        location=user.location,
        preferences=user.preferences
    )
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered.")
    return db_user


@app.get("/users/", response_model=List[UserResponse])
def read_users(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    users = db.query(Users).offset(skip).limit(limit).all()
    return users


@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_update: UserBase, db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user.username = user_update.username
    user.email = user_update.email
    user.location = user_update.location
    user.preferences = user_update.preferences
    
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered.")
    
    return user


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    db.delete(user)
    db.commit()
    return

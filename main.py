# main.py

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import requests
import logging
from fastapi import BackgroundTasks 
from pydantic import AnyHttpUrl 

# Import models from models.py
from models import Base, User, EcommerceProduct, WardrobeItem, Outfit, FashionTrend, WeatherData, OutfitSuggestion

# Import fashion_trends function
from fashion_trends import fetch_and_update_fashion_trends

from outfit_suggester import suggest_outfits

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL is not set in the environment variables.")
    raise ValueError("DATABASE_URL is not set in the environment variables.")

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=False)  # Set echo to False for production

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="LazYdrobe API",
    description="API for LazYdrobe Wardrobe Management Application",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True, allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    location: str  # Now required
    preferences: Optional[List[str]] = None
    gender: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None

    class Config:
        orm_mode = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    location: Optional[str] = None
    preferences: Optional[List[str]] = None  # Expecting a list
    gender: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    height: Optional[str] = None
    weight: Optional[str] = None

    class Config:
        orm_mode = True


class UserResponse(UserBase):
    user_id: int
    date_joined: datetime

    class Config:
        orm_mode = True


# Login Schemas

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: int
    username: str
    email: EmailStr

    class Config:
        orm_mode = True


# Weather Schemas

class WeatherRequest(BaseModel):
    user_id: int 

class WeatherResponse(BaseModel):
    date: datetime
    location: str
    temp_max: float
    temp_min: float
    feels_max: float
    feels_min: float
    wind_speed: float
    humidity: float
    precipitation: float
    precipitation_probability: float
    special_condition: str
    weather_icon: str

    class Config:
        orm_mode = True

class FashionTrendResponse(BaseModel):
    trend_id: int
    trend_name: str
    trend_description: str
    date_added: datetime

    class Config:
        orm_mode = True

# Wardrobe Item Schemas

class WardrobeItemBase(BaseModel):
    clothing_type: Optional[str] = Field(..., min_length=3, max_length=50)
    for_weather: Optional[str] = None
    color: Optional[List[str]] = None
    size: Optional[str] = Field(..., min_length=1, max_length=50)
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None

    class Config:
        orm_mode = True


class WardrobeItemCreate(WardrobeItemBase):
    user_id: int


class WardrobeItemUpdate(BaseModel):
    clothing_type: Optional[str] = Field(None, min_length=3, max_length=50)
    for_weather: Optional[str] = Field(None, min_length=3, max_length=50)
    color: Optional[List[str]] = None
    size: Optional[str] = Field(None, min_length=1, max_length=50)
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None

    class Config:
        orm_mode = True
class WardrobeItemResponse(WardrobeItemBase):
    item_id: int
    clothing_type: str
    for_weather: str
    color: List[str]
    size: str
    tags: List[str]
    image_url: Optional[str] = None

    class Config:
        orm_mode = True

# Outfit

class OutfitBase(BaseModel):
    occasion: Optional[List[str]] = None
    for_weather: Optional[str] = None
    clothings: Optional[List[int]] = None
    source_url: Optional[str] = None

class OutfitCreate(OutfitBase):
    user_id: int

class OutfitResponse(OutfitBase):
    outfit_id: int
    clothings: List[int]
    occasion: List[str]
    for_weather: Optional[str]

    class Config:
        orm_mode = True

class OutfitUpdate(BaseModel):
    occasion: Optional[List[str]] = None
    for_weather: Optional[str] = None


# Outfit Suggestion - it is working now

class OutfitComponent(BaseModel):
    clothing_type: str
    item_id: int
    product_name: str
    image_url: Optional[str] = None
    eBay_link: Optional[List[str]] = None 
    gender: str
    
    class Config:
        orm_mode = True


class OutfitSuggestionResponse(BaseModel):
    suggestion_id: int
    outfit_details: List[List[OutfitComponent]]
    gender: str
    date_suggested: datetime
    image_url: Optional[AnyHttpUrl] = None

    class Config:
        orm_mode = True
        
class OutfitSuggestionRequest(BaseModel):
    user_id: int

class OutfitSuggestionCreateResponse(BaseModel):
    suggestion_id: int
    outfit_details: List[List[OutfitComponent]]
    gender: str
    date_suggested: datetime
    image_url: Optional[AnyHttpUrl] = None

    class Config:
        orm_mode = True

        
# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Utility Functions

def hash_password(password: str) -> str:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)


def get_api_key(key_name: str) -> str:
    api_key = os.getenv(key_name)
    if not api_key:
        logger.error(f"{key_name} not found in environment variables.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"{key_name} not found in environment variables.")
    return api_key

def fetch_weather_data_from_db(location: str, user_id: Optional[int] = None) -> List[dict]:
    today = datetime.utcnow().date()
    db = SessionLocal()

    weather_data = []
    logger.info(f"Fetching data from database for location: {location}")

    try:
        query = db.query(WeatherData).filter(
            WeatherData.location == location,
            WeatherData.date >= today
        ).order_by(WeatherData.date) 

        if user_id:
            query = query.filter(WeatherData.user_id == user_id)

        entries = query.limit(5).all()  # Fetch up to 5 latest days

        for entry in entries:
            weather_data.append({
                'date': entry.date,
                'location': entry.location,
                'temp_max': entry.temp_max,
                'temp_min': entry.temp_min,
                'feels_max': entry.feels_max,
                'feels_min': entry.feels_min,
                'wind_speed': entry.wind_speed,
                'humidity': entry.humidity,
                'precipitation': entry.precipitation,
                'precipitation_probability': entry.precipitation_probability,
                'special_condition': entry.special_condition,
                'weather_icon': entry.weather_icon,
            })
            logger.info(f"Obtained weather data for {entry.date}")
    except Exception as e:
        logger.error(f"Error fetching data from database: {e}")
        return []
    finally:
        db.close()

    logger.debug(f"Weather data retrieved: {weather_data}")
    if len(weather_data) == 5:
        return weather_data
    return []


def fetch_weather_data(api_key: str, location: str) -> List[dict]:
    weather_entries = fetch_weather_data_from_db(location)

    if weather_entries:
        return weather_entries

    location_encoded = requests.utils.quote(location)
    url = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location_encoded}/next5days?key={api_key}&unitGroup=us&iconSet=icons2'
    response = requests.get(url)
    logger.info("Getting weather data from API")

    if response.status_code != 200:
        error_message = response.text
        logger.error(f"Failed to fetch weather data. Status Code: {response.status_code}, Message: {error_message}")
        raise HTTPException(status_code=response.status_code, detail=error_message)

    data = response.json()
    if 'days' not in data or not data['days']:
        logger.error("No weather data available.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No weather data available.")

    weather_entries = []
    for day in data["days"]:
        weather_entry = {
            'date': datetime.strptime(day['datetime'], "%Y-%m-%d").date(),  # Ensure 'date' is a date object
            'location': location,
            'temp_max': day.get('tempmax', 0.0),
            'temp_min': day.get('tempmin', 0.0),
            'feels_max': day.get('feelslikemax', 0.0),
            'feels_min': day.get('feelslikemin', 0.0),
            'wind_speed': day.get('windspeed', 0.0),
            'humidity': day.get('humidity', 0.0),
            'precipitation': day.get('precip', 0.0),
            'precipitation_probability': day.get('precipprob', 0.0),
            'special_condition': day.get('conditions', 'Unknown'),
            'weather_icon': day.get('icon', '')
        }
        weather_entries.append(weather_entry)

    return weather_entries



def insert_weather_data_to_db(data: List[dict], user_id: Optional[int] = None):
    """
    Inserts or updates weather data into the database.
    
    Args:
        data (List[dict]): List of weather data dictionaries.
        user_id (Optional[int]): ID of the user, if applicable.
    """
    db = SessionLocal()
    if not data:
        logger.info("No data to insert into the database.")
        db.close()
        return

    try:
        for entry in data:
            existing_record = db.query(WeatherData).filter_by(
                date=entry['date'], location=entry['location'], user_id=user_id
            ).first()

            if existing_record:
                # Update the existing record
                for key, value in entry.items():
                    setattr(existing_record, key, value)
                logger.info(f"Updated existing weather record for {entry['date']} at {entry['location']}.")
            else:
                # Insert new record
                weather_record = WeatherData(
                    date=entry['date'],
                    location=entry['location'],
                    temp_max=entry['temp_max'],
                    temp_min=entry['temp_min'],
                    feels_max=entry['feels_max'],
                    feels_min=entry['feels_min'],
                    wind_speed=entry['wind_speed'],
                    humidity=entry['humidity'],
                    precipitation=entry['precipitation'],
                    precipitation_probability=entry['precipitation_probability'],
                    special_condition=entry['special_condition'],
                    weather_icon=entry['weather_icon'],
                    user_id=user_id
                )
                db.add(weather_record)
        logger.info("Weather data successfully updated or inserted into the database.")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error inserting data: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to insert weather data into the database.")
    finally:
        db.close()




# API Routes

## User Registration

@app.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Creating user with email: {user.email}")

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        logger.warning(f"Email {user.email} already registered.")
        raise HTTPException(status_code=400, detail="Email already registered.")

    if not user.location:
        logger.warning("Location not provided during user creation.")
        raise HTTPException(status_code=400, detail="Location is required.")

    # Hash the password
    hashed_password = hash_password(user.password)

    # Create User instance
    db_user = User(
        username=user.username,
        email=user.email,
        password=hashed_password,
        location=user.location,  # Now required
        preferences=user.preferences,
        gender=user.gender,
        height=user.height,
        weight=user.weight
    )

    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
        logger.info(f"User {user.email} created successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

    return db_user



## User Login

@app.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    logger.info(f"Attempting login for email: {request.email}")

    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        logger.warning(f"Login failed for email: {request.email} - User not found.")
        raise HTTPException(status_code=400, detail="Invalid email or password.")

    if not verify_password(request.password, user.password):
        logger.warning(f"Login failed for email: {request.email} - Incorrect password.")
        raise HTTPException(status_code=400, detail="Invalid email or password.")

    logger.info(f"User {request.email} logged in successfully.")
    return LoginResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email
    )


## Get User by ID

@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching user with ID: {user_id}")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        logger.warning(f"User with ID {user_id} not found.")
        raise HTTPException(status_code=404, detail="User not found.")

    logger.info(f"User with ID {user_id} retrieved successfully.")
    return user


## Update User Information

@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_update: UserUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    logger.info(f"Updating user with ID: {user_id}")
    logger.debug(f"Update data received: {user_update.dict()}")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        logger.warning(f"User with ID {user_id} not found.")
        raise HTTPException(status_code=404, detail="User not found.")

    # Determine if location is being updated
    location_updated = False
    old_location = user.location
    if user_update.location and user_update.location != user.location:
        location_updated = True
        logger.info(f"User ID {user_id} location updated from '{old_location}' to '{user_update.location}'.")

    # If password is being updated, hash it
    if user_update.password:
        logger.debug("Updating password.")
        user.password = hash_password(user_update.password)

    # Update other fields if provided
    update_data = user_update.dict(exclude_unset=True, exclude={"password"})
    logger.debug(f"Updating fields: {update_data}")
    for key, value in update_data.items():
        setattr(user, key, value)

    try:
        db.commit()
        db.refresh(user)
        logger.info(f"User with ID {user_id} updated successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")

    # If location was updated, fetch and insert new weather data
    if location_updated:
        try:
            logger.info(f"Fetching and inserting weather data for new location '{user.location}'.")
            api_key = get_api_key('VISUAL_CROSSING_API_KEY')
            weather_data = fetch_weather_data(api_key, user.location)
            insert_weather_data_to_db(weather_data, user_id=user_id)
            logger.info(f"Weather data for location '{user.location}' inserted successfully.")
        except HTTPException as he:
            logger.error(f"HTTPException during weather data fetch: {he.detail}")
            raise HTTPException(status_code=500, detail="Failed to fetch and insert weather data after location update.")
        except Exception as e:
            logger.error(f"Unexpected error during weather data fetch: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching weather data after location update.")

    return user


## Delete User

@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deleting user with ID: {user_id}")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        logger.warning(f"User with ID {user_id} not found.")
        raise HTTPException(status_code=404, detail="User not found.")

    try:
        db.delete(user)
        db.commit()
        logger.info(f"User with ID {user_id} deleted successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")

    return


## Create Wardrobe Item

@app.post("/wardrobe_item/", response_model=WardrobeItemResponse, status_code=status.HTTP_201_CREATED)
def create_wardrobe_item(item: WardrobeItemCreate, db: Session = Depends(get_db)):
    logger.info(f"Adding wardrobe item for user ID: {item.user_id}")

    # Create a new WardrobeItem instance
    db_item = WardrobeItem(
        user_id=item.user_id,
        clothing_type=item.clothing_type,
        for_weather=item.for_weather,
        color=item.color,
        size=item.size,
        tags=item.tags,
        image_url=item.image_url
    )

    # Add the item to the database
    db.add(db_item)
    try:
        db.commit()
        db.refresh(db_item)
        logger.info(f"Wardrobe item with ID {db_item.item_id} created successfully.")
        return db_item
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create wardrobe item: {e}")
        raise HTTPException(status_code=500, detail="Failed to create wardrobe item.")

## Get Wardrobe Items for User

@app.get("/wardrobe_item/user/{user_id}", response_model=List[WardrobeItemResponse])
def get_all_wardrobe_items(user_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching wardrobe item for user ID: {user_id}")
    items = db.query(WardrobeItem).filter(WardrobeItem.user_id == user_id).all()
    if not items:
        raise HTTPException(status_code=404, detail="No wardrobe items found for this user.")
    return items

## Get Wardrobe Item Information

@app.get("/wardrobe_item/{item_id}", response_model=WardrobeItemResponse)
def read_wardrobe_item(item_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching wardrobe item with ID: {item_id}")

    wardrobe_item = db.query(WardrobeItem).filter(WardrobeItem.item_id == item_id).first()
    if not wardrobe_item:
        logger.warning(f"Wardrobe item with ID {item_id} not found.")
        raise HTTPException(status_code=404, detail="Wardrobe item not found.")

    logger.info(f"Wardrobe item with ID {item_id} retrieved successfully.")
    return wardrobe_item


## Update Wardrobe Item Information

@app.put("/wardrobe_item/{item_id}", response_model=WardrobeItemResponse)
def update_wardrobe_item(item_id: int, item_update: WardrobeItemUpdate, db: Session = Depends(get_db)):
    logger.info(f"Updating wardrobe item with ID: {item_id}")
    logger.debug(f"Update data received: {item_update.dict()}")

    wardrobe_item = db.query(WardrobeItem).filter(WardrobeItem.item_id == item_id).first()
    if not wardrobe_item:
        logger.warning(f"Wardrobe item with ID {item_id} not found.")
        raise HTTPException(status_code=404, detail="Wardrobe item not found.")

    # Update fields from the incoming request if they are provided
    update_data = item_update.dict(exclude_unset=True)
    logger.debug(f"Updating fields: {update_data}")
    for key, value in update_data.items():
        setattr(wardrobe_item, key, value)

    try:
        db.commit()
        db.refresh(wardrobe_item)
        logger.info(f"Wardrobe item with ID {item_id} updated successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update wardrobe item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update wardrobe item: {str(e)}")

    return wardrobe_item


## Delete Wardrobe Item

@app.delete("/wardrobe_item/", status_code=status.HTTP_204_NO_CONTENT)
def delete_wardrobe_item(item_ids: List[int] = Body(..., embed=True), db: Session = Depends(get_db)):
    logger.info(f"Deleting wardrobe item with IDs: {item_ids}")

    not_found_items = []
    for item_id in item_ids:
        wardrobe_item = db.query(WardrobeItem).filter(WardrobeItem.item_id == item_id).first()
        if not wardrobe_item:
            not_found_items.append(item_id)
        else:
            try:
                db.delete(wardrobe_item)
                db.commit()
                logger.info(f"Wardrobe item with ID {item_id} deleted successfully.")
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to delete wardrobe item with ID {item_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to delete wardrobe item with ID {item_id}: {str(e)}")

    # If there are any items not found, return a 404 error
    if not_found_items:
        raise HTTPException(status_code=404, detail=f"Wardrobe items with IDs {', '.join(map(str, not_found_items))} not found.")

    return


## Weather Endpoint

@app.post("/weather/", response_model=List[WeatherResponse], status_code=status.HTTP_200_OK)
def get_weather_data(weather_request: WeatherRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    logger.info(f"Received weather data request for user_id={weather_request.user_id}")

    user = db.query(User).filter(User.user_id == weather_request.user_id).first()
    if not user:
        logger.error(f"User with ID {weather_request.user_id} not found.")
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.location:
        logger.error(f"User with ID {weather_request.user_id} does not have a location set.")
        raise HTTPException(status_code=400, detail="User location not set.")

    location = user.location

    try:
        weather_data = fetch_weather_data_from_db(location)
        if not weather_data:
            logger.info(f"No full weather data found in DB for location: {location}")
            raise ValueError(f"No full weather data for {location} found in the database.")
    except ValueError:
        try:
            api_key = get_api_key('VISUAL_CROSSING_API_KEY')
            logger.info("Retrieved Visual Crossing API key successfully.")
        except ValueError as e:
            logger.error(f"API Key Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        try:
            weather_data = fetch_weather_data(api_key, location)
            logger.info("Fetched weather data successfully from API.")
        except HTTPException as he:
            logger.error(f"HTTPException during weather data fetch: {he.detail}")
            raise he
        except Exception as e:
            logger.error(f"Unexpected error during weather data fetch: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching weather data.")

        try:
            # Insert into DB as a background task with the provided user_id
            background_tasks.add_task(insert_weather_data_to_db, weather_data, user_id=weather_request.user_id)
            logger.info("Scheduled weather data insertion as a background task.")
        except Exception as e:
            logger.error(f"Error scheduling background task for weather data insertion: {e}")
            raise HTTPException(status_code=500, detail="Failed to schedule weather data insertion.")

    # Return the data
    logger.info("Returning weather data to the client.")
    return weather_data


## Fashion Trends Endpoints

@app.post("/fashion_trends/update", status_code=status.HTTP_202_ACCEPTED)
def update_fashion_trends_endpoint(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Endpoint to trigger the fetching and updating of fashion trends.
    """
    background_tasks.add_task(fetch_and_update_fashion_trends, db)
    logger.info("Fashion trends update initiated via API.")
    return {"message": "Fashion trends update initiated."}

@app.get("/fashion_trends/", response_model=List[FashionTrendResponse], status_code=status.HTTP_200_OK)
def get_fashion_trends(db: Session = Depends(get_db)):
    """
    Retrieve the latest fashion trends from the database.
    """
    trends = db.query(FashionTrend).order_by(FashionTrend.date_added.desc()).all()
    return trends

# Get latest 3 trends

@app.get("/fashion-trends/latest", response_model=List[FashionTrendResponse])
def get_fashion_trends(db: Session = Depends(get_db)):
    logger.info("Fetching the latest three fashion trends")
    trends = db.query(FashionTrend).order_by(FashionTrend.trend_id.desc()).limit(3).all()
    logger.debug(f"Number of trends found: {len(trends)}")
    
    if not trends:
        logger.warning("No fashion trends found in the database.")
        raise HTTPException(status_code=404, detail="No fashion trends found.")

    for trend in trends:
        logger.debug(f"Trend ID: {trend.trend_id}, Name: {trend.trend_name}, Date Added: {trend.date_added}")
    
    return trends

## Create Custom Outfit
@app.post("/outfit/", response_model=OutfitResponse, status_code=status.HTTP_201_CREATED)
def create_outfit(outfit: OutfitCreate, db: Session = Depends(get_db)):
    """
    Create a customized outfit and save it to the database
    """
    db_outfit = Outfit(
        user_id=outfit.user_id,
        occasion=outfit.occasion,
        for_weather=outfit.for_weather,
        clothings=outfit.clothings
    )

    db.add(db_outfit)
    try:
        db.commit()
        db.refresh(db_outfit)
        logger.info(f"Outfit with ID {db_outfit.outfit_id} created successfully.")
        return db_outfit
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create outfit: {e}")
        raise HTTPException(status_code=400, detail="Failed to create outfit")

## Get Outfits for User

@app.get("/outfit/user/{user_id}", response_model=List[OutfitResponse])
def get_all_outfits(user_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching outfits for user ID: {user_id}")
    outfits = db.query(Outfit).filter(Outfit.user_id == user_id).all()
    return outfits

## Get Outfit Information

@app.get("/outfit/{outfit_id}", response_model=OutfitResponse)
def read_outfit(outfit_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching outfit with ID: {outfit_id}")
    outfit = db.query(Outfit).filter(Outfit.outfit_id == outfit_id).first()

    if not outfit:
        logger.warning(f"Outfit with ID {outfit_id} not found.")
        raise HTTPException(status_code=404, detail="Outfit not found.")

    logger.info(f"Outfit with ID {outfit_id} retrieved successfully.")
    return outfit

## Delete Outfits

@app.delete("/outfit/{outfit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outfit(outfit_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deleting outfit with ID: {outfit_id}")

    outfit = db.query(Outfit).filter(Outfit.outfit_id == outfit_id).first()
    if not outfit:
        logger.warning(f"Outfit with ID {outfit_id} not found.")
        raise HTTPException(status_code=404, detail="Outfit not found.")

    try:
        db.delete(outfit)
        db.commit()
        logger.info(f"Outfit with ID {outfit_id} deleted successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete outfit with ID {outfit_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete outfit with ID {outfit_id}: {str(e)}")
    return

## Update Outfit Information

@app.put("/outfit/{outfit_id}", response_model=OutfitResponse)
def update_outfit(outfit_id: int, outfit_update: OutfitUpdate, db: Session = Depends(get_db)):
    logger.info(f"Updating outfit with ID: {outfit_id}")

    outfit = db.query(Outfit).filter(Outfit.outfit_id == outfit_id).first()
    if not outfit:
        logger.warning(f"Outfit with ID {outfit_id} not found.")
        raise HTTPException(status_code=404, detail="Outfit not found.")

    # Update fields from the incoming request if they are provided
    update_data = outfit_update.dict(exclude_unset=True)
    logger.debug(f"Updating fields: {update_data}")
    for key, value in update_data.items():
        setattr(outfit, key, value)

    try:
        db.commit()
        db.refresh(outfit)
        logger.info(f"Outfit with ID {outfit_id} updated successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update outfit: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update outfit: {str(e)}")

    return outfit


# Outfit suggest

@app.post("/outfits/suggest", response_model=OutfitSuggestionCreateResponse, status_code=status.HTTP_201_CREATED)
def suggest_outfit_endpoint(request: OutfitSuggestionRequest, db: Session = Depends(get_db)):
    """
    Suggests outfits for the user based on current weather and fashion trends.
    Does not consider the user's existing wardrobe.
    """
    logger.info(f"Received outfit suggestion request for user_id={request.user_id}")
    
    try:
        outfit_suggestion = suggest_outfits(request.user_id, db)
        logger.info(f"Outfit suggestion ID {outfit_suggestion.suggestion_id} created for user_id={request.user_id}")
        return outfit_suggestion
    except ValueError as ve:
        logger.error(f"ValueError during outfit suggestion: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during outfit suggestion: {e}")
        raise HTTPException(status_code=500, detail="Failed to suggest outfits.")


from sqlalchemy.orm import joinedload

@app.get("/outfits/suggestions/{user_id}", response_model=List[OutfitSuggestionResponse])
def get_outfit_suggestions(user_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching outfit suggestions for user ID: {user_id}")
    suggestions = db.query(OutfitSuggestion).filter(OutfitSuggestion.user_id == user_id).all()
    logger.debug(f"Number of outfit suggestions found: {len(suggestions)}")
    
    if not suggestions:
        logger.warning(f"No outfit suggestions found for user ID: {user_id}")
        raise HTTPException(status_code=404, detail="No outfit suggestions found for this user.")
    
    for suggestion in suggestions:
        logger.debug(f"Suggestion ID: {suggestion.suggestion_id}, Date: {suggestion.date_suggested}, Gender: {suggestion.gender}")
    
    return suggestions

@app.delete("/outfits/suggestions/all", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_outfit_suggestions(user_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deleting all outfit suggestions for user_id={user_id}")
    
    # Verify if the user exists
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        logger.error(f"User with ID {user_id} not found.")
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Delete all outfit suggestions for the user
    deleted = db.query(OutfitSuggestion).filter(OutfitSuggestion.user_id == user_id).delete()
    db.commit()
    logger.info(f"Deleted {deleted} outfit suggestion(s) for user_id={user_id}.")
    return

## Delete Outfit Suggestion

@app.delete("/outfits/suggestions/", status_code=status.HTTP_204_NO_CONTENT)
def delete_wardrobe_item(suggestion_id: List[int] = Body(..., embed=True), db: Session = Depends(get_db)):
    logger.info(f"Deleting outfit suggestions with IDs: {suggestion_id}")

    not_found_items = []
    for id in suggestion_id:
        suggestion = db.query(OutfitSuggestion).filter(OutfitSuggestion.suggestion_id == id).first()
        if not suggestion:
            not_found_items.append(suggestion_id)
        else:
            try:
                db.delete(suggestion)
                db.commit()
                logger.info(f"Outfit suggestions with IDs {id} deleted successfully.")
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to delete outfit suggestion with ID {id}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to delete outfit suggestion with ID {id}: {str(e)}")

    # If there are any items not found, return a 404 error
    if not_found_items:
        raise HTTPException(status_code=404, detail=f"Outfit suggestions with IDs {', '.join(map(str, not_found_items))} not found.")

    return

## Exception Handlers

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred."},
    )

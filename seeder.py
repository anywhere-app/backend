from database import SessionLocal
from models import Pin, PinCategory, Category
import random
import string
import math


db = SessionLocal()

# Bratislava bounding box
BRATISLAVA_BOUNDS = {
    'min_lat': 48.05,
    'max_lat': 48.22,
    'min_lon': 17.0,
    'max_lon': 17.20
}


def generate_bratislava_coordinates():
    """Generate random coordinates within Bratislava with realistic distribution"""
    # Weight towards city center
    center_lat, center_lon = 48.1486, 17.1077

    # Generate with normal distribution (cluster around center)
    latitude = random.gauss(center_lat, 0.04)  # Standard deviation ~4km
    longitude = random.gauss(center_lon, 0.05)

    # Ensure within bounds
    latitude = max(BRATISLAVA_BOUNDS['min_lat'], min(latitude, BRATISLAVA_BOUNDS['max_lat']))
    longitude = max(BRATISLAVA_BOUNDS['min_lon'], min(longitude, BRATISLAVA_BOUNDS['max_lon']))

    return latitude, longitude


try:
    # Create categories
    for i in range(15):
        name = ''.join(random.choices(string.ascii_letters, k=8))
        description = ''.join(random.choices(string.ascii_letters, k=70))

        db.add(Category(
            name=name,
        ))
    db.commit()

    # Get all categories
    categories = db.query(Category).all()

    # Create pins
    for i in range(15):
        title = ''.join(random.choices(string.ascii_letters, k=10))
        description = ''.join(random.choices(string.ascii_letters, k=100))

        # Generate random coordinates in Bratislava
        latitude, longitude = generate_bratislava_coordinates()

        pin = Pin(
            slug=title.lower().replace(" ", "_"),
            title=title,
            coordinates=f'POINT({longitude} {latitude})',
            description=description,
            cost=random.choice(['$', '$$', '$$$', '$$$$', None]),
            wishlist_count=random.randint(0, 100),
            visit_count=random.randint(0, 50),
            posts_count=random.randint(0, 20),
            view_count=random.randint(0, 500),
        )
        db.add(pin)
        db.flush()  # Get the pin ID

        # Assign random categories to the pin
        num_categories = random.randint(1, 3)
        selected_categories = random.sample(categories, min(num_categories, len(categories)))

        for category in selected_categories:
            db.add(PinCategory(
                pin_id=pin.id,
                category_id=category.id
            ))

    db.commit()
    print("Seeding completed successfully!")

except Exception as e:
    db.rollback()
    print(f"Error during seeding: {e}")
finally:
    db.close()
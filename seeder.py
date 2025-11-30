import json
import random
from sqlalchemy.orm import Session
from models import Pin  # Replace with your actual import


def create_slug(name, osm_id):
    """Create a unique slug from name or fallback to osm_id"""
    if name:
        return name.lower().replace(" ", "_").replace("&", "and")
    return f"location_{osm_id}"


def get_title(properties):
    """Extract title from properties"""
    if properties.get('name'):
        return properties['name']

    # Fallback to type of location
    for key in ['shop', 'amenity', 'leisure', 'tourism', 'historic']:
        if properties.get(key):
            return f"{properties[key].replace('_', ' ').title()}"

    return f"Location {properties['osm_id']}"


def get_description(properties):
    """Generate description from available properties"""
    parts = []

    if properties.get('shop'):
        parts.append(f"Shop type: {properties['shop']}")
    if properties.get('amenity'):
        parts.append(f"Amenity: {properties['amenity']}")
    if properties.get('leisure'):
        parts.append(f"Leisure: {properties['leisure']}")
    if properties.get('tourism'):
        parts.append(f"Tourism: {properties['tourism']}")
    if properties.get('opening_hours'):
        parts.append(f"Hours: {properties['opening_hours']}")
    if properties.get('religion'):
        parts.append(f"Religion: {properties['religion']}")
    if properties.get('historic'):
        parts.append(f"Historic: {properties['historic']}")

    return " | ".join(parts) if parts else "No description available"


def seed_pins_from_geojson(session: Session, geojson_path: str):
    """
    Seed the database with Pin records from a GeoJSON file

    Args:
        session: SQLAlchemy session
        geojson_path: Path to the GeoJSON file
    """
    with open(geojson_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pins_to_create = []
    skipped = 0
    errors = 0

    # First, get all existing slugs to check for duplicates
    existing_slugs = {pin.slug for pin in session.query(Pin.slug).all()}

    for feature in data['features']:
        try:
            props = feature['properties']
            coords = feature['geometry']['coordinates']
            longitude, latitude = coords[0], coords[1]

            title = get_title(props)
            slug = create_slug(props.get('name'), props['osm_id'])
            description = get_description(props)

            # Check if pin already exists
            if slug in existing_slugs:
                print(f"Skipping duplicate: {slug}")
                skipped += 1
                continue

            pin = Pin(
                slug=slug,
                title=title,
                title_image_url='',  # Empty string or use a default image URL
                coordinates=f'SRID=4326;POINT({longitude} {latitude})',  # Proper EWKT format
                description=description,
                cost=random.choice(['$', '$$', '$$$', '$$$$', None]),
                wishlist_count=random.randint(0, 100),
                visit_count=random.randint(0, 50),
                posts_count=random.randint(0, 20),
                view_count=random.randint(0, 500),
            )

            pins_to_create.append(pin)
            existing_slugs.add(slug)  # Add to set to catch duplicates in this batch

        except Exception as e:
            print(f"Error processing feature {props.get('osm_id', 'unknown')}: {e}")
            errors += 1
            continue

    # Bulk add all pins
    if pins_to_create:
        try:
            session.bulk_save_objects(pins_to_create)
            session.commit()
            print(f"\n✓ Successfully created {len(pins_to_create)} pins")
            print(f"✗ Skipped {skipped} duplicates")
            print(f"✗ Failed {errors} records")
        except Exception as e:
            session.rollback()
            print(f"Error committing transaction: {e}")
            print("Rolling back all changes")
    else:
        print("No pins to create")


# Usage example:
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Replace with your database URL
    DATABASE_URL = "postgresql://user:password@localhost/dbname"

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        seed_pins_from_geojson(db, "anywhere.geojson")
    finally:
        db.close()
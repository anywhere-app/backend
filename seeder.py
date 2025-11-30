import json
import random
from sqlalchemy.orm import Session
from models import Pin


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

    return " | ".join(parts) if parts else None


def seed_pins_from_geojson(session: Session, geojson_path: str):
    """
    Seed the database with Pin records from a GeoJSON file

    Args:
        session: SQLAlchemy session
        geojson_path: Path to the GeoJSON file
    """
    with open(geojson_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pins_created = 0

    for feature in data['features']:
        try:
            props = feature['properties']
            coords = feature['geometry']['coordinates']
            longitude, latitude = coords[0], coords[1]

            title = get_title(props)
            slug = create_slug(props.get('name'), props['osm_id'])
            description = get_description(props)

            # Check if pin already exists
            existing = session.query(Pin).filter_by(slug=slug).first()
            if existing:
                print(f"Skipping duplicate: {slug}")
                continue

            pin = Pin(
                slug=slug,
                title=title,
                coordinates=f'POINT({longitude} {latitude})',
                description=description,
                cost=random.choice(['$', '$$', '$$$', '$$$$', None]),
                wishlist_count=random.randint(0, 100),
                visit_count=random.randint(0, 50),
                posts_count=random.randint(0, 20),
                view_count=random.randint(0, 500),
            )

            session.add(pin)
            pins_created += 1

        except Exception as e:
            print(f"Error processing feature {props.get('osm_id')}: {e}")
            continue

    session.commit()
    print(f"Successfully created {pins_created} pins")


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
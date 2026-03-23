from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
import config

# Create engine
engine = create_engine(
    config.DATABASE_URL,
    poolclass=StaticPool,
    connect_args={
        "check_same_thread": False,
    } if config.DATABASE_URL.startswith('sqlite') else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create scoped session for thread safety
Session = scoped_session(SessionLocal)

def get_db():
    """Dependency to get database session"""
    db = Session()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all tables defined in models"""
    from .models import Base
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """Drop all tables (for testing/reset)"""
    from .models import Base
    Base.metadata.drop_all(bind=engine)

def init_db():
    """Initialize database with tables and seed data"""
    create_tables()
    seed_subjects()
    seed_regions_and_districts()
    seed_directions_from_pdf()

def seed_subjects():
    """Seed basic subjects"""
    from .models import Subject
    
    db = Session()
    
    try:
        # Check if already seeded
        if db.query(Subject).first():
            print("Subjects already seeded, skipping...")
            return
        
        subjects_data = [
            {'id': 1, 'name_uz': 'Matematika', 'name_oz': 'Matematika', 'name_ru': 'Математика', 'points_per_question': 1.1},
            {'id': 2, 'name_uz': 'Fizika', 'name_oz': 'Fizika', 'name_ru': 'Физика', 'points_per_question': 3.1},
            {'id': 3, 'name_uz': 'Kimyo', 'name_oz': 'Kimyo', 'name_ru': 'Химия', 'points_per_question': 3.1},
            {'id': 4, 'name_uz': 'Biologiya', 'name_oz': 'Biologiya', 'name_ru': 'Биология', 'points_per_question': 3.1},
            {'id': 5, 'name_uz': 'Tarix', 'name_oz': 'Tarix', 'name_ru': 'История', 'points_per_question': 1.1},
            {'id': 6, 'name_uz': 'Ona tili', 'name_oz': 'Ona tili', 'name_ru': 'Родной язык', 'points_per_question': 1.1},
            {'id': 7, 'name_uz': 'Adabiyot', 'name_oz': 'Adabiyot', 'name_ru': 'Литература', 'points_per_question': 2.1},
            {'id': 8, 'name_uz': 'Geografiya', 'name_oz': 'Geografiya', 'name_ru': 'География', 'points_per_question': 2.1},
            {'id': 9, 'name_uz': 'Ingliz tili', 'name_oz': 'Ingliz tili', 'name_ru': 'Английский язык', 'points_per_question': 2.1},
            {'id': 10, 'name_uz': 'Rus tili', 'name_oz': 'Rus tili', 'name_ru': 'Русский язык', 'points_per_question': 2.1},
        ]
        
        for subject_data in subjects_data:
            subject = Subject(
                id=subject_data['id'],
                name_uz=subject_data['name_uz'],
                name_oz=subject_data['name_oz'],
                name_ru=subject_data['name_ru'],
                points_per_question=subject_data['points_per_question']
            )
            db.add(subject)
        
        db.commit()
        print("Successfully seeded subjects")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding subjects: {e}")
    finally:
        db.close()

def seed_regions_and_districts():
    """Seed regions and districts from JSON files"""
    import json
    import os
    from .models import Region, District
    
    db = Session()
    
    try:
        # Check if already seeded
        if db.query(Region).first():
            print("Regions already seeded, skipping...")
            return
        
        # Load regions
        regions_file = os.path.join(os.path.dirname(__file__), '..', 'regions.json')
        with open(regions_file, 'r', encoding='cp1251') as f:
            regions_data = json.load(f)
        
        regions_map = {}
        for region_data in regions_data:
            region = Region(
                id=int(region_data['id']),
                name_uz=region_data['name_uz'],
                name_oz=region_data['name_oz'],
                name_ru=region_data['name_ru']
            )
            db.add(region)
            regions_map[region.id] = region
        
        db.commit()
        
        # Load districts
        districts_file = os.path.join(os.path.dirname(__file__), '..', 'districts.json')
        with open(districts_file, 'r', encoding='cp1251') as f:
            districts_data = json.load(f)
        
        for district_data in districts_data:
            district = District(
                id=int(district_data['id']),
                region_id=int(district_data['region_id']),
                name_uz=district_data['name_uz'],
                name_oz=district_data['name_oz'],
                name_ru=district_data['name_ru']
            )
            db.add(district)
        
        db.commit()
        print("Successfully seeded regions and districts")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding regions and districts: {e}")
    finally:
        db.close()

def seed_directions_from_pdf():
    """Seed directions from PDF parsing"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from utils.pdf_parser import parse_directions_from_pdf, get_subject_id_from_name
    
    db = Session()
    
    try:
        # Check if already seeded
        from .models import Direction
        if db.query(Direction).first():
            print("Directions already seeded, skipping...")
            return
        
        directions = parse_directions_from_pdf()
        seeded_codes = set()
        
        for direction_data in directions:
            # Skip if subject names are just numbers (parsing errors)
            if direction_data['subject1'].isdigit() or direction_data['subject2'].isdigit():
                continue
            
            # Skip if we've already seeded this code
            if direction_data['code'] in seeded_codes:
                continue
                
            subject1_id = get_subject_id_from_name(direction_data['subject1'])
            subject2_id = get_subject_id_from_name(direction_data['subject2'])
            
            direction = Direction(
                id=direction_data['code'],
                name_uz=direction_data['name'],
                name_oz=direction_data['name'],
                name_ru=direction_data['name'],  # For now, use same name
                subject1_id=subject1_id,
                subject2_id=subject2_id
            )
            db.add(direction)
            seeded_codes.add(direction_data['code'])
        
        db.commit()
        print(f"Successfully seeded {len(seeded_codes)} unique directions from PDF")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding directions: {e}")
    finally:
        db.close()
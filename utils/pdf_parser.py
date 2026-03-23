import PyPDF2
import os
import re
from typing import List, Dict

def parse_directions_from_pdf() -> List[Dict]:
    """
    Parse directions from Fanlar_majmuasi_2025-2026.pdf
    Returns list of direction dictionaries with code, name, and subject IDs
    """
    pdf_path = os.path.join(os.path.dirname(__file__), '..', 'Fanlar_majmuasi_2025-2026.pdf')
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            
            # Parse directions from text
            directions = extract_directions_from_text(text)
            
            return directions
            
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        # Return sample directions for now
        return get_sample_directions()

def extract_directions_from_text(text: str) -> List[Dict]:
    """
    Extract direction information from PDF text
    Format: "1.  60110100  Direction Name  Subject1  Subject2"
    """
    lines = text.split('\n')
    directions = []
    
    for line in lines:
        line = line.strip()
        if not line or not re.match(r'^\d+\.', line):
            continue
        
        # Split by double spaces to separate columns
        parts = re.split(r'\s{2,}', line)
        if len(parts) < 4:
            continue
        
        try:
            num = parts[0].rstrip('.')
            code = parts[1]
            
            # The direction name is everything between code and the last two subjects
            subject2 = parts[-1].strip()
            subject1 = parts[-2].strip()
            name_parts = parts[2:-2]  # Everything between code and subjects
            name = ' '.join(name_parts).strip()
            
            directions.append({
                'num': num,
                'code': code,
                'name': name.strip(),
                'subject1': subject1.strip(),
                'subject2': subject2.strip()
            })
        except (IndexError, ValueError) as e:
            print(f"Error parsing line: {line} - {e}")
            continue
    
    return directions

def get_subject_id_from_name(subject_name: str) -> int:
    """
    Map subject name to subject ID
    This needs to be updated based on actual subjects in database
    """
    subject_mapping = {
        'matematika': 1,
        'fizika': 2,
        'kimyo': 3,
        'biologiya': 4,
        'tarix': 5,
        'ona tili': 6,
        'ona tili va adabiyoti': 6,  # Map to native language
        'adabiyot': 7,
        'geografiya': 8,
        'ingliz tili': 9,
        'chet tili': 9,  # Map to English
        'rus tili': 10,
        'rus tili va adabiyoti': 10,
        'oʻzbek tili va adabiyoti': 6,  # Map to native language
        'qirgʻiz tili va adabiyoti': 9,  # Map to foreign language
        'qozoq tili va adabiyoti': 9,  # Map to foreign language
        'tojik tili va adabiyoti': 9,  # Map to foreign language
        'turkman tili va': 9,  # Map to foreign language
        'qoraqalpoq tili va': 9,  # Map to foreign language
        'fransuz tili': 9,  # Map to foreign language
        'nemis tili': 9,  # Map to foreign language
        'kasbiy': 7,  # Map to literature (creative exam)
        'kasbiy (ijodiy imtihon)': 7,  # Map to literature
        'kasbiy (ijodiy) imtihon': 7,  # Map to literature
        'huquqshunoslik': 5,  # Map to history
        'huquqshunoslik fanlari': 5,  # Map to history
    }
    
    # Clean subject name and find match
    clean_name = subject_name.lower().strip()
    for key, value in subject_mapping.items():
        if key in clean_name:
            return value
    
    print(f"Warning: Unknown subject '{subject_name}', defaulting to Math")
    return 1  # Default to math

def get_sample_directions() -> List[Dict]:
    """
    Return sample directions for testing
    Based on typical DTM directions - update with actual data from PDF
    """
    return [
        {
            'code': '101',
            'name_uz': 'Matematika va Fizika',
            'name_oz': 'Matematika va Fizika',
            'name_ru': 'Математика и Физика',
            'subject1_id': 1,  # Math
            'subject2_id': 2,  # Physics
        },
        {
            'code': '102',
            'name_uz': 'Matematika va Kimyo',
            'name_oz': 'Matematika va Kimyo',
            'name_ru': 'Математика и Химия',
            'subject1_id': 1,  # Math
            'subject2_id': 3,  # Chemistry
        },
        {
            'code': '103',
            'name_uz': 'Matematika va Biologiya',
            'name_oz': 'Matematika va Biologiya',
            'name_ru': 'Математика и Биология',
            'subject1_id': 1,  # Math
            'subject2_id': 4,  # Biology
        },
        {
            'code': '201',
            'name_uz': 'Tarix va Ona tili',
            'name_oz': 'Tarix va Ona tili',
            'name_ru': 'История и Родной язык',
            'subject1_id': 5,  # History
            'subject2_id': 6,  # Native Language
        },
        {
            'code': '202',
            'name_uz': 'Tarix va Adabiyot',
            'name_oz': 'Tarix va Adabiyot',
            'name_ru': 'История и Литература',
            'subject1_id': 5,  # History
            'subject2_id': 7,  # Literature
        },
        # Add more directions as needed
    ]
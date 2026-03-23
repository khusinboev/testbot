import PyPDF2
import re
import json

def parse_pdf_directions():
    pdf_path = 'Fanlar_majmuasi_2025-2026.pdf'
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ''
        for page in pdf_reader.pages:
            text += page.extract_text()

    lines = text.split('\n')
    directions = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Match direction lines: "1.  60110100  Direction Name  Subject1  Subject2"
        match = re.match(r'(\d+)\.\s+(\d{8})\s+(.+?)\s+([^\d]+?)\s+([^\d]+?)\s*$', line)
        if match:
            num, code, name_part, subject1, subject2 = match.groups()
            
            # Check if the next line continues the direction name
            full_name = name_part.strip()
            j = i + 1
            while j < len(lines) and not re.match(r'^\d+\.', lines[j].strip()):
                next_part = lines[j].strip()
                if next_part and not re.match(r'^\d{8}', next_part):  # Not a code
                    full_name += ' ' + next_part
                j += 1
            
            directions.append({
                'num': num,
                'code': code,
                'name': full_name.strip(),
                'subject1': subject1.strip(),
                'subject2': subject2.strip()
            })
            
            i = j
        else:
            i += 1

    print(f'Found {len(directions)} directions')

    # Extract unique subjects
    all_subjects = set()
    for d in directions:
        all_subjects.add(d['subject1'])
        all_subjects.add(d['subject2'])

    print(f'Unique subjects ({len(all_subjects)}): {sorted(all_subjects)}')

    # Save to files
    with open('directions_from_pdf.json', 'w', encoding='utf-8') as f:
        json.dump(directions, f, ensure_ascii=False, indent=2)

    with open('subjects_from_pdf.txt', 'w', encoding='utf-8') as f:
        for subj in sorted(all_subjects):
            f.write(f'{subj}\n')

    return directions, list(all_subjects)

if __name__ == "__main__":
    parse_pdf_directions()
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
                'name': name,
                'subject1': subject1,
                'subject2': subject2
            })
        except Exception as e:
            print(f'Error parsing line: {line} - {e}')
            continue

    print(f'Found {len(directions)} directions')
    for d in directions[:10]:
        print(f'{d["num"]}: {d["code"]} - {d["name"]} | {d["subject1"]} | {d["subject2"]}')

    # Extract unique subjects
    all_subjects = set()
    for d in directions:
        all_subjects.add(d['subject1'])
        all_subjects.add(d['subject2'])

    print(f'Unique subjects ({len(all_subjects)}): {sorted(all_subjects)}')

    # Save to files
    with open('directions_from_pdf_fixed.json', 'w', encoding='utf-8') as f:
        json.dump(directions, f, ensure_ascii=False, indent=2)

    with open('subjects_from_pdf_fixed.txt', 'w', encoding='utf-8') as f:
        for subj in sorted(all_subjects):
            f.write(f'{subj}\n')

    return directions, list(all_subjects)

if __name__ == "__main__":
    parse_pdf_directions()
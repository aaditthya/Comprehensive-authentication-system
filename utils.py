import face_recognition 
import json
import cv2
import numpy as np
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer import AnalyzerEngine
import os
import datetime
import PyPDF2
from presidio_anonymizer.entities import OperatorConfig
from fpdf import FPDF


with open("data.json", "r") as f:
    data = json.load(f)


def load_encodings():

    encodings = data['face']['encodings']
    faces = data['face']['ids']

    return encodings, faces


def encode_image(name, img_path, admin=False):

    img = face_recognition.load_image_file(img_path)
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)[0]
    data['face']['encodings'].append(list(face_encodings))
    data['face']['ids'].append(name)

    if admin:
        data['roles']['admin'].append(name)
    else:
        data['roles']['employee'].append(name)

    with open('data.json', 'w') as jf:
        json.dump(data, jf)


    return True



def detect_faces(stream_path):
    print("Loading frame from:", stream_path)
    frame = cv2.imread(stream_path)
    if frame is None:
        print("Error: Unable to load frame from", stream_path)
        return False, False

    print("Frame loaded successfully.")

    with open("data.json", "r") as f:
        data = json.load(f)

    encodings = data['face']['encodings']
    faces = data['face']['ids']

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, locations)

    if not face_encodings:
        print("Error: No faces detected in the frame")
        return False, False

    for (t, r, b, l), encoding in zip(locations, face_encodings):
        matches = face_recognition.compare_faces(encodings, encoding, tolerance=0.5)

        name = False

        distances = face_recognition.face_distance(encodings, encoding)
        match_idx = np.argmin(distances)

        if matches[match_idx]:
            name = faces[match_idx]

        colors = (0, 0, 255) if name else (255, 0, 0)
        cv2.rectangle(frame, (l, t), (r, b), colors, 2)
        cv2.rectangle(frame, (l, b-35), (r, b), colors, cv2.FILLED)
        cv2.putText(frame, str(name), (l+6, b-6), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 1)

    cv2.imshow('Window', frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    if name and name in data['face']['ids']:
        if name in data['roles']['admin']:
            return True, True
        else:
            return True, False
    else:
        return False, False



def get_file_details(folder_path):
    file_details_list = []

    # List all files in the given directory
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        # Check if it's a file and not a directory
        if os.path.isfile(file_path):
            # Get file size in KB
            size = os.path.getsize(file_path) / 1024  # Size in KB

            # Get the last modified date
            mod_timestamp = os.path.getmtime(file_path)
            mod_date = datetime.datetime.fromtimestamp(mod_timestamp).strftime('%d/%m/%y')

            # Append the details to the list
            file_details_list.append({"doc": filename, "size": f"{size:.2f}kb", "date": mod_date})

    return file_details_list


def read_pdf(file_path):
    # Open the PDF file
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        num_pages = len(reader.pages)
        
        # Read text from each page and concatenate
        text = ''
        for i in range(num_pages):
            page = reader.pages[i]
            text += page.extract_text() + '\n'
    
    return text


def identify_pii(text):
    analyzer = AnalyzerEngine()
    results = analyzer.analyze(text=text, language='en')
    original_entities = []
    identified_entities = []
    for result in results:
        if result.entity_type != "O":
            identified_entities.append(result)
            original_entities.append({
                "entity_type": result.entity_type,
                "start": result.start,
                "end": result.end,
                "text": text[result.start:result.end]
            })

    return identified_entities, original_entities


def anonymize_pii(text, identified_pii):
    anonymizer = AnonymizerEngine()
    operators = {}
    for pii_entity in identified_pii:
        operators[pii_entity.entity_type] = OperatorConfig("replace", {"new_value": "****"})
    anonymized_results = anonymizer.anonymize(text=text, analyzer_results=identified_pii, operators=operators)
    return anonymized_results.text


def generate_entities(original_entities):
    entity_dict = {}
    for i in original_entities:
        if entity_dict.get(i['entity_type']):
            entity_dict[i['entity_type']].append(i['text'])
        else:
            x = i['entity_type']
            entity_dict[x] = [i['text']]


    return entity_dict


def save_pdf(anonymized_text, pdf_file_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    text = anonymized_text
    pdf.multi_cell(0, 10, txt=text, border=0, align='L')
    pdf.output(pdf_file_path)


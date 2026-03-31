import face_recognition
import cv2
import numpy as np
import base64
import json

def get_face_encodings(image_data, is_base64=True):
    """
    Given image data (base64 or bytes), returns facial encodings if a face is found.
    """
    if is_base64:
        # Convert base64 string to bytes
        if "," in image_data:
            image_data = image_data.split(",")[1]
        decoded_data = base64.b64decode(image_data)
        nparr = np.frombuffer(decoded_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        img = image_data

    # Convert to RGB (face_recognition uses RGB)
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Get face locations and encodings
    face_locations = face_recognition.face_locations(rgb_img)
    face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
    
    if not face_encodings:
        return None
    
    # Return the first face encoding found (as list for easy JSON storage)
    return face_encodings[0].tolist()

def compare_faces(known_encodings_dict, frame_base64):
    """
    Compare multiple faces from a camera frame against a dictionary of known student encodings.
    known_encodings_dict: {student_id: [encoding_list], ...}
    returns: List of recognized student IDs
    """
    # Decode frame
    if "," in frame_base64:
        frame_base64 = frame_base64.split(",")[1]
    decoded_data = base64.b64decode(frame_base64)
    nparr = np.frombuffer(decoded_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Convert to RGB
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Find all faces in the current frame
    face_locations = face_recognition.face_locations(rgb_img)
    face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
    
    recognized_ids = []
    
    # Extract student IDs and their corresponding encodings
    student_ids = list(known_encodings_dict.keys())
    known_encodings = [known_encodings_dict[sid] for sid in student_ids]
    
    if not face_encodings or not known_encodings:
        return []
    
    for face_encoding in face_encodings:
        # Compare with known encodings
        matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
        
        # If there's a match, get the best distance
        face_distances = face_recognition.face_distance(known_encodings, face_encoding)
        best_match_index = np.argmin(face_distances)
        
        if matches[best_match_index]:
            recognized_ids.append(student_ids[best_match_index])
            
    return list(set(recognized_ids)) # Unique IDs

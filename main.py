import os
import json
import copy
import shutil  # Import shutil for file/folder moving
import random
import zipfile
import datetime
import winsound
import cv2 as cv
import numpy as np
import customtkinter
from PIL import Image
from ultralytics import YOLO
from tkinter import filedialog
from util.createjson import *

# Define the path to the model
model_path = "forentoModel.pt"

# Define the classes
classes = ["fly", "larvae", "pupae"]

# Generate random colors for each class
def generate_random_colors(num_classes):
    """Generates a list of random BGR colors for a specified number of classes."""
    colors = []
    fly_class = [0, 206, 245]  # yellow color for fly
    colors.append(fly_class)
    larvae_class = [217, 22, 152]
    colors.append(larvae_class)
    pupae_class = [160, 199, 65]
    colors.append(pupae_class)  # Note: OpenCV uses BGR format
    return colors

detection_colors = generate_random_colors(len(classes))  # Generate colors once

# Load a pretrained YOLOv8n model
model = YOLO(model_path, 'v8')

# Initialize the camera (placeholder)
cap = None
# Global variables
running = False
save_directory = None
fly_data_file = None  # New variable to store the JSON file handle
fly_data_file_path = None 
json_data_dir = "data"
fly_data = {}  # Create an empty dictionnary to store fly data objects
images_to_archive = []
fly_data_per_frame = []

# Custom function to check if an external camera is available
def check_external_camera():
    external_cameras = []
    for i in range(5):
        cap = cv.VideoCapture(i)
        if cap.isOpened():
            if not is_built_in_webcam(cap):
                external_cameras.append(cap)
            else:
                cap.release()
    
    if len(external_cameras) > 0:
        print(f"Found {len(external_cameras)} external cameras")
        return external_cameras[0]
    else:
        print("No external camera found")
        return None

# Helper function to check if a camera is a built-in webcam
def is_built_in_webcam(cap):
    # Check the camera name or other properties to determine if it's a built-in webcam
    # This implementation assumes that built-in webcams have "webcam" in their name
    cap_name = cap.getBackendName()
    return "webcam" in cap_name.lower()

# Function to prompt for save directory
def get_save_directory():
    folder_path = filedialog.askdirectory(title="Select Save Directory")
    if folder_path:
        return folder_path
    else:
        return None

# Function to create a new JSON file for the day's fly data
def create_new_fly_data_file():
    global fly_data_file
    # Create a subdirectory for JSON files if it doesn't exist
    sub_directory = os.path.join(json_data_dir, "json_data")
    os.makedirs(sub_directory, exist_ok=True)

    # Generate filename based on date
    today_str = datetime.datetime.now().strftime("%d-%m-%Y")
    file_name = f"detection_data_{today_str}.json"
    json_file_path = os.path.join(sub_directory, file_name)

    # Check json file's existence
    if os.path.exists(json_file_path):
        return json_file_path
    else:
        data = {'data': []}
        try:
            with open(json_file_path, "w") as fly_data_file:
                json.dump(data,fly_data_file, indent=2)
            fly_data_file.close()
            return json_file_path
        except IOError:
            print(f"Error opening JSON file: {json_file_path}")
            return None

# Create the CustomTkinter app
customtkinter.set_appearance_mode("dark")  # Set the appearance mode
app = customtkinter.CTk()  # Create the app
app.geometry("1100x950")  # Set the initial window size
app.title("Forento Fly Detector")  # Set the title

# Create a sidebar frame
sidebar_frame = customtkinter.CTkFrame(app, width=150, corner_radius=0)
sidebar_frame.pack(side="left", padx=10, pady=10, fill="y")

# Create buttons in the sidebar
start_button = customtkinter.CTkButton(sidebar_frame, text="Start", command=lambda: start_detection())
start_button.pack(pady=10, fill="x")

stop_button = customtkinter.CTkButton(sidebar_frame, text="Stop", command=lambda: stop_detection(), state="disabled")
stop_button.pack(pady=10, fill="x")

open_folder_button = customtkinter.CTkButton(sidebar_frame, text="Open Folder", command=lambda: open_save_folder(), state="disabled")
open_folder_button.pack(pady=10, fill="x")

exit_button = customtkinter.CTkButton(sidebar_frame, text="Exit", command=app.quit)
exit_button.pack(pady=10, fill="x")

# Create a label for the confidence spinbox
confidence_label = customtkinter.CTkLabel(sidebar_frame, text="Confidence Threshold:")
confidence_label.pack(pady=10)

# Create the confidence spinbox with initial value of 0.85 and increments of 0.01
confidence_var = customtkinter.IntVar(value= 85)  # Initial value as 85 (represents 0.85)
confidence_entry = customtkinter.CTkEntry(
                    sidebar_frame,
                    width= 200,  
                    textvariable=confidence_var)
confidence_entry.pack(pady=10)

# Create buttons for pause and play confidence threshold functionality
pause_button = customtkinter.CTkButton(sidebar_frame, text="pause", command=lambda: pause_detection(), state="disabled")
pause_button.pack(pady=10, fill="x")

play_button = customtkinter.CTkButton(sidebar_frame, text="play", command=lambda: resume_detection(), state="normal")
play_button.pack(pady=10, fill="x")

# Create a frame to hold the image
image_frame = customtkinter.CTkFrame(app)
image_frame.pack(padx=10, pady=10, fill="both", expand=True)

# Create a label to display the image
image_label = customtkinter.CTkLabel(image_frame, text="")
image_label.pack(fill="both", expand=True)


def start_detection():
    global cap, running, save_directory, fly_data_file, fly_data_file_path

    # Create new fly data file
    fly_data_file_path = create_new_fly_data_file()
    
    # Check if an external camera is available
    cap = check_external_camera()
    if not cap:
        return

    # Check save directory only on initial start
    if not save_directory:
        save_directory = get_save_directory()
        if not save_directory:
            return  # Exit function if user cancels save directory selection

    # Ensure JSON data directory exists
    if not os.path.exists(json_data_dir):
        print(f"Error: JSON data directory '{json_data_dir}' does not exist!")
        return
    
    # Clear fly data before starting a new detection session
    # fly_data.clear()

    running = True
    start_button.configure(state="disabled")
    stop_button.configure(state="normal")
    open_folder_button.configure(state="normal")
    pause_button.configure(state="normal")  # Enable pause button when detection starts
    confidence_entry.configure(state="disabled")  # Disable confidence entry editing
    detect_objects()

def stop_detection():
    global running, fly_data_file
    running = False
    start_button.configure(state="normal")
    stop_button.configure(state="disabled")
    open_folder_button.configure(state="normal")
    clear_image_label()
    fly_data_file.close()
    # if fly_data_file:
    #     fly_data_file.close()  # Close the JSON file
    #     fly_data_file = None


def open_save_folder():
    if save_directory:
        os.startfile(save_directory)

def clear_image_label():
    image_label.configure(image=None)
    image_label.image = None

# Function to pause detection
def pause_detection():
    global running
    if running:
        running = False
        pause_button.configure(state="normal")
        play_button.configure(state="normal")
        confidence_entry.configure(state="normal")  # Enable editing the entry

# Function to resume detection
def resume_detection():
    global running
    if not running:
        confidence_threshold = float(confidence_entry.get()) / 100.0  # Get and validate threshold
        confidence_entry.configure(state="disabled")  # Disable editing the entry
        start_detection()  # Call start_detection to handle further logic

fly_id_counter = 0  # Initialize a counter
def generate_unique_id():
    global fly_id_counter
    fly_id_counter += 1
    return fly_id_counter

def save_fly_data(fly_info):
    unique_id = generate_unique_id()
    fly_data[f"fly_{unique_id}"] = fly_info  # Add data with unique key

# Define the function to write fly data to JSON (assuming in the same file)
def write_fly_data_to_json(file_path, fly_data_per_frame):
    # global fly_data_per_frame  # Access the global list from detect_objects
    global fly_data_file

    if file_path:
        try:
            json_data = None
            # Open in read mode
            with open(file_path, 'r') as fly_data_file:
                json_data = json.load(fly_data_file)
            fly_data_file.close()

            json_data["data"] = json_data["data"] + fly_data_per_frame

            with open(file_path, 'w') as fly_data_file:
                json.dump(json_data, fly_data_file, indent=2)
            fly_data_file.close()    
        except IOError as e:
            print(f"Error writing fly data to JSON: {e}")


def detect_objects():
    global running, cap, save_directory, fly_data_file, fly_data_file_path
    
    if not running:
        return

    ret, frame = cap.read()

    # Check if frame capture was successful
    if not ret:
        print("Error: Unable to capture frame from camera")
        return
    
    # Get the confidence threshold from the entry, handle empty values
    try:
        confidence_threshold_str = confidence_entry.get()  # Get the text from the entry
        confidence_threshold = float(confidence_threshold_str) / 100.0  # Convert to float (0-1)
    except ValueError:
        confidence_threshold = 0.85  # Set default value if conversion fails

    # print(confidence_threshold, "confidence")
    
    # Predict on the frame
    detections = model.predict(source=frame, save=False, conf=confidence_threshold)
    detections = detections[0].numpy()

    if len(detections) != 0:
        
        if fly_data_file_path and running:
            for detection in detections:
                boxes = detection.boxes

                for box in boxes:
                    # Retreive necessery data from the boxes
                    x_min, y_min, x_max, y_max = box.xyxy[0]  # Unpack the box information
                    class_id = int(box.cls[0])  # Assuming integer class IDs
                    conf = box.conf[0]  # The confidence of the prediction
                    rounded_confidence = str(round(conf * 100, 2))  # Convert confidence to string and round
                    color = detection_colors[class_id]  # Access color for the current class

                    # Draw rectangle and display class name and confidence
                    cv.rectangle(frame, (int(x_min), int(y_min)), (int(x_max), int(y_max)), color, 2)
                    font = cv.FONT_HERSHEY_COMPLEX
                    fontScale = 0.5  # Decrease the font size by 0.5
                    class_name = classes[class_id]  # Assuming classes is a dictionary mapping id to class name
                    text = class_name + " " + rounded_confidence + "%"
                    cv.putText(frame, text, (int(x_min), int(y_min) - 10), font, fontScale, (0, 0, 255), 1)

                    # Check if detected object is a fly
                    if detection.names[class_id] != "fly" and fly_data_file_path:
                        unique_id = generate_unique_id()
                        now = datetime.datetime.now()
                        date_time_str = now.strftime("%d-%m-%y_%H-%M-%S")
                        file_name = os.path.join(save_directory, f'detected-fly_{date_time_str}.png')
                        images_to_archive.append(file_name)
                        rgb_frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)  # Convert to RGB
                        pil_image = Image.fromarray(rgb_frame)  # Convert to PIL Image
                        winsound.Beep(3000, 500)
                        pil_image.save(file_name)
                        fly_info = {
                            "date_time": date_time_str,
                            "confidence": rounded_confidence
                        }
                        fly_data_per_frame.append(fly_info)  # Append fly data to the list
        # Write data for every frame (real-time)
        #Write data after every frame
        write_fly_data_to_json(fly_data_file_path, fly_data_per_frame)

    # Archive fly images to ZIP file in ../data/archive dir

    # Update the GUI with the processed frame
    img = Image.fromarray(cv.cvtColor(frame, cv.COLOR_BGR2RGB))
    photo = customtkinter.CTkImage(img, size=(640, 480))
    image_label.configure(image=photo)
    image_label.image = photo

    # Schedule the next frame capture and detection
    if running:
        app.after(10, detect_objects)


app.mainloop()

# Release the capture when the app is closed
if cap:
    cap.release()
cv.destroyAllWindows()
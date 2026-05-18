"""
PROJECT: Live-Geotagged Pothole Reporter
AUTHOR: High School AI Developer
DESCRIPTION: 
    This Streamlit web application uses a smartphone/computer browser to:
    1. Capture the user's exact live GPS coordinates.
    2. Take a photo of a road surface using the device camera.
    3. Manually inject those GPS coordinates into the hidden metadata (EXIF) of the image.
    4. Pass the image to Google's Gemini AI model to check for potholes.
    5. Automatically email a supervisor with a Google Maps link if a pothole is found.
"""

# ==========================================
# 1. IMPORTING REQUIRED LIBRARIES (TOOLBOX)
# ==========================================
import streamlit as st                  # Streamlit: Helps us build a beautiful web interface using only Python
import google.generativeai as genai     # Google Generative AI: Connects our app to the Gemini AI models
from PIL import Image                   # Pillow (PIL): Used for opening, manipulating, and saving images
import smtplib                          # SMTP Library: Python's built-in tool to send emails via the internet
from email.message import EmailMessage  # Email Message: Helps us format emails cleanly (Subject, To, From, Body)
from streamlit_geolocation import streamlit_geolocation  # A custom Streamlit tool that asks the browser for GPS data
import io                               # Input/Output: Allows us to handle image data in the computer's memory without saving files to disk

# ==========================================
# 2. CONFIGURATION & SECRETS MANAGEMENT
# ==========================================
# Instead of typing private passwords into our code (which is dangerous!), 
# we use st.secrets. Streamlit securely reads these from a hidden file or cloud dashboard.
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    GMAIL_USER = st.secrets["GMAIL_USER"]
    GMAIL_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]  # Your 16-character Google App Password
    RECIPIENT_EMAIL = st.secrets["RECIPIENT_EMAIL"]    # Who receives the pothole alerts
except KeyError:
    # If you forgot to set up your secrets, the app will show this helpful error message and stop.
    st.error("🚨 Configuration Error: Missing required keys in Streamlit Secrets!")
    st.info("Please ensure GEMINI_API_KEY, GMAIL_USER, GMAIL_APP_PASSWORD, and RECIPIENT_EMAIL are set up in your secrets.")
    st.stop()

# Activate and set up our Gemini AI model connection
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')  # We use 2.5-flash because it is incredibly fast and great with images

# ==========================================
# 3. EXIF METADATA INJECTION HELPERS
# ==========================================
def change_to_rational(number):
    """
    EXIF data (the hidden metadata inside JPEG files) doesn't store coordinates as standard 
    decimals like 40.7128. Instead, it expects them in a math format called 'Rationals' 
    broken into (Degrees, Minutes, Seconds). This function converts decimals into that format.
    """
    deg = int(number)
    min_float = (number - deg) * 60
    minute = int(min_float)
    sec = round((min_float - minute) * 60, 4)
    # Returns the data in a nested tuple format required by the official EXIF standard
    return ((deg, 1), (minute, 1), (int(sec * 10000), 10000))

def add_geotag_to_image(image_buffer, lat, lon):
    """
    When you take a photo on a web app, the browser strips away location data for privacy.
    This function acts like a digital stamp, manually injecting the browser's GPS coordinates 
    back into the image file's metadata headers so the image becomes permanently 'Geo-Tagged'.
    """
    img = Image.open(image_buffer)  # Open the raw camera photo stream using Pillow
    
    gps_info = {}
    # Determine direction flags ('N' for North of the equator, 'S' for South, etc.)
    lat_ref = 'N' if lat >= 0 else 'S'
    lon_ref = 'E' if lon >= 0 else 'W'
    
    # Standard EXIF GPS Tags use numbers as IDs:
    # 1 = Latitude Reference, 2 = Latitude Value, 3 = Longitude Reference, 4 = Longitude Value
    gps_info[1] = lat_ref
    gps_info[2] = change_to_rational(abs(lat))
    gps_info[3] = lon_ref
    gps_info[4] = change_to_rational(abs(lon))
    
    # Grab any existing metadata from the image
    exif = img.getexif()
    # Tag ID 0x8825 is the official global ID reserved for GPS Information in images. 
    # We overwrite it with our custom GPS data dictionary.
    exif[0x8825] = gps_info
    
    # Instead of saving the file onto your hard drive, we save it directly inside RAM memory
    # using BytesIO. This makes the web application much faster.
    output_buffer = io.BytesIO()
    img.save(output_buffer, format="JPEG", exif=exif)
    output_buffer.seek(0)  # Reset the pointer to the beginning of the image data file
    return output_buffer

# ==========================================
# 4. AUTOMATED EMAIL DISPATCHER
# ==========================================
def send_notification_email(lat, lon, analysis):
    """
    Connects to Google's secure mail servers using SMTP (Simple Mail Transfer Protocol) 
    to automatically construct and send an incident report email.
    """
    msg = EmailMessage()
    # Dynamically generate a clickable Google Maps link using our latitude and longitude coordinates
    maps_link = f"https://www.google.com/maps?q={lat},{lon}"
    
    # Draft the text body of our email report
    email_body = (
        f"🚨 AUTOMATED ALERT: Pothole Hazard Detected.\n\n"
        f"--- GEOGRAPHIC LOCATION ---\n"
        f"Latitude: {lat}\n"
        f"Longitude: {lon}\n"
        f"Google Maps Link: {maps_link}\n\n"
        f"--- GEMINI AI DAMAGE ANALYSIS ---\n"
        f"{analysis}\n\n"
        f"Sent automatically by the Pothole Reporting Application."
    )
    
    # Set standard email headers
    msg.set_content(email_body)
    msg['Subject'] = "🚨 CRITICAL: Pothole Hazard Location Report"
    msg['From'] = GMAIL_USER
    msg['To'] = RECIPIENT_EMAIL

    # Establish a highly secure, encrypted connection (SSL) to Gmail on Port 465
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASSWORD)  # Log in securely using our App Password
        smtp.send_message(msg)                 # Dispatch the email into the internet relay

# ==========================================
# 5. STREAMLIT FRONTEND USER INTERFACE (UI)
# ==========================================
# Configure basic web browser tab settings
st.set_page_config(page_title="Pothole Reporter", page_icon="🛡️", layout="centered")

st.title("🛡️ Live-Geotagged Pothole Reporter")
st.write("An automated AI application to capture, log, and report infrastructure damage.")

st.markdown("---")
st.subheader("Step 1: Acquire GPS Coordinates")
st.write("Click the button below to fetch live device hardware location via your browser.")

# Active client-side hardware coordinate retrieval. This triggers a popup in the 
# browser asking the user: 'Allow this website to access your location?'
location_data = streamlit_geolocation()

# Check if the user successfully granted location access and coordinates exist
if location_data and location_data.get('latitude') is not None:
    lat = location_data['latitude']
    lon = location_data['longitude']
    st.success(f"📍 GPS coordinates successfully locked: `{lat}, {lon}`")
    
    st.markdown("---")
    st.subheader("Step 2: Snapshot the Asset Damage")
    
    # Opens up the user's phone camera or laptop webcam directly inside the web page
    camera_photo = st.camera_input("Position the camera over the road surface defect:")
    
    if camera_photo:
        # A spinner shows a temporary loading wheel while processing happens
        with st.spinner("Embedding hardware coordinates directly into image stream..."):
            # Run metadata background conversion and patching using our helper function
            geotagged_image_file = add_geotag_to_image(camera_photo, lat, lon)
            st.toast("Metadata mapping complete: EXIF headers added.", icon="✅")
            
        st.markdown("---")
        # Create a large action button to submit everything to the AI
        if st.button("🚀 Analyze & Dispatch Report", use_container_width=True):
            with st.spinner("Processing asset frames through Gemini AI Core..."):
                
                # Re-load the freshly geo-tagged image bytes so Gemini can read it
                final_img = Image.open(geotagged_image_file)
                
                # Prompt Engineering: We force Gemini to output a strict answer structure.
                # Starting with 'YES' or 'NO' makes it easy for our Python code to parse.
                prompt = (
                    "Look closely at this image. Is there a clear pothole, deep asphalt crater, "
                    "or dangerous structural breakdown on the driving lanes? "
                    "Answer strictly with either 'YES' or 'NO' as your first word. "
                    "Follow that with a short description explaining what you see."
                )
                
                # Upload the prompt and image together to the Gemini Cloud API
                response = model.generate_content([prompt, final_img])
                verdict = response.text.strip()
                
                # Display Gemini's raw written thoughts directly on the web page screen
                st.subheader("AI Analysis Results:")
                st.info(f"{verdict}")
                
                # Check if the first word coming back from the AI is "YES"
                if verdict.upper().startswith("YES"):
                    st.warning("⚠️ Pothole presence verified. Initializing secure email routing protocol...")
                    try:
                        # Call our email helper function and feed it our tracked data variables
                        send_notification_email(lat, lon, verdict)
                        st.success("📩 Notification report successfully dispatched to public transit logs!")
                    except Exception as e:
                        # If the internet drops or passwords are wrong, show the error code safely
                        st.error(f"Failed to communicate with SMTP relay servers: {e}")
                else:
                    # If the AI starts its message with 'NO', we skip sending emails entirely
                    st.success("🌿 No actionable structural failures identified. No automated alerts triggered.")
else:
    # If the user blocks location permissions, hide the camera and show a warning notice
    st.warning("👋 Action Required: Please interact with the location prompt above and grant your browser access to GPS to display camera capture tool.")
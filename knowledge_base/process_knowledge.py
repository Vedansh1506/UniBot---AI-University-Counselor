import os
import json
import time
import google.generativeai as genai

# --- Action Required: PASTE YOUR GEMINI API KEY HERE ---
GEMINI_API_KEY = "AIzaSyBx4byRlSAFYANUbqYbEGb5oG2MpZxodq4"
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"ERROR: Gemini API key not set or invalid. {e}")
    exit()

# --- Configuration ---
RAW_DATA_DIR = "data"
CLEANED_DATA_DIR = "cleaned_data"

def clean_program_list(university_name, programs):
    """Uses Gemini to clean a messy list of academic programs."""
    print(f"  Cleaning program list for {university_name}...")
    
    # --- FIX: Using the stable 'gemini-1.0-pro' model name ---
    model = genai.GenerativeModel('gemini-1.0-pro')
    
    prompt = f"""
    You are a data cleaning expert for university academic programs.
    From the following list of programs for {university_name}, your task is to extract ONLY the official Master of Science (MS), Master of Engineering (MEng), or other relevant Master's degree programs.

    RULES:
    - Exclude all PhD programs, undergraduate degrees (BS, BA), certificates, non-degree programs, and minors.
    - Exclude overly broad, non-specific terms like 'All Graduate Programs', 'Masters Programs', 'Graduate Studies'.
    - If the list is already clean, return it as is.
    - If the list contains no valid Master's programs, return an empty list.
    - Your final output MUST be a valid JSON array of strings. For example: ["MS in Computer Science", "MS in Electrical Engineering"].

    MESSY LIST:
    {programs}

    Clean JSON Array:
    """
    
    try:
        response = model.generate_content(prompt)
        json_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        cleaned_list = json.loads(json_text)
        return cleaned_list
    except Exception as e:
        print(f"    ERROR: Gemini cleaning failed or returned invalid JSON. {e}")
        return None

def main():
    if not os.path.exists(CLEANED_DATA_DIR):
        os.makedirs(CLEANED_DATA_DIR)
        
    for filename in os.listdir(RAW_DATA_DIR):
        if filename.endswith(".json"):
            raw_file_path = os.path.join(RAW_DATA_DIR, filename)
            cleaned_file_path = os.path.join(CLEANED_DATA_DIR, filename)
            
            with open(raw_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"Processing {data.get('university_name', 'Unknown University')}...")
            
            messy_programs = data.get('ms_programs', [])
            
            if messy_programs:
                cleaned_programs = clean_program_list(data.get('university_name'), messy_programs)
                
                if cleaned_programs is not None:
                    data['ms_programs'] = cleaned_programs
                    with open(cleaned_file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
                    print(f"  SUCCESS: Saved cleaned data to {cleaned_file_path}")
                else:
                    print(f"  FAILURE: Could not clean data for {filename}.")
            else:
                print("  SKIPPING: No programs found to clean.")
            
            time.sleep(1)

if __name__ == "__main__":
    if "YOUR_GEMINI_API_KEY_HERE" in GEMINI_API_KEY:
        print("Please paste your Gemini API key into the script before running.")
    else:
        main()
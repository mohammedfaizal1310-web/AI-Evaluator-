# Initial setup for the proposal evaluation project
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

import os
import shutil
from io import StringIO
import json
import re
import math

import fitz  # PyMuPDF
import google.generativeai as genai
import pandas as pd

app = Flask(__name__)
CORS(app)

# Configuration for file upload
UPLOAD_FOLDER = 'uploaded_files'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure Generative AI - Remember to replace with your key
genai.configure(api_key="AIzaSyARTWrJapZhC3oLBxzeJfAHYIY90tlKdPI") # Replace with your actual key
model = genai.GenerativeModel("gemini-2.5-flash")


# --- Helper Functions ---

def sanitize_filename(filename):
    """Remove path traversal and unsafe characters."""
    filename = filename.strip().replace("/", "_").replace("\\", "_")
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    return filename

def clean_text(text):
    """Remove duplicate empty lines, trailing spaces, and tabs."""
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = re.sub(r'[ ]+\n', '\n', text)
    text = re.sub(r'[^\S\r\n]+', ' ', text)
    return text.strip()

def parse_markdown_table_to_json(markdown_table_text):
    try:
        df = pd.read_csv(StringIO(markdown_table_text), sep="|", engine="python", skipinitialspace=True)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]  # drop any unnamed column
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        json_data = df.to_dict(orient="records")
        return json_data
    except Exception as e:
        print("Error parsing markdown to JSON:", e)
        return []



# --- File Reading and AI Interaction Functions ---

def read_text_file(file_path):
    """Reads the entire content of a text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

def extract_text_from_pdf_page(pdf_path, page_number):
    """Extracts text from a single page of a PDF file."""
    try:
        with fitz.open(pdf_path) as doc:
            if page_number < 0 or page_number >= len(doc):
                return f"Error: Page number {page_number} is out of bounds."
            page = doc[page_number]
            return page.get_text()
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return None

def extract_table_from_gemini(text):
    """Sends RFP text to Gemini to create a multi-level rubric."""
    prompt = (
        "From the following text, extract the 'Evaluation Parameters' table located under section 51. "
        "Present the data in a **markdown table format** with the following columns:\n"
        "- 'Main Criterion (with English in brackets)'\n"
        "- 'Weight %'\n"
        "- 'Sub-Criterion (with English in brackets)'\n"
        "- 'Sub-Weight %'\n"
        "- 'Expectation'\n\n"

        "The English translation of both the main criterion and sub-criterion should appear inside **brackets** next to the Arabic text.\n"
        "For example: المعايير الفنية (Technical Criteria)\n\n"
        
        "**CRITICAL INSTRUCTION FOR 'Expectation' COLUMN:**\n"
        "For each sub-criterion, you must generate a **multi-level evaluation rubric**. Define what constitutes different levels of compliance. Use this format precisely:\n"
        "- **Excellent (Full Marks):** Describe the ideal submission. e.g., 'Vendor provides detailed individual CVs for all key roles...'\n"
        "- **Good (Partial Marks):** Describe a submission that meets the basic requirement but lacks detail. e.g., 'Vendor provides role descriptions but no individual CVs.'\n"
        "- **Insufficient (Low/No Marks):** Describe a non-compliant submission. e.g., 'Vendor only lists roles with no description...'\n\n"
        f"**Text to Analyze:**\n{text}"
    )
    try:
        generation_config = {"temperature": 0.0}
        safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        return response.text
    except Exception as e:
        print(f"Gemini error during table extraction: {e}")
        return None

def extract_tables_from_response(response_content):
    # Use regex to extract table-like structures
    table_matches = re.findall(r"\|.*?\|\n(?:\|.*?\|(?:\n|$))+", response_content)
    tables = []

    for table_content in table_matches:
        try:
            table = pd.read_csv(
                StringIO(table_content),
                sep="|",
                engine="python",
                skipinitialspace=True
            )
            # Drop any unnamed empty columns caused by extra pipes
            table = table.loc[:, ~table.columns.str.contains('^Unnamed')]
            table = table.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
            tables.append(table)
        except Exception as e:
            print(f"Error parsing table: {e}")
    return tables

def normalize_parameter_table(df):
    try:
        # Strip all column names and values
        df.columns = [col.strip() for col in df.columns]
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        # Remove separator row (row of dashes)
        df = df[~df.iloc[:, 0].astype(str).str.contains("^-+$")]

        # Fill down missing main criterion and weights
        df.ffill(inplace=True)

        # Rename columns to consistent keys
        df.columns = ['main_criteria', 'main_weight', 'sub_weight', 'sub_criteria', 'expectation']

        # Convert to list of dictionaries
        parameter_table = df.to_dict(orient='records')

        return parameter_table
    except Exception as e:
        print(f"Error normalizing table: {e}")
        return []

def generate_evaluation_prompt(parameter_table, proposal_texts, rfp_text, human_evaluation_text):
    prompt = []
    prompt.append(
        "You are an expert RFP technical evaluator with 20 years of experience in government IT procurement. "
        "Your task is to apply deep domain knowledge to assess the quality and feasibility of the proposed solutions. "
        "Your final output should be a standalone, authoritative evaluation based on your expert analysis in Arabic."
    )
    prompt.append(
        "\n\n### Expert Judgment Calibration (Internal Training Document)\n"
        "To calibrate your judgment, first study the provided internal training document. Internalize the reasoning patterns, paying attention to:\n"
        "1.  The critical assessment of technical plans, focusing on feasibility over keywords.\n"
        "2.  The holistic interpretation of evidence to award nuanced, partial scores.\n"
        "Apply this calibrated judgment to evaluate the new proposals independently. Do not refer to or mention this training document in your final output.\n"
        f"--- START INTERNAL TRAINING DOCUMENT ---\n{human_evaluation_text}\n--- END INTERNAL TRAINING DOCUMENT ---"
    )
    if rfp_text:
        prompt.append("\n\n### RFP Full Text (for reference only):\n" + rfp_text)

    prompt.append("\n\n### Evaluation Criteria Rubric:\n"
                  "This table provides the sub-criterion, its weight, and a detailed rubric for scoring.\n")
    prompt.append(json.dumps(parameter_table, ensure_ascii=False, indent=2))
    
    proposal_names = [name for name, _ in proposal_texts]
    prompt.append(f"\n\n### Proposals to Evaluate ({len(proposal_names)} total): " + ", ".join(proposal_names))
    prompt.append("\n\n### Proposal Contents:\n")
    for name, text in proposal_texts:
        prompt.append(f"\n## Proposal: {name}\n{text}")

    prompt.append(
        "\n\n### Expert Evaluation Instructions:\n"
        "- Evaluate each proposal against the multi-level rubric in the criteria table.\n"
        "- Assess the context and quality of the information, not just keywords.\n"
        "- Critically assess the technical feasibility of the proposed solutions.\n"
        "- Assign nuanced scores based on the rubric (Excellent, Good, Insufficient).\n"
        "- The 'Score' you assign for any sub-criterion **MUST NOT** exceed the value in the 'Sub Weight' column.\n"
        "- For each proposal, include: Score (numeric), Brief reason, and Page reference."
    )
    prompt.append(
        "\n\n### CRITICAL: Output Markdown Table Format:\n"
        "Your entire response MUST be a single markdown table. Do not include text before or after the table.\n\n"
        "| Main Criteria | Sub-Criteria | Main Weight | Sub Weight | " +
        " | ".join([f"{name} Score | {name} Reason | {name} Reference" for name in proposal_names]) + " |\n"
        "|---|---|---|---|" + "---|---|---|" * len(proposal_names)
    )
    prompt.append(
        "\n\n### Final Row - Total Score:\n"
        "The last row must be labeled `Total Score` and include the sum of scores and a summary reason for each proposal."
    )
    return "\n".join(prompt)

def clean_evaluation_json(rows):
    cleaned = []
    for row in rows:
        # Skip rows where keys = values (redundant headers)
        if all(str(k).strip() == str(v).strip() for k, v in row.items()):
            continue
        # Skip full separator rows
        if all(re.match(r'^-+$', str(v).strip()) for v in row.values()):
            continue
        cleaned.append({k.strip(): v for k, v in row.items()})
    return cleaned

def sanitize_nan(obj):
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_nan(elem) for elem in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return "N/A"
    else:
        return obj


# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    try:
        print("Received upload request.")

        # Get the RFP and proposal files from the request
        rfp_file = request.files.get('rfp')
        proposal_files = request.files.getlist('proposals')

        # Ensure the upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        rfp_path = None
        proposal_paths = []

        # Save RFP file with a prefixed name
        if rfp_file:
            rfp_filename = f"rfp_{secure_filename(rfp_file.filename)}"
            rfp_path = os.path.join(UPLOAD_FOLDER, rfp_filename)
            print(f"Saving RFP file to: {rfp_path}")
            rfp_file.save(rfp_path)

        # Count existing proposal files to avoid overwriting
        existing_files = os.listdir(UPLOAD_FOLDER)
        existing_proposals = [f for f in existing_files if f.startswith("proposal_")]
        next_index = len(existing_proposals) + 1  # Start from next available index

        # Save Proposal files using their original filenames
        if proposal_files:
            for proposal_file in proposal_files:
                original_name = sanitize_filename(proposal_file.filename)
                proposal_filename = f"proposal_{next_index}_{original_name}"
                # Avoid overwriting if same file name already exists
                proposal_path = os.path.join(UPLOAD_FOLDER, proposal_filename)
                
                print(f"Saving proposal file to: {proposal_path}")
                proposal_file.save(proposal_path)
                proposal_paths.append(proposal_path)
                next_index += 1  # Increment index for the next file

        # Return a response with the file paths
        response = {
            "message": "Files uploaded successfully",
            "rfp_path": rfp_path,
            "proposal_paths": proposal_paths
        }
        print("Response:", response)
        return jsonify(response), 200

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/clear_all', methods=['POST'])
def clear_all_files():
    try:
        if os.path.exists(UPLOAD_FOLDER):
            shutil.rmtree(UPLOAD_FOLDER)
            os.makedirs(UPLOAD_FOLDER)
        return jsonify({"message": "All uploaded files cleared"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to clear files: {str(e)}"}), 500

# CORRECTED AND CLEANED evaluate_files function
@app.route('/evaluate', methods=['POST'])
def evaluate_files():
    try:
        # Step 1: Read essential documents at the beginning
        human_eval_text = read_text_file('evaluationDoc.txt')
        if human_eval_text is None:
            return jsonify({"error": "Crucial file 'evaluationDoc.txt' not found."}), 404

        rfp_page_text = extract_text_from_pdf_page('rfp.pdf', 18)
        if rfp_page_text is None:
            return jsonify({"error": "Crucial file 'rfp.pdf' not found."}), 404
        
        # Step 2: Logic for caching the rubric
        rubric_file_path = 'generated_rubric.json'
        parameter_table = None

        if os.path.exists(rubric_file_path):
            print("Found existing rubric. Loading from file...")
            with open(rubric_file_path, 'r', encoding='utf-8') as f:
                parameter_table = json.load(f)
        else:
            print("No rubric found. Generating a new one...")
            gemini_table_response = extract_table_from_gemini(rfp_page_text)
            if not gemini_table_response:
                return jsonify({"error": "AI failed to extract table from RFP text."}), 500
            
            tables = extract_tables_from_response(gemini_table_response)
            if not tables:
                return jsonify({"error": "Could not parse criteria table from AI response."}), 500
            
            parameter_table = normalize_parameter_table(tables[0])
            
            with open(rubric_file_path, 'w', encoding='utf-8') as f:
                json.dump(parameter_table, f, ensure_ascii=False, indent=4)
            print(f"New rubric saved to {rubric_file_path}")

        # Step 3: Read uploaded proposal files
        proposal_texts = []
        for file_name in sorted(os.listdir(UPLOAD_FOLDER)):
            if file_name.startswith("proposal_"):
                text = clean_text(read_text_file(os.path.join(UPLOAD_FOLDER, file_name)))
                proposal_name = file_name.replace("proposal_", "", 1)
                proposal_texts.append((proposal_name, text))
        
        if not proposal_texts:
            return jsonify({"error": "No proposal files found to evaluate. Please upload them first."}), 400

        # Step 4: Generate enhanced prompt and get AI evaluation
        # FIX: Use the correct variable 'rfp_page_text'
        evaluation_prompt = generate_evaluation_prompt(parameter_table, proposal_texts, clean_text(rfp_page_text), human_eval_text)
        
        generation_config = {"temperature": 0.0}
        safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        
        gemini_output = model.generate_content(
            evaluation_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        print("\n--- RAW GEMINI OUTPUT ---\n")
        print(gemini_output.text)
        print("\n--- END RAW GEMINI OUTPUT ---\n")
        
        # Step 5: Parse and return the result
        parsed_table_json = parse_markdown_table_to_json(gemini_output.text)
        cleaned_output = clean_evaluation_json(parsed_table_json)
        evaluation_table = sanitize_nan(cleaned_output)
        print(evaluation_table)
        
        if not evaluation_table:
             return jsonify({"error": "Parsing the AI evaluation response failed.", "raw_output": gemini_output.text}), 500

        return jsonify({"evaluation_table": evaluation_table}), 200

    except Exception as e:
        print(f"An unexpected error occurred during evaluation: {e}")
        return jsonify({"message": "Evaluation failed.", "error": f"{str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
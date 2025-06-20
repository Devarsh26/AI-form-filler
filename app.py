import streamlit as st
import json
import os
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, List, Optional
import re
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY is not set in the .env file")
else:
    # Mask the token for security
    masked_token = GOOGLE_API_KEY[:4] + "..." + GOOGLE_API_KEY[-4:] if len(GOOGLE_API_KEY) > 8 else "***"
    #print(f"GOOGLE_API_KEY loaded: {masked_token}")

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize session state
if 'current_field_index' not in st.session_state:
    st.session_state.current_field_index = 0
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}
if 'uploaded_json' not in st.session_state:
    st.session_state.uploaded_json = None
if 'error_message' not in st.session_state:
    st.session_state.error_message = None
if 'validation_attempts' not in st.session_state:
    st.session_state.validation_attempts = {}
if 'validation_details' not in st.session_state:
    st.session_state.validation_details = {}
if 'cached_questions' not in st.session_state:
    st.session_state.cached_questions = {}


# Autofill mapping for common field types
AUTOFILL_MAPPING = {
    "name": "name",
    "full name": "name",
    "first name": "given-name",
    "last name": "family-name",
    "email": "email",
    "email address": "email",
    "phone": "tel",
    "phone number": "tel",
    "mobile": "tel",
    "cell": "tel",
    "address": "street-address",
    "street": "street-address",
    "city": "address-level2",
    "state": "address-level1",
    "province": "address-level1",
    "zip": "postal-code",
    "zip code": "postal-code",
    "postal code": "postal-code",
    "country": "country",
    "date of birth": "bday",
    "birthday": "bday",
    "dob": "bday",
    "social security number": "username",
    "ssn": "username",
    "username": "username",
    "password": "current-password",
    "card number": "cc-number",
    "credit card": "cc-number",
    "expiry": "cc-exp",
    "expiration": "cc-exp",
    "cvv": "cc-csc",
    "security code": "cc-csc"
}

def get_autofill_attribute(field_name: str, field_type: str) -> str:
    """Determine the appropriate autofill attribute based on field name and type."""
    field_name_lower = field_name.lower()
    
    # Check if field name contains any of the autofill keywords
    for keyword, autofill_value in AUTOFILL_MAPPING.items():
        if keyword in field_name_lower:
            return autofill_value
    
    # Fallback to field type
    if field_type == "email":
        return "email"
    elif field_type == "phone":
        return "tel"
    elif field_type == "date":
        return "bday"
    elif field_type == "number":
        return "numeric"
    
    return "off"  # Default to off if no match

def generate_question(field_name: str, field_metadata: Dict) -> str:
    """Generate a natural question using LLM with support for multiple choice options."""
    cache_key = f"{field_name}_{field_metadata.get('description', '')}"
    if cache_key in st.session_state.cached_questions:
        return st.session_state.cached_questions[cache_key]
    
    # Add support for multiple choice options
    options_text = ""
    if field_metadata.get('type') in ['radio', 'checkbox']:
        options = field_metadata.get('options', [])
        options_text = "\nAvailable options:\n" + "\n".join([f"- {opt['label']}" for opt in options])
        
        if field_metadata.get('type') == 'checkbox':
            min_sel = field_metadata.get('min_selections', 0)
            max_sel = field_metadata.get('max_selections', len(options))
            options_text += f"\nPlease select between {min_sel} and {max_sel} options."
    
    prompt = f"""Generate a friendly, conversational question to ask for {field_name}. 
    Additional context: {field_metadata.get('description', '')}
    {options_text}
    
    If the field is required, mention that it's required.
    If the field is not required, mention that it's optional.
    
    Make it sound natural and friendly, like a helpful assistant asking a question.
    Keep it concise but informative."""
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        st.session_state.cached_questions[cache_key] = result
        return result
    except Exception as e:
        st.write(f"Debug - Exception in generate_question: {str(e)}")
        required_text = " (required)" if field_metadata.get('required', False) else " (optional)"
        return f"Please select your {field_name}{required_text}"

def validate_with_llm(input_value: str, validation_rule: str, field_name: str, field_description: str = "") -> tuple[bool, str, str]:
    """Use LLM to validate input against a custom validation rule and provide detailed feedback."""
    # If there's a specific validation rule in the form, prioritize it
    if validation_rule:
        prompt = f"""You are a validation expert. Your task is to validate input according to a specific rule.

Field: "{field_name}"
Field Description: "{field_description}"
Validation Rule: "{validation_rule}"
Input to Validate: "{input_value}"

IMPORTANT: The validation rule provided above takes precedence over any general validation rules.
Your task is to validate the input against THIS SPECIFIC RULE ONLY.

If the input is valid, respond with: VALID
If the input is invalid, respond with: INVALID: [error message explaining why]

Then, on a new line, provide an example of a valid input that would pass this validation rule.
Format your response as:

VALID
Example: [example of valid input]

or

INVALID: [error message]
Example: [example of valid input]

Be specific in your error message to help the user understand what's wrong."""
    else:
        # If no specific validation rule, use general field type validation
        prompt = f"""You are a validation expert. Your task is to validate input based on the field type.

Field: "{field_name}"
Field Description: "{field_description}"
Input to Validate: "{input_value}"

Analyze the field name and description to determine the appropriate validation rules.
For example:
- If the field is about SSN, validate it as a social security number
- If the field is about dates, validate it as a date
- If the field is about email, validate it as an email address
- If the field is about phone numbers, validate it as a phone number

If the input is valid, respond with: VALID
If the input is invalid, respond with: INVALID: [error message explaining why]

Then, on a new line, provide an example of a valid input that would pass this validation rule.
Format your response as:

VALID
Example: [example of valid input]

or

INVALID: [error message]
Example: [example of valid input]

Be specific in your error message to help the user understand what's wrong."""

    try:
        response = model.generate_content(prompt)
        if not response.text:
            return False, "Validation failed", "Please try again"
            
        result = response.text.strip()
            
            # Extract validation result and example
            lines = result.split('\n')
            validation_line = lines[0].strip()
            example_line = lines[1].strip() if len(lines) > 1 else "Example: No example provided"
            
            if validation_line.startswith("VALID"):
                return True, "", example_line.replace("Example:", "").strip()
            elif validation_line.startswith("INVALID:"):
                error_message = validation_line[8:].strip()
                return False, error_message, example_line.replace("Example:", "").strip()
            else:
                # If the model didn't follow the format, try to interpret the response
                if "valid" in validation_line.lower() and "invalid" not in validation_line.lower():
                    return True, "", example_line.replace("Example:", "").strip()
                else:
                    return False, validation_line, example_line.replace("Example:", "").strip()
    except Exception as e:
        st.write(f"Debug - Exception in validate_with_llm: {str(e)}")
        return False, f"Validation failed with error: {str(e)}", "No example available"

def validate_input(input_value: str, field_metadata: Dict) -> tuple[bool, str, str]:
    """Validate input with support for multiple choice options."""
    field_type = field_metadata.get('type', 'text')
    field_name = field_metadata.get('name', '')
    
    # Handle radio and checkbox inputs first, without using LLM
    if field_type in ['radio', 'checkbox']:
        options = field_metadata.get('options', [])
        valid_values = [opt['value'] for opt in options]
        
        if field_type == 'radio':
            if not input_value:
                return False, "Please select an option", ", ".join(valid_values)
            if input_value not in valid_values:
                return False, f"Please select one of the available options: {', '.join(valid_values)}", ", ".join(valid_values)
            return True, "", input_value
            
        else:  # checkbox
            try:
                selected_values = json.loads(input_value) if isinstance(input_value, str) else input_value
                if not isinstance(selected_values, list):
                    return False, "Please select at least one option", str(valid_values)
                
                if not all(val in valid_values for val in selected_values):
                    return False, "One or more selected options are invalid", str(valid_values)
                
                min_sel = field_metadata.get('min_selections', 0)
                max_sel = field_metadata.get('max_selections', len(options))
                
                if len(selected_values) < min_sel:
                    return False, f"Please select at least {min_sel} option(s)", str(valid_values)
                if len(selected_values) > max_sel:
                    return False, f"Please select at most {max_sel} option(s)", str(valid_values)
            except json.JSONDecodeError:
                return False, "Invalid selection format", str(valid_values)
                
    # For all other field types, including SSN, use LLM validation
    return validate_with_llm(input_value, field_metadata.get('validation', ''), 
                           field_name, field_metadata.get('description', ''))

def should_show_field_ai(field: Dict, form_data: Dict) -> bool:
    """Determine if a field should be shown based on visibility rules and previous answers."""
    # If no visibility rule, show the field
    if 'visibility' not in field:
        return True
    
    visibility_rule = field['visibility'].lower()
    
    # Handle common visibility patterns without using LLM
    if "previous answer to us citizen is yes" in visibility_rule:
        # Check if US Citizen was answered as "Yes"
        us_citizen_answer = form_data.get("US Citizen", "").lower()
        return us_citizen_answer == "yes"
    
    # Add more visibility rule patterns here as needed
    # For example:
    # if "previous answer to x is y" in visibility_rule:
    #     field_name = extract_field_name(visibility_rule)
    #     expected_value = extract_expected_value(visibility_rule)
    #     return form_data.get(field_name, "").lower() == expected_value.lower()
    
    # Default to showing the field if we can't determine visibility
    return True

def render_input_field(field: Dict):
    """Render the appropriate input field based on type and handle value storage."""
    field_type = field.get('type', 'text')
    field_name = field['name']
    
    if field_type == 'radio':
        options = field.get('options', [])
        radio_key = f"radio_{field_name}"
        selected = st.radio(
            "Select an option",
            options=[opt['value'] for opt in options],
            format_func=lambda x: next((opt['label'] for opt in options if opt['value'] == x), x),
            key=radio_key
        )
        if selected:
            st.session_state.form_data[field_name] = selected
        return selected

    elif field_type == 'checkbox':
        options = field.get('options', [])
        checkbox_key = f"checkbox_{field_name}"
        selected = st.multiselect(
            "Select options",
            options=[opt['value'] for opt in options],
            format_func=lambda x: next((opt['label'] for opt in options if opt['value'] == x), x),
            key=checkbox_key
        )
        if selected:
            st.session_state.form_data[field_name] = selected
        return selected

    else:
        # Handle all other input types, including SSN, with a simple text input
        return st.text_input("Your answer", key=f"input_{field_name}")

def main():
    st.title("Form Filling Bot")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload your form JSON", type=['json'])
    
    if uploaded_file is not None:
        try:
            form_data = json.load(uploaded_file)
            if 'fields' not in form_data:
                st.error("Invalid JSON format. Must contain a 'fields' array.")
                return
            
            st.session_state.uploaded_json = form_data
            
            # Display form title and description if available
            if 'title' in form_data:
                st.header(form_data['title'])
            if 'description' in form_data:
                st.write(form_data['description'])
            
            # Calculate visible fields using simple visibility rules
            visible_fields = [field for field in form_data['fields'] if should_show_field_ai(field, st.session_state.form_data)]
            
            # Progress bar
            progress = st.session_state.current_field_index / len(visible_fields) if visible_fields else 0
            st.progress(progress)
            st.write(f"Question {st.session_state.current_field_index + 1} of {len(visible_fields)}")
            
            # Process each field
            if st.session_state.current_field_index < len(visible_fields):
                field = visible_fields[st.session_state.current_field_index]
                field_name = field['name']
                field_type = field.get('type', 'text')
                is_required = field.get('required', False)
                
                # Generate question
                question = generate_question(field_name, field)
                st.write(question)
                
                # Get autofill attribute
                autofill_attr = get_autofill_attribute(field_name, field_type)
                
                # Create a custom HTML input with proper autofill attributes (for Google Autofill demo)
                    input_id = f"autofill_input_{st.session_state.current_field_index}"
                    st.markdown(
                        f"""
                        <div style="margin-bottom: 1rem;">
                            <input 
                            type="{field_type}" 
                                id="{input_id}" 
                                name="{field_name}"
                                class="stTextInput" 
                                autocomplete="{autofill_attr}" 
                            placeholder="(Google Autofill Demo)"
                                style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px;"
                            />
                        </div>
                    <div style='color: #888; font-size: 0.9em; margin-bottom: 0.5em;'>Above: Google Autofill Demo (not used for submission)</div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                # Render the appropriate input field
                user_input = render_input_field(field)
                
                # Show validation attempts for this field
                if field_name in st.session_state.validation_attempts:
                    st.warning(f"Previous attempts: {st.session_state.validation_attempts[field_name]}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Submit"):
                        if user_input:
                            # Validate the input
                            is_valid, error_message, example = validate_input(user_input, field)
                            
                            if field_name not in st.session_state.validation_attempts:
                                st.session_state.validation_attempts[field_name] = 0
                            st.session_state.validation_attempts[field_name] += 1
                            st.session_state.validation_details[field_name] = {
                                "is_valid": is_valid,
                                "error_message": error_message,
                                "example": example
                            }
                            
                            if is_valid:
                                st.session_state.form_data[field_name] = user_input
                                st.session_state.current_field_index += 1
                                st.rerun()
                            else:
                                st.error(error_message)
                                if example:
                                    st.info(f"Example of valid input: {example}")
                        else:
                            if is_required:
                                st.warning("This field is required. Please provide an answer.")
                            else:
                                st.warning("Please provide an answer or click Skip if this field is optional.")
                with col2:
                    if st.button("Skip"):
                        if is_required:
                            st.warning("This field is required and cannot be skipped.")
                        else:
                            st.session_state.current_field_index += 1
                            st.rerun()
            
            # Show completion and download option
            if st.session_state.current_field_index >= len(visible_fields):
                st.success("Form completed!")
                st.json(st.session_state.form_data)
                
                # Download button
                json_str = json.dumps(st.session_state.form_data, indent=2)
                st.download_button(
                    label="Download filled form",
                    data=json_str,
                    file_name="filled_form.json",
                    mime="application/json"
                )
                
                if st.button("Start Over"):
                    st.session_state.current_field_index = 0
                    st.session_state.form_data = {}
                    st.session_state.validation_attempts = {}
                    st.session_state.validation_details = {}
                    st.rerun()
        
        except json.JSONDecodeError:
            st.error("Invalid JSON file. Please upload a valid JSON file.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            st.info("Please try uploading the file again or contact support if the issue persists.")

if __name__ == "__main__":
    main() 
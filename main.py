import streamlit as st
import google.generativeai as genai
import anthropic
import pandas as pd
import tempfile
import os
import time
import base64
import io
import mimetypes
import openpyxl
import json
import sys
import copy
from openai import OpenAI
from PIL import Image
from google.cloud import firestore
from google.api_core.exceptions import NotFound
from google.oauth2 import service_account
from datetime import datetime

# --- Define USER_INFO TEMPLATE ---

USER_INFO_TEMPLATE = {
    "name": "",
    "DOB": "",
    "nationality": "",
    "Language": "English (native)",
    "datetime": "",
    "system": ""
}

# --- Authenticate to Firestore with the JSON account key ---

@st.cache_resource
def get_db_client():
    """
    Initializes and returns a Firestore client using credentials from Streamlit secrets.
    """
    key_dict = json.loads(st.secrets["textkey"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project="")
    return db

# --- Initialize Firestore client ---

db = get_db_client()

# --- Password lock, uncomment if required ---

# PASS = st.secrets["passw"]
# password = st.sidebar.text_input("Password", type="password")

# if PASS != password:
#    st.stop()

# --- API Initialization ---

client_openai = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
client_anthropic = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

# --- Model Selection ---

openai_models = ["gpt-4o", "o1-preview", "o1-mini"]
gemini_models = ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest"]
anthropic_models = ["claude-3-5-sonnet-20240620"]
all_models = openai_models + gemini_models + anthropic_models

# --- Firestore Collection References ---

CONVERSATIONS_COLLECTION = "conversations"
CHAT_HISTORY_COLLECTION = "chat_history"

# --- Database Functions ---

def save_conversation(conversation_name):
    """
    Saves the current conversation to Firestore under the given conversation name.
    If a conversation with the same name exists, it overwrites the existing chat history.
    """
    conversations_ref = db.collection(CONVERSATIONS_COLLECTION)
    query = conversations_ref.where("name", "==", conversation_name).limit(1).stream()
    existing_doc = next(query, None)

    if existing_doc:
        conversation_id = existing_doc.id
        # Delete existing chat history for this conversation
        chat_history_ref = conversations_ref.document(conversation_id).collection(CHAT_HISTORY_COLLECTION)
        for doc in chat_history_ref.stream():
            doc.reference.delete()
    else:
        # Create a new conversation document
        new_conv_ref = conversations_ref.add({"name": conversation_name, "created_at": firestore.SERVER_TIMESTAMP})
        conversation_id = new_conv_ref[1].id

    # Reference to the chat history subcollection
    chat_history_ref = conversations_ref.document(conversation_id).collection(CHAT_HISTORY_COLLECTION)

    for idx, msg in enumerate(st.session_state.messages):
        role = msg.get("role")
        content = msg.get("content")

        # Sanitize the 'content' field to ensure compatibility with Firestore
        if isinstance(content, dict):
            sanitized_content = {k: v for k, v in content.items() if k != "data"}
            try:
                content_to_save = json.dumps(sanitized_content)
            except (TypeError, OverflowError) as e:
                st.error(f"Error serializing message content at index {idx}: {e}")
                continue 
        elif isinstance(content, list):
            try:
                content_to_save = json.dumps(content)
            except (TypeError, OverflowError) as e:
                st.error(f"Error serializing message content at index {idx}: {e}")
                continue
        else:
            content_to_save = content

        # Ensure content size is within Firestore limits
        if isinstance(content_to_save, str) and len(content_to_save.encode('utf-8')) > 900 * 1024:
            st.error(f"Message content at index {idx} exceeds size limits and was not saved.")
            continue

        # Add the sanitized message to Firestore
        try:
            chat_history_ref.add({
                "role": role,
                "content": content_to_save,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            st.error(f"Failed to save message at index {idx}: {e}")
            continue

    st.success(f"Saved conversation: '{conversation_name}'")

def load_conversation(conversation_id):
    """
    Loads a conversation from Firestore using the provided conversation ID.
    Populates the session state with the loaded messages.
    """
    conversations_ref = db.collection(CONVERSATIONS_COLLECTION).document(conversation_id)
    chat_history_ref = conversations_ref.collection(CHAT_HISTORY_COLLECTION).order_by("timestamp")

    st.session_state.messages = []
    try:
        chat_docs = chat_history_ref.stream()
        for doc in chat_docs:
            data = doc.to_dict()
            content = data.get("content")
            try:
                # Attempt to deserialize JSON strings back to Python objects
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass 
            st.session_state.messages.append({"role": data.get("role"), "content": content})
    except NotFound:
        st.error("Conversation not found.")

def clear_conversation():
    """
    Clears the current conversation from the session state.
    """
    st.session_state.messages = []

# --- Helper Functions ---

def stream_response(response):
    """
    Processes the streamed response from the API and yields chunks of text.
    """
    for chunk in response:
        try:
            if hasattr(chunk, 'finish_message') and chunk.finish_message:
                yield chunk.finish_message.text
            elif hasattr(chunk, 'text'):
                yield chunk.text
            else:
                yield ''
        except AttributeError as e:
            st.error(f"Error processing chunk: {e}")
            yield "An error occurred while processing the response."

def handle_file(uploaded_file):
    """
    Handles the uploaded file based on its MIME type and displays appropriate content.
    """
    file_type = uploaded_file.type

    if file_type.startswith('image/'):
        st.image(uploaded_file)
    elif file_type.startswith('audio/'):
        st.audio(uploaded_file)
    elif file_type.startswith('video/'):
        st.video(uploaded_file)
    elif file_type.startswith('application/pdf'):
        st.success(f"Uploaded PDF: {uploaded_file.name}")
    elif file_type == 'text/csv':
        df = pd.read_csv(uploaded_file)
        st.dataframe(df)
    elif file_type in [
        'application/vnd.ms-excel', 
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ]:
        df = pd.read_excel(uploaded_file)
        st.dataframe(df)
    elif file_type.startswith('text/plain'):
        text = uploaded_file.read().decode("utf-8")
        st.markdown(text)
    else:
        st.warning("Unsupported file type.")

def convert_image_to_base64(file, max_size_mb=5):
    """
    Converts an image file to a base64 string, ensuring it does not exceed the specified size.
    """
    max_size_bytes = max_size_mb * 1024 * 1024

    try:
        # Open the image using PIL
        image = Image.open(file)
        img_format = image.format

        # Initialize compression parameters
        quality = 90 
        resize_factor = 0.9 
        min_quality = 20
        min_dimension = 200

        while True:
            img_bytes = io.BytesIO()

            # Save image based on its format
            if img_format in ["JPEG", "JPG"]:
                image.save(img_bytes, format='JPEG', quality=quality, optimize=True)
            else:
                if img_format != "PNG":
                    image = image.convert("RGB")
                image.save(img_bytes, format='PNG' if img_format == "PNG" else 'JPEG', 
                           quality=quality if img_format != "PNG" else None, 
                           optimize=True)

            img_size = img_bytes.tell()
            encoded_size = (img_size * 4) / 3

            if encoded_size <= max_size_bytes:
                # Image meets size requirements
                break

            # Adjust compression parameters
            if img_format in ["JPEG", "JPG"] and quality > min_quality:
                quality -= 10
            else:
                width, height = image.size
                new_width = int(width * resize_factor)
                new_height = int(height * resize_factor)

                # Prevent image from becoming too small
                if new_width < min_dimension or new_height < min_dimension:
                    st.warning("Unable to compress the image below the size limit.")
                    return None

                image = image.resize((new_width, new_height), Image.ANTIALIAS)

        # Encode the image to base64
        encoded_image = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        return encoded_image

    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None

def prepare_api_messages(user=True):
    """
    Prepares the messages by prepending USER_INFO to each user message.
    Ensures that the original session messages remain unaltered.
    """
    api_messages = []
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            if user:
                # Create a copy of USER_INFO with the current datetime
                user_info = USER_INFO_TEMPLATE.copy()
                user_info['datetime'] = datetime.now().isoformat()

                if isinstance(msg["content"], str):
                    # Prepend USER_INFO as a JSON string followed by the original content
                    content = f"USER_INFO: {json.dumps(user_info)}\n{msg['content']}"
                elif isinstance(msg["content"], dict):
                    # Prepend USER_INFO by merging dictionaries
                    content = {"USER_INFO": user_info, "content": msg["content"]}
                elif isinstance(msg["content"], list):
                    # Prepend USER_INFO as a separate dict in the list
                    content = [{"USER_INFO": user_info}] + msg["content"]
                else:
                    # For any other type, convert USER_INFO to string and prepend
                    content = f"USER_INFO: {json.dumps(user_info)}\n{str(msg['content'])}"
            else:
                content = msg["content"]

            api_messages.append({"role": msg["role"], "content": content})
        else:
            api_messages.append(msg)
    return api_messages

# --- AI Completion Functions ---

def open_ai_completion(uploaded_file):
    """
    Handles the OpenAI model completions, including image generation and file processing.
    """
    models_requiring_structured = {"o1-mini", "o1-preview"}
    image_command = "/image "

    # Determine MIME type if a file is uploaded
    if uploaded_file:
        mime_type, _ = mimetypes.guess_type(uploaded_file.name)
    else:
        mime_type = None

    # Initialize user_content and locate the latest user message
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        user_content = st.session_state.messages[-1]["content"]
        user_message_index = len(st.session_state.messages) - 1
    else:
        user_content = ""
        user_message_index = None

    # Handle image generation requests
    if isinstance(user_content, str) and user_content.startswith(image_command):
        image_description = user_content[len(image_command):].strip()
        try:
            image_response = client_openai.images.generate(
                model="dall-e-3",
                prompt=image_description,
                size="1024x1024",
                quality="hd",
                n=1,
            )
            image_url = image_response.data[0].url
            st.image(image_url, caption=image_description)
            st.session_state.messages.append({
                "role": "assistant",
                "content": {
                    "type": "image",
                    "url": image_url,
                    "description": image_description
                }
            })
        except Exception as e:
            st.error(f"Image generation failed: {e}")
        
        # Exit after handling image generation 
        return  

    # Handle uploaded files if any
    if uploaded_file:
        if mime_type in [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel"
        ]:
            # Process Excel files
            try:
                df = pd.read_excel(uploaded_file)
                df_string = df.to_string(index=False)

                if user_message_index is not None:
                    # Append DataFrame string to existing user message
                    existing_content = st.session_state.messages[user_message_index]["content"]
                    if isinstance(existing_content, str):
                        updated_content = f"{existing_content}\nHere is the data from the uploaded Excel file:\n{df_string}"
                    elif isinstance(existing_content, list):
                        updated_content = existing_content + [f"Here is the data from the uploaded Excel file:\n{df_string}"]
                    else:
                        # Unexpected format
                        updated_content = existing_content 
                    st.session_state.messages[user_message_index]["content"] = updated_content
                else:
                    # If no existing user message, append a new one
                    st.session_state.messages.append({
                        "role": "user",
                        "content": f"Here is the data from the uploaded Excel file:\n{df_string}"
                    })
            except Exception as e:
                st.error(f"Failed to process Excel file: {e}")
                # Exit if Excel processing fails
                return  

        elif mime_type and mime_type.startswith("image/"):
            # Process image files
            try:
                base64_image = convert_image_to_base64(uploaded_file)
                if base64_image is None:
                    st.error("Failed to convert image to base64.")
                    return

                image_data_uri = f"data:{mime_type};base64,{base64_image}"

                if user_message_index is not None:
                    # Append image URL to existing user message
                    existing_content = st.session_state.messages[user_message_index]["content"]
                    if isinstance(existing_content, str):
                        updated_content = existing_content + f"\n![Uploaded Image]({image_data_uri})"
                    elif isinstance(existing_content, list):
                        updated_content = existing_content + [{
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_uri,
                            },
                        }]
                    else:
                         # Unexpected format
                        updated_content = existing_content 
                    st.session_state.messages[user_message_index]["content"] = updated_content
                else:
                    # If no existing user message, append a new one
                    st.session_state.messages.append({
                        "role": "user",
                        "content": {
                            "type": "image_url",
                            "image_url": image_data_uri,
                        }
                    })

            except Exception as e:
                st.error(f"Failed to process image file: {e}")
                # Exit if image processing fails
                return  

        else:
            st.error("Unsupported file type uploaded.")
             # Exit if file type is unsupported
            return 

    # Cleanup Process to Remove Media Content from User Messages
    def clean_user_messages():
        """
        Cleans the user messages by removing media content such as images and dataframes.
        Retains only the textual parts of the messages.
        """
        if not uploaded_file:
            return

        for idx, msg in enumerate(st.session_state.messages):
            if msg["role"] == "user":
                content = msg.get("content")
                has_media = False
                text_parts = []

                if isinstance(content, list):
                    # Separate text and media parts
                    new_content = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "image_url":
                            has_media = True
                            # Skip adding media data to text_parts
                        elif isinstance(item, dict) and item.get("type") == "text":
                            text_parts.append(item["text"])
                        elif isinstance(item, str):
                            text_parts.append(item)
                        else:
                            # Handle unexpected types by converting to string
                            text_parts.append(str(item))
                    # Replace content with text-only
                    st.session_state.messages[idx]["content"] = " ".join(text_parts).strip()

                elif isinstance(content, str):
                    # Check and remove image markdown or DataFrame references
                    if "Here is the data from the uploaded Excel file:" in content or "![" in content:
                        has_media = True
                        split_content = content.split("\nHere is the data from the uploaded Excel file:", 1)
                        if len(split_content) > 1:
                            text_parts.append(split_content[0])
                        else:
                            # Attempt to remove image markdown
                            text_parts = [line for line in content.split("\n") if not line.strip().startswith("![")]
                        st.session_state.messages[idx]["content"] = " ".join(text_parts).strip()

                elif isinstance(content, dict):
                    # Handle dict-based content
                    if content.get("type") in ["image_url", "dataframe"]:
                        has_media = True
                        st.session_state.messages[idx]["content"] = ""
                    elif content.get("type") == "text":
                        text_parts.append(content["text"])
                        st.session_state.messages[idx]["content"] = " ".join(text_parts).strip()

                if has_media:
                    # Continue cleaning other messages
                    continue

    # Invoke the cleanup function
    clean_user_messages()

    # Prepare API Messages for Completion Request
    if uploaded_file:
        # Deep copy to preserve the original messages
        api_messages = copy.deepcopy(st.session_state.messages)
    else:
        # Prepare messages normally if no file is uploaded
        api_messages = copy.deepcopy(prepare_api_messages())

    # Adjust messages based on MIME type for API consumption
    if uploaded_file:
        # Modify api_messages to include media content if necessary
        for m in api_messages:
            if m["role"] == "user":
                content = m["content"]
                if isinstance(content, list):
                    pass  # Already a list
                elif isinstance(content, dict):
                    m["content"] = [m["content"]]
                else:
                    # Convert string content to list if necessary
                    m["content"] = [{"type": "text", "text": content}]

                if mime_type and mime_type.startswith("image/"):
                    m["content"].append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{convert_image_to_base64(uploaded_file)}",
                        },
                    })
                elif mime_type in [
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.ms-excel"
                ]:
                    try:
                        df = pd.read_excel(uploaded_file)
                        df_string = df.to_string(index=False)
                        m["content"].append({
                            "type": "text",
                            "text": f"Here is the data from the uploaded Excel file:\n{df_string}"
                        })
                    except Exception as e:
                        st.error(f"Failed to process Excel file for API messages: {e}")

    # Handle Models Requiring Structured Messages 
    if st.session_state.selected_model in models_requiring_structured:
        structured_messages = []
        for m in api_messages:
            if isinstance(m["content"], list):
                structured_content = []
                for item in m["content"]:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            structured_content.append({"type": "text", "text": item["text"]})
                        elif item.get("type") == "image_url":
                            structured_content.append({"type": "image_url", "url": item["image_url"]["url"]})
                        # Add other types if necessary
                    elif isinstance(item, str):
                        structured_content.append({"type": "text", "text": item})
                    else:
                        # Handle unexpected types
                        structured_content.append({"type": "text", "text": str(item)})
                structured_messages.append({
                    "role": m["role"],
                    "content": structured_content
                })
            elif isinstance(m["content"], dict):
                if m["content"].get("type") == "image_url":
                    structured_messages.append({
                        "role": m["role"],
                        "content": [{"type": "image_url", "url": m["content"]["image_url"]["url"]}]
                    })
                elif m["content"].get("type") == "text":
                    structured_messages.append({
                        "role": m["role"],
                        "content": [{"type": "text", "text": m["content"]["text"]}]
                    })
                
            else:
                # Assume it's a text string
                structured_messages.append({
                    "role": m["role"],
                    "content": [{"type": "text", "text": m["content"]}]
                })
        try:
            # Make the completion request
            completion = client_openai.chat.completions.create(
                model=st.session_state.selected_model,
                messages=structured_messages,
                stream=False,
            )
            assistant_msg = completion.choices[0].message.content
            st.write(assistant_msg)
            st.session_state.messages.append({"role": "assistant", "content": assistant_msg})
        except Exception as e:
            st.error(f"Completion failed: {e}")

    else:
        # Handle models that don't require structured messages
        try:
            # Send the original api_messages
            completion = client_openai.chat.completions.create(
                model=st.session_state.selected_model,
                messages=[{"role": m["role"], "content": m["content"]} for m in api_messages],
                stream=True,
            )
            response = st.write_stream(completion)
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.error(f"Completion failed: {e}")

def google_gemini_completion(uploaded_file):
    """
    Handles the Google Gemini model completions, including file uploads.
    """
    model_name = st.session_state.get("selected_model", "default-model")
    model = genai.GenerativeModel(model_name=model_name)

    # Prepare API messages with USER_INFO
    api_messages = prepare_api_messages()
    prompt = "\n".join([
        m.get('content', '') if not isinstance(m.get('content'), dict) else m.get('content', {}).get('description', '') 
        for m in api_messages
    ])

    try:
        if uploaded_file:
            file_type = uploaded_file.type
            if file_type in [
                'application/vnd.ms-excel', 
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ]:
                # Append Excel data to prompt
                df = pd.read_excel(uploaded_file)
                prompt = df.to_string() + "\n" + prompt
                response = model.generate_content(prompt, stream=True)
            else:
                # Handle image or other file types
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                    tmp_file.write(uploaded_file.getbuffer())
                    temp_file_path = tmp_file.name
                file = genai.upload_file(path=temp_file_path)
                while file.state.name == "PROCESSING":
                    time.sleep(5)
                    file = genai.get_file(file.name)
                os.remove(temp_file_path)
                response = model.generate_content([file, prompt], stream=True)

        else:
            # Generate content without files
            response = model.generate_content(prompt, stream=True)

        # Stream and display the response
        full_response = st.write_stream(stream_response(response))

        # Clean up the assistant message if it starts with "assistant:" --- Gemini bug?
        if full_response.lower().startswith("assistant:"):
            full_response = full_response[len("assistant:"):].strip()
        st.session_state.messages.append({"role": "assistant", "content": full_response})
    except Exception as e:
        st.error(f"An error occurred: {e}")

def anthropic_completion(uploaded_file):
    """
    Handles the Anthropic model completions, including media content integration and cleanup.
    """
    try:
        cleaned_messages = []

        # Clean consecutive user messages
        for msg in st.session_state.messages:
            if (
                msg["role"] == "user" 
                and cleaned_messages 
                and cleaned_messages[-1]["role"] == "user"
            ):
                cleaned_messages[-1] = msg
            else:
                cleaned_messages.append(msg)

        # Handle the uploaded file
        if uploaded_file:
            mime_type, _ = mimetypes.guess_type(uploaded_file.name)

            # Define valid MIME types
            valid_image_mime_types = ["image/jpeg", "image/png", "image/gif"]
            valid_excel_mime_types = [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel"
            ]

            if mime_type in valid_image_mime_types:
                # Handle image upload
                image_media_type = mime_type
                image_data = convert_image_to_base64(uploaded_file)

                if image_data is None:
                    st.error("Failed to convert image to base64.")
                    return

                image_content = {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_data,
                    },
                }

                # Integrate the image into the last user message if possible
                if cleaned_messages and cleaned_messages[-1]["role"] == "user":
                    last_content = cleaned_messages[-1].get("content")

                    if isinstance(last_content, str):
                        # Convert string to dict with type "text"
                        text_content = {
                            "type": "text",
                            "text": last_content
                        }
                        cleaned_messages[-1]["content"] = [text_content, image_content]
                    elif isinstance(last_content, list):
                        # Ensure all existing content items are dicts
                        new_content = []
                        for item in last_content:
                            if isinstance(item, str):
                                new_content.append({"type": "text", "text": item})
                            elif isinstance(item, dict):
                                new_content.append(item)
                            else:
                                new_content.append({"type": "text", "text": str(item)})
                        # Append the image content
                        new_content.append(image_content)
                        cleaned_messages[-1]["content"] = new_content
                    elif isinstance(last_content, dict):
                        # Convert single dict to list
                        cleaned_messages[-1]["content"] = [last_content, image_content]
                    else:
                        # Handle unexpected formats
                        cleaned_messages[-1]["content"] = [image_content]
                else:
                    # Append a new user message with the image
                    image_message = {
                        "role": "user",
                        "content": [image_content],
                    }
                    cleaned_messages.append(image_message)

            elif mime_type in valid_excel_mime_types:
                # Handle Excel upload
                try:
                    df = pd.read_excel(uploaded_file)
                except Exception as e:
                    st.error(f"Failed to read Excel file: {e}")
                    return

                df_string = df.to_string(index=False)
                dataframe_content = {
                    "type": "text",
                    "text": f"```\n{df_string}\n```"
                }

                # Integrate the DataFrame into the last user message if possible
                if cleaned_messages and cleaned_messages[-1]["role"] == "user":
                    last_content = cleaned_messages[-1].get("content")

                    if isinstance(last_content, str):
                        # Convert string to dict with type "text"
                        text_content = {
                            "type": "text",
                            "text": last_content
                        }
                        cleaned_messages[-1]["content"] = [text_content, dataframe_content]
                    elif isinstance(last_content, list):
                        # Ensure all existing content items are dicts
                        new_content = []
                        for item in last_content:
                            if isinstance(item, str):
                                new_content.append({"type": "text", "text": item})
                            elif isinstance(item, dict):
                                new_content.append(item)
                            else:
                                new_content.append({"type": "text", "text": str(item)})
                        # Append the dataframe content
                        new_content.append(dataframe_content)
                        cleaned_messages[-1]["content"] = new_content
                    elif isinstance(last_content, dict):
                        # Convert single dict to list
                        cleaned_messages[-1]["content"] = [last_content, dataframe_content]
                    else:
                        # Handle unexpected formats
                        cleaned_messages[-1]["content"] = [dataframe_content]
                else:
                    # Append a new user message with the dataframe
                    dataframe_message = {
                        "role": "user",
                        "content": [dataframe_content],
                    }
                    cleaned_messages.append(dataframe_message)

            else:
                st.error("Unsupported file type. Please upload a JPEG, PNG, GIF image or an Excel file.")
                return

        # Prepare API messages with USER_INFO
        if uploaded_file:
            api_messages = cleaned_messages
        else:
            api_messages = prepare_api_messages()

        # Make the API call with the cleaned and updated messages
        with client_anthropic.messages.stream(
            max_tokens=4096,
            messages=api_messages,
            model=st.session_state["selected_model"],
        ) as stream:
            response = st.write_stream(stream_response(stream))

        # Append the assistant's response to the session messages
        assistant_message = {"role": "assistant", "content": response}
        st.session_state.messages.append(assistant_message)

        # Clean up the user message by removing image or dataframe data
        if uploaded_file:
            for idx, msg in enumerate(st.session_state.messages):
                if msg["role"] == "user":
                    content = msg.get("content")
                    has_media = False
                    text_parts = []

                    if isinstance(content, list):
                        # Separate text and media parts
                        for item in content:
                            if isinstance(item, dict) and item.get("type") in ["image", "dataframe"]:
                                has_media = True
                                # Skip adding media data to text_parts
                            elif isinstance(item, dict) and item.get("type") == "text":
                                text_parts.append(item["text"])
                            elif isinstance(item, str):
                                text_parts.append(item)
                            else:
                                # Handle unexpected types by converting to string
                                text_parts.append(str(item))
                    elif isinstance(content, dict):
                        if content.get("type") in ["image", "dataframe"]:
                            has_media = True
                        elif content.get("type") == "text":
                            text_parts.append(content["text"])
                    elif isinstance(content, str):
                        text_parts.append(content)

                    if has_media:
                        # Replace the user message with text-only content
                        new_user_message = {
                            "role": "user",
                            "content": " ".join(text_parts).strip()
                        }
                        st.session_state.messages[idx] = new_user_message
                        break  # Assuming only one media-containing user message

        # Ensure role alternation is maintained
        if len(st.session_state.messages) >= 2:
            last_msg = st.session_state.messages[-1]
            second_last_msg = st.session_state.messages[-2]
            if last_msg["role"] == second_last_msg["role"]:
                st.error("Role alternation issue detected in message history.")
                # Optionally, handle the inconsistency here

    except Exception as e:
        st.error(f"An error occurred: {e}")

# --- Session State Initialization ---

# Initialize selected_model and messages in session state if not present
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = all_models[0] 

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Sidebar Functions ---

def get_all_conversations():
    """
    Retrieves all conversations from Firestore, ordered by creation time descending.
    """
    conversations_ref = db.collection(CONVERSATIONS_COLLECTION).order_by("created_at", direction=firestore.Query.DESCENDING)
    return list(conversations_ref.stream())

# Fetch all conversations for the sidebar
conversations = get_all_conversations()
conversation_names = [conv.to_dict()["name"] for conv in conversations]

# Model selection dropdown in the sidebar
st.session_state["selected_model"] = st.sidebar.selectbox(
    "Model:",
    options=all_models
)

# Conversation loading dropdown in the sidebar
selected_conversation = st.sidebar.selectbox(
    "Load conversation",
    ["New conversation"] + conversation_names
)

# Load selected conversation if not new
if selected_conversation != "New conversation":
    selected_conv = next((conv for conv in conversations if conv.to_dict()["name"] == selected_conversation), None)
    if selected_conv:
        conv_id = selected_conv.id
        load_conversation(conv_id)

# Conversation saving input and button
conversation_name = st.sidebar.text_input("Save conversation:")
if st.sidebar.button("Save", use_container_width=True):
    if conversation_name:
        save_conversation(conversation_name)
    else:
        st.warning("Please enter a name for the conversation.")

# Conversation deletion button
if selected_conversation != "New conversation":
    if st.sidebar.button("Delete", use_container_width=True):
        selected_conv = next((conv for conv in conversations if conv.to_dict()["name"] == selected_conversation), None)
        if selected_conv:
            conv_id = selected_conv.id
            # Delete all chat history
            chat_history_ref = db.collection(CONVERSATIONS_COLLECTION).document(conv_id).collection(CHAT_HISTORY_COLLECTION)
            for doc in chat_history_ref.stream():
                doc.reference.delete()
            # Delete the conversation document
            db.collection(CONVERSATIONS_COLLECTION).document(conv_id).delete()
            # Clear session messages and notify the user
            st.session_state.messages = []
            st.error(f"Deleted conversation: {selected_conversation}")

# Clear conversation button
if st.sidebar.button("Clear", on_click=clear_conversation, use_container_width=True):
    pass

# --- Attachment Management ---

# Define allowed file types for specific models
available_models = {
    "gpt-4o": ["png", "jpg", "jpeg", "webp", "xlsx"], 
    "gemini-1.5-flash-latest": None,
    "gemini-1.5-pro-latest": None,
    "claude-3-5-sonnet-20240620": ["png", "jpg", "jpeg", "webp", "xlsx"]
}

uploaded_file = None

# Determine allowed file types based on the selected model
if st.session_state["selected_model"] in available_models:
    allowed_file_types = available_models[st.session_state["selected_model"]]
    if allowed_file_types is not None:
        # Display the file uploader with specific file types
        uploaded_file = st.sidebar.file_uploader("Attachment", type=allowed_file_types)
    else:
        # Allow all file types if none are specified
        uploaded_file = st.sidebar.file_uploader("Attachment")

# Handle the uploaded file if present
if uploaded_file:
    handle_file(uploaded_file)

# --- Chat Display ---

# Display each message in the chat with appropriate avatars
for message in st.session_state.messages:
    avatar = "🕹️" if message["role"] == "user" else "👾"
    with st.chat_message(message["role"], avatar=avatar):
        if isinstance(message["content"], dict) and message["content"].get("type") == "image":
            st.image(message["content"]["url"], caption=message["content"]["description"])
        else:
            st.markdown(message["content"])

# --- User Input ---

# Capture user input and handle AI responses
if prompt := st.chat_input("..."):
    # Append user message to session state
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🕹️"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="👾"):
        # Call the appropriate completion function based on the selected model
        if st.session_state["selected_model"] in openai_models:
            open_ai_completion(uploaded_file)
        elif st.session_state["selected_model"] in gemini_models:
            google_gemini_completion(uploaded_file)
        elif st.session_state["selected_model"] in anthropic_models:
            anthropic_completion(uploaded_file)
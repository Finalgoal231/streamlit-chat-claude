Multi AI Platform Streamlit App
This application provides an interactive chat interface powered by multiple AI models, including OpenAI's GPT-4, Google's Gemini, and Anthropic's Claude. It includes features such as conversation saving/loading, file uploads, image generation, and more, all integrated seamlessly with Firebase Firestore for persistent storage.

Table of Contents
Features
Demo
Installation
Configuration
1. Clone the Repository
2. Install Dependencies
3. Set Up Firebase Firestore
4. Configure st.secrets
5. (Optional) Set Up Password Protection
Running the App
Usage
Selecting AI Models
Managing Conversations
Uploading and Handling Files
Generating Images
Troubleshooting
Contributing
License
Features
Multi-Model Support: Utilize OpenAI's GPT-4, Google's Gemini, and Anthropic's Claude models.
Conversation Management: Save, load, and delete chat conversations using Firebase Firestore.
File Uploads: Upload and handle images, audio, video, PDFs, CSVs, Excel files, and plain text.
Image Generation: Generate images using OpenAI's DALL·E model directly from the chat interface.
Secure Storage: Conversations are securely stored in Firebase Firestore.
Optional Password Protection: Protect access to the app with a password.
User Information Integration: Each user message is prepended with user information for personalized interactions.
Demo
Chat Interface

Screenshot of the ChatGPT Streamlit App interface

Installation
Prerequisites
Python: Ensure you have Python 3.7 or higher installed. You can download it from Python.org.
pip: Python package installer. It usually comes bundled with Python.
1. Clone the Repository
git clone https://github.com/yourusername/chatgpt-streamlit-app.git
cd chatgpt-streamlit-app

2. Install Dependencies
It's recommended to use a virtual environment to manage dependencies.

Using venv:
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

3. Set Up Firebase Firestore
Create a Firebase Project:

Go to the Firebase Console.
Click on "Add project" and follow the prompts to create a new project.
Enable Firestore:

In your Firebase project dashboard, navigate to Firestore Database.
Click on Create database and follow the setup instructions.
Generate Service Account Key:

Navigate to Project Settings > Service Accounts.
Click on Generate new private key and save the JSON file.
Note: You'll need the contents of this JSON file for the next step.

4. Configure st.secrets
Streamlit uses st.secrets to manage sensitive information securely. You need to set up the secrets required by the app.

Create a Secrets File:

Create a file named secrets.toml in the root directory of your project with the following structure:

[OPENAI_API_KEY]
OPENAI_API_KEY = "your-openai-api-key"

[GOOGLE_API_KEY]
GOOGLE_API_KEY = "your-google-api-key"

[ANTHROPIC_API_KEY]
ANTHROPIC_API_KEY = "your-anthropic-api-key"

[textkey]
textkey = """
{
    "type": "service_account",
    "project_id": "your-project-id",
    "private_key_id": "your-private-key-id",
    "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
    "client_email": "your-client-email@your-project.iam.gserviceaccount.com",
    "client_id": "your-client-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-client-email@your-project.iam.gserviceaccount.com"
}
"""

[passw]
# Optional: Uncomment and set your password if you want to enable password protection
# passw = "your-secure-password"

Replace the placeholders (your-openai-api-key, your-google-api-key, etc.) with your actual API keys and Firebase service account details.

Secure Your Secrets:

Ensure that secrets.toml is not committed to version control by adding it to your .gitignore:

# Add to .gitignore
secrets.toml

5. (Optional) Set Up Password Protection
The app includes optional password protection to restrict access.

Enable Password Protection:

In the secrets.toml file, uncomment and set the passw field:

[passw]
passw = "your-secure-password"

Usage:

If password protection is enabled, users will be prompted to enter the password in the sidebar to access the chat functionalities.

Running the App
After completing the installation and configuration steps, you can run the Streamlit app using the following command:

streamlit run app.py

Replace app.py with the filename of your Streamlit application if different.

The app should open in your default web browser. If it doesn't, navigate to the URL provided in the terminal output (usually http://localhost:8501).

Usage
Selecting AI Models
Model Selection:

In the sidebar, use the dropdown menu to select your preferred AI model from the available options:

OpenAI Models:
gpt-4o
o1-preview
o1-mini
Google Gemini Models:
gemini-1.5-flash-latest
gemini-1.5-pro-latest
Anthropic Models:
claude-3-5-sonnet-20240620
Attachment Support:

Depending on the selected model, specific file types can be uploaded as attachments to enhance interactions.

Managing Conversations
Saving Conversations:

Enter a name for your conversation in the "Save conversation" text input field in the sidebar.
Click the Save button to store the current chat history in Firebase Firestore.
Loading Conversations:

Use the Load conversation dropdown in the sidebar to select and load previously saved conversations.
Deleting Conversations:

If a conversation is loaded, click the Delete button in the sidebar to remove it from Firestore.
Clearing Conversations:

Click the Clear button in the sidebar to erase the current chat history from the session.
Uploading and Handling Files
Supported File Types:

Images: png, jpg, jpeg, webp
Documents: xlsx (Excel files), csv, pdf, txt
Audio: audio/*
Video: video/*
Uploading Files:

In the sidebar, use the Attachment uploader to upload files.
The supported file types depend on the selected AI model.
Handling Uploaded Files:

Images: Displayed directly in the chat.
Excel Files: Parsed and displayed as dataframes.
PDFs & Text: Displayed as text content.
Unsupported Types: A warning will be shown.
Generating Images
Image Commands:

To generate an image, start your message with the /image command followed by a description.
Example: /image A sunset over a mountain range with a river flowing through.
Displaying Generated Images:

The generated image will be displayed in the chat along with the description.
Troubleshooting
Missing Dependencies:

Ensure all required Python packages are installed. Run pip install -r requirements.txt to install missing dependencies.

Firebase Authentication Issues:

Verify that the Firebase service account JSON in st.secrets is correct and has the necessary permissions.
Check the project ID and other credentials.
API Key Errors:

Ensure that your API keys for OpenAI, Google, and Anthropic are correct and have the required permissions.
Verify that the keys are correctly set in st.secrets.
File Upload Problems:

Ensure that the uploaded files are of supported types.
Check the file size limits and try uploading smaller files if encountering issues.
Password Protection Not Working:

If enabled, ensure the correct password is entered.
Verify that the passw field in secrets.toml is correctly set.
Streamlit Server Issues:

Restart the Streamlit server using streamlit run app.py.
Check for any error messages in the terminal and address them accordingly.
Contributing
Contributions are welcome! If you'd like to contribute to this project, please follow these steps:

Fork the Repository:

Click the Fork button at the top-right corner of this page.

Clone Your Fork:

git clone https://github.com/yourusername/chatgpt-streamlit-app.git
cd chatgpt-streamlit-app

Create a New Branch:

git checkout -b feature/YourFeatureName

Commit Your Changes:

git commit -m "Add your descriptive commit message here"

Push to Your Fork:

git push origin feature/YourFeatureName

Create a Pull Request:

Navigate to the original repository and create a pull request from your fork.

License
This project is licensed under the MIT License.
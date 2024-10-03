# Multi AI Platform Streamlit App

This application provides a chat interface to consolidate OpenAI, Google, and Anthropic models into one chat service. It includes conversation saving/loading, file uploads, image generation, integrated with Firebase Firestore for persistent storage. Available models will depend on your API access, please check your development account with the various platforms.

## Features

- **Multi-Model Support**: Utilize OpenAI's GPT, Google's Gemini, and Anthropic's Claude models.
- **Conversation Management**: Save, load, and delete chat conversations using Firebase Firestore.
- **File Uploads**: Upload and handle images, audio, video, PDFs, CSVs, Excel files, and plain text.
- **Image Generation**: Generate images using OpenAI's DALL·E model directly from the chat interface.
- **Optional Password Protection**: Protect access to the app with a password.
- **User Information Integration**: Each user message is prepended with user information for personalized interactions.

## Installation

### Prerequisites

- **Python**
- **pip**

### 1. Clone the Repository

```bash
git clone https://github.com/dylnbk/chatty-v2.git
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Firebase Firestore

**Create a Firebase Project:**

- Go to the [Firebase Console](https://console.firebase.google.com/).
- Click on **"Add project"** and follow the prompts to create a new project.

**Enable Firestore:**

- In your Firebase project dashboard, navigate to **Firestore Database**.
- Click on **"Create database"** and follow the setup instructions.

**Generate Service Account Key:**

- Navigate to **Project Settings > Service Accounts**.
- Click on **"Generate new private key"** and save the JSON file.
- **Note:** You'll need the contents of this JSON file for the next step.

### 4. Configure `st.secrets`

Streamlit uses `st.secrets` to manage sensitive information securely. You need to set up the secrets required by the app.

**Create a Secrets File:**

Create a `.streamlit` folder in the root directory of your project, and a file named `secrets.toml` with the following structure:

```toml
[OPENAI_API_KEY]
OPENAI_API_KEY = "your-openai-api-key"

[GOOGLE_API_KEY]
GOOGLE_API_KEY = "your-google-api-key"

[ANTHROPIC_API_KEY]
ANTHROPIC_API_KEY = "your-anthropic-api-key"

[textkey]
# Use key-to-toml.py to convert your JSON to TOML and paste it here

[passw]
# Optional: Uncomment and set your password if you want to enable password protection
# passw = "your-secure-password"
```

**Replace the placeholders** (`your-openai-api-key`, `your-google-api-key`, etc.) with your actual API keys.

**Secure Your Secrets:**

Ensure that `secrets.toml` is not committed to version control by adding it to your `.gitignore`:

```gitignore
# Add to .gitignore
/.streamlit/secrets.toml
```

### 5. Config settings for Streamlit Cloud file uploads

In the `.streamlit` folder, add a file named `config.toml` with the following content:

```toml
[server]
enableXsrfProtection = false
enableCORS = false
```

### 6. (Optional) Set Up Password Protection

Optional password protection to restrict access.

**Enable Password Protection:**

In the `secrets.toml` file, uncomment and set the `passw` field:

```toml
[passw]
passw = "your-secure-password"
```

Uncomment lines 51 <-> 55:

```python
PASS = st.secrets["passw"]
password = st.sidebar.text_input("Password", type="password")

if PASS != password:
    st.stop()
```

## Running the App

After completing the installation and configuration steps, you can run the Streamlit app using the following command:

```bash
streamlit run main.py
```

Replace `main.py` with the filename of your Streamlit application if different.

The app should open in your default web browser. If it doesn't, navigate to the URL provided in the terminal output (usually `http://localhost:8501`).

## Usage

### Selecting AI Models

**Model Selection:**

In the sidebar, use the dropdown menu to select your preferred AI model from the available options:

- **OpenAI Models:**
  - `gpt-4o`
  - `o1-preview`
  - `o1-mini`
- **Google Gemini Models:**
  - `gemini-1.5-flash-latest`
  - `gemini-1.5-pro-latest`
- **Anthropic Models:**
  - `claude-3-5-sonnet-20240620`

**Attachment Support:**

Depending on the selected model, specific file types can be uploaded as attachments to enhance interactions.

- **Google Gemini** can process Video, Audio, Image, Excel, PDF, Text.
- **Anthropic Claude and OpenAI GPT-4o** can process Image and Excel.

### Managing Conversations

**Saving Conversations:**

- Enter a name for your conversation in the **"Save conversation"** text input field in the sidebar.
- Click the **Save** button to store the current chat history in Firebase Firestore.

**Loading Conversations:**

- Use the **Load conversation** dropdown in the sidebar to select and load previously saved conversations.

**Deleting Conversations:**

- If a conversation is loaded, click the **Delete** button in the sidebar to remove it from Firestore.

**Clearing Conversations:**

- Click the **Clear** button in the sidebar to erase the current chat history from the session.

### Generating Images

**Image Commands:**

- To generate an image, start your message with the `/image` command followed by a description.
- **Example:** `/image A sunset over a mountain range with a river flowing through.`

**Displaying Generated Images:**

- The generated image will be displayed in the chat along with the description.

## Publishing to Streamlit Cloud

You can deploy your Streamlit app to Streamlit Cloud for easy sharing and access.

### Steps to Publish:

1. **Create a Streamlit Account:**

   - Go to [Streamlit Cloud](https://streamlit.io/cloud) and sign up for an account if you haven't already.

2. **Connect Your GitHub Repository:**

   - In your Streamlit Cloud dashboard, click on **"New app"**.
   - Connect your GitHub account and authorize Streamlit to access your repositories.
   - Select the `chatty-v2` repository from the list.

3. **Configure the Deployment:**

   - **Repository:** `dylnbk/chatty-v2`
   - **Branch:** `main` (or the branch you want to deploy)
   - **Main file:** `main.py` (or the entry point of your app)

4. **Set Up Secrets:**

   - In the **Advanced settings**, click on **"Edit"** next to **Secrets**.
   - Add your secrets in the provided text area using TOML format, mirroring your `secrets.toml` file:

     ```toml
     [OPENAI_API_KEY]
     OPENAI_API_KEY = "your-openai-api-key"

     [GOOGLE_API_KEY]
     GOOGLE_API_KEY = "your-google-api-key"

     [ANTHROPIC_API_KEY]
     ANTHROPIC_API_KEY = "your-anthropic-api-key"

     [textkey]
     # Paste the converted TOML content of your Firebase service account key here

     [passw]
     # Optional: Set your password if you have enabled password protection
     passw = "your-secure-password"
     ```

     - **Note:** Ensure you include your Firebase credentials under `[textkey]`.

5. **Deploy the App:**

   - Click **"Deploy"** to start the deployment process.
   - Wait for Streamlit to build and launch your app.

6. **Access Your App:**

   - Once deployed, you will receive a URL where your app is hosted - this can be customized.
   - Share this URL to provide access to your app.
   - Settings > Sharing > Who can view this app > Public/Private to determine access.

### Updating the App:

- Any changes pushed to the branch specified during deployment will automatically trigger a redeployment.
- To manually trigger a redeployment, you can also use the **"Deploy"** button in your Streamlit Cloud dashboard.

## License

This project is licensed under the MIT License.
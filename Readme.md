**🌌 Local Chatbot for LM Studio**

**Created by Arun Verma**

**Python Version:** 3.10+ \| **Backend:** LM Studio \| **UI:** CustomTkinter \| **License:** MIT

A sleek, standalone desktop client for running local Large Language Models (LLMs). Designed to connect seamlessly to the LM Studio local server, this application provides a robust, professional-grade interface with live hardware monitoring, document handling, and native support for modern reasoning models.

**✨ Key Features**

- 🎨 **Windows 7 Aero Aesthetic**: Features a clean, highly readable interface with classic \"Aero Light\" and \"Dark Mode\" skeuomorphic themes.

- 📊 **Live Hardware Telemetry**: Real-time percentage tracking for CPU, System RAM, and NVIDIA GPU VRAM utilization directly in the sidebar.

- 🧠 **Deep Reasoning Support**: Native parser for DeepSeek-R1 and similar models. Automatically intercepts \<think\> tags and displays the model\'s internal reasoning trace in a dedicated, collapsible UI block.

- 📎 **Rich Document Handling**:

  - **Import**: Seamlessly read from attached .pdf, .txt, and code files (.py, .json, .csv, etc.), as well as images.

  - **Export**: Save AI responses as beautifully formatted .pdf or raw .txt files with one click.

- 💾 **Persistent Chat History**: Automatically saves your chat sessions locally as .json files, accessible via the sidebar.

- 📦 **Professional Setup Wizard**: Includes PowerShell scripts to automatically compile the Python code into an .exe and wrap it in a standard Windows Setup Installer using Inno Setup.

**🛠️ Prerequisites**

1.  **LM Studio**: Must be installed and running on your network.

2.  **Python 3.10+**: Make sure Python is added to your system PATH.

3.  **Inno Setup 6** *(Optional)*: Only required if you want to build the distributable setup installer.

**🚀 Getting Started**

**1. Setup LM Studio**

1.  Open LM Studio and load your preferred model (e.g., DeepSeek R1, Qwen Coder, or Llama 3).

2.  Go to the **Local Server** tab.

3.  Ensure the server is running on http://localhost:1234/v1.

4.  Click **Start Server**.

**2. Setup the Chatbot**

Clone this repository or download the source code, then install the dependencies in PowerShell: pip install -r requirements.txt

**3. Run the App**

Launch the app using the provided PowerShell script: powershell -ExecutionPolicy Bypass -File .\chatbot.ps1

**📦 Compiling to an Installer**

Want to share the app across different machines without dealing with Python dependencies? You can compile the entire project into a standard Windows Setup Installer.

1.  Ensure **Inno Setup 6** is installed on your machine.

2.  Run the build script in PowerShell: powershell -ExecutionPolicy Bypass -File .\build.ps1

3.  The script will gather dependencies, compile the .exe, and generate the installer.

4.  Once finished, navigate to the newly created dist_installer folder and run LocalChatbot_Setup.exe.

**📂 Project Structure**

- **app.py** - The main CustomTkinter application logic and UI.

- **requirements.txt** - Python dependencies (openai, customtkinter, psutil, pynvml, etc.).

- **chatbot.ps1** - PowerShell quick-launch script that verifies the LM Studio server.

- **build.ps1** - PowerShell automation script to compile via PyInstaller & Inno Setup.

- **chatbot.spec** - Configuration file for PyInstaller executable bundling.

- **setup.iss** - Inno Setup configuration file for generating the installation wizard.

**ℹ️ Project Info**

- **Version:** 1.0

- **Author:** Arun Verma (arun.verma@iitdh.ac.in)

- **Repository:** [github.com/arunniperk/LMStudio_chatbot](https://www.google.com/search?q=https://github.com/arunniperk/LMStudio_chatbot)

**🤝 Dependencies & Acknowledgements**

- UI built with CustomTkinter.

- LLM API connections powered by the openai Python client.

- Telemetry driven by psutil and pynvml.

- PDF operations handled by pypdf and fpdf2.

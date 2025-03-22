# **Loom Automation - Google Drive to Loom Uploader**  

## **Overview**  
This project automates the process of downloading videos from Google Drive and uploading them to Loom. The tool provides a **Graphical User Interface (GUI)** for seamless video management and supports **Windows, macOS, and Linux**.

---

## **1. Prerequisites**  
Before setting up the program, ensure you have the following:

### **A. Install Python**  
You need Python, python **3.11.9** is preferred. 

You can also download it from:  
🔗 [Python 3.11.9 Official Download](https://www.python.org/downloads/release/python-3119/)

#### **Windows:**
Run **python-3.11.9-amd64.exe**, ensuring you check **"Add Python to PATH"** during installation.

#### **macOS:**
- Open **Terminal** (`Cmd + Space`, type "Terminal", and press `Enter`).
- If Python is not installed, install it using Homebrew:
  ```bash
  brew install python
  ```

#### **Linux (Debian-based like Ubuntu)**
- Open a terminal (`Ctrl + Alt + T`) and install Python:
  ```bash
  sudo apt update && sudo apt install python3 python3-pip
  ```

---

## **2. Setting Up Google Drive API & Service Account**  

To allow this program to access your **Google Drive videos**, you need to create a **Service Account** and enable the **Google Drive API**.

### **Step 1: Enable Google Drive API**  
1. Go to the **Google Cloud Console**:  
   🔗 [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one).
3. Navigate to **APIs & Services > Library**.
4. Search for **Google Drive API**, click it, and enable it.

### **Step 2: Create a Service Account**
1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials** > **Service Account**.
3. Fill in details and click **Create**.
4. In the **Service Account details**, click **Manage Keys**.
5. Click **Add Key > Create new key**.
6. Select **JSON** and download the file.
7. Place the downloaded file in the program folder (You will be asked to select it)

⚠ **Important**: This file contains sensitive credentials. Keep it safe and do not share it.

### **Step 3: Share Google Drive Folder with Service Account**
1. Open **Google Drive**.
2. Right-click the folder containing your videos.
3. Click **"Share"**.
4. Copy the **email address** of your Service Account from the JSON file.
5. Paste it into the **Share with people and groups** field.
6. Set permission to **Viewer** or **Editor**.

### **Step 4: Get Google Drive Folder ID**
1. Open the **Google Drive folder**.
2. Copy the **last part** of the URL after `/folders/`:
   ```
   https://drive.google.com/drive/folders/**1ABcD1234xyz56789**
   ```
   The bold part (`1ABcD1234xyz56789`) is your **Folder ID**.

---

## **3. Setting Up the Project**
#### **Windows:**
1. Right click on **build_windows.bat** 
2. Click Run as Administrator

#### **macOS / Linux:**

Double click on **build_mac.command**


#### This file will:

✅ Install required dependencies (including Playwright)  
✅ Generate an executable file (`LoomAutomation`)  

After completion, the **executable** will be in the same folder.

---

## **4. Using the Program**
Run the generated executable (`LoomAutomation.exe` on Windows or `./LoomAutomation` on macOS/Linux).

### **Main Features & Buttons**
| Button | Functionality |
|---------|-------------|
| **Login** | Opens a browser where you manually log in to Loom. Saves login cookies for automation (You only have to do this at least once).|
| **Logout** | Deletes stored login data (cookies) and configuration. |
| **Download** | Downloads videos from your Google Drive folder. |
| **Upload** | Uploads downloaded videos to Loom and stores Title, URL, and Embed Code for each video uploaded. |
| **Download & Upload** | Runs both Download and Upload processes automatically. |
| **Rename Selected** | Allows renaming a selected video before uploading it. |
| **Pause** | Pauses uploading videos. |
| **Generate Embeds** | Generates Embed codes for the videos that don't have embed codes in teh excel sheet. |
| **Sync** | Adds all the videos titles and URLs that are present in teh loom folder but not the excel sheet. |

### **Steps to Upload Videos**
1. Specify Folder ID
2. Select the Google Service Account config file (Json)
3. Specify the workspace URL (Loom Workspace on which you wish the videos to be uploaded)
4. **Login** to Loom (Only if not already logged in from before) **Warning - Login first then click ok on the messagebox**.
5. **Download** videos from Google Drive.
6. Rename selected videos if needed (Optional)
7. **Upload** them to Loom.
8. Or try the Download & Upload option (You will not be able to rename files using this option)
9. The uploaded video details (title, link, embed code) are saved in an Excel file.

---

## **5. Troubleshooting**
### **A. "No module named 'playwright'" Error**
Run:
```bash
python -m pip install -r requirements.txt
```

### **B. "Could not find a version that satisfies the requirement tkinter"**
- **Windows:** Tkinter comes pre-installed with Python.
- **macOS/Linux:** Install it using:
  ```bash
  sudo apt install python3-tk  # Ubuntu/Debian
  brew install python-tk       # macOS (with Homebrew)
  ```

### **C. Loom Login Doesn't Work**
- Make sure your cookies are saved after logging in.
- Try **Logout**, then **Login** again.

---

## **6. Contributing**
Feel free to contribute by:
- Reporting issues
- Suggesting improvements
- Creating pull requests

---

**Enjoy automating your Google Drive to Loom workflow!** 🎥

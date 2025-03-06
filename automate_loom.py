from playwright.sync_api import sync_playwright
import time
import tempfile
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from openpyxl import Workbook, load_workbook
import threading
import queue
import json
from pathlib import Path
import sys
# Add this after TEMPORARY_DOWNLOAD_DIR definition
CONFIG_FILE = "loom_config.json"
LOOM_COOKIES_FILE = "loom_cookies.json"

# Define temporary download directory
TEMPORARY_DOWNLOAD_DIR = 'downloaded_videos'
os.makedirs(TEMPORARY_DOWNLOAD_DIR, exist_ok=True)

if getattr(sys, 'frozen', False):
    # When running as a frozen executable, set the browsers path to the bundled "browsers" folder
    exe_path = os.path.dirname(sys.executable)
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.join(exe_path, 'browsers')

# Add this function to handle config saving/loading
def load_config():
    config = {
        'folder_id': '',
        'service_file': '',
        'space': ''  # Default space name
    }
    try:
        if Path(CONFIG_FILE).exists():
            with open(CONFIG_FILE, 'r') as f:
                config.update(json.load(f))
    except Exception as e:
        print(f"Error loading config: {e}")
    return config

def save_config():
    config = {
        'folder_id': folder_id_entry.get(),
        'service_file': service_file_entry.get(),
        'space': space_entry.get()
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)


def append_to_excel(video_title, video_url, embed_code):
    file_name = "uploaded_videos.xlsx"
    sheet_name = "Videos"
    
    try:
        wb = load_workbook(file_name)
    except FileNotFoundError:
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        ws.append(["Video Title", "URL", "Embed Code"])
    else:
        ws = wb[sheet_name]
    
    ws.append([video_title, video_url, embed_code])
    wb.save(file_name)





def login_and_save_cookies():
    """Launch non-headless browser, user logs in manually, then save cookies."""
    with sync_playwright() as p:
        # We'll use a fresh persistent context in a temp directory, or you can store permanently
        temp_profile_dir = tempfile.mkdtemp()
        print(f"[LOGIN] Using profile at: {temp_profile_dir}")

        context = p.chromium.launch_persistent_context(
            temp_profile_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )

        page = context.new_page()
        page.evaluate("() => { delete window.navigator.webdriver; }")
        page.goto("https://www.loom.com/looms/videos")

        # Wait up to a minute (or indefinite) for user login. 
        # Alternatively, show a messagebox or something to let them know:
        time.sleep(5)
        messagebox.showinfo("Login Required",
            "Please login to Loom in the opened browser.\nClose the browser or press OK here when done."
        )

        # Once the user is presumably logged in, extract cookies:
        cookies = context.cookies()
        print("[LOGIN] Cookies extracted. Saving to file loom_cookies.json.")
        with open(LOOM_COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)

        context.close()
        messagebox.showinfo("Login Complete", "Cookies have been saved. You can close the browser now if it's still open.")


def logout():
    """Delete config and cookies file, then clear GUI entries."""
    confirm = messagebox.askyesno(
        "Confirm Logout",
        "This will delete your saved Loom cookies and config file. Continue?"
    )
    if not confirm:
        return  # User cancelled

    # Delete loom_cookies.json and loom_config.json if they exist
    try:
        if os.path.exists(LOOM_COOKIES_FILE):
            os.remove(LOOM_COOKIES_FILE)
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
    except Exception as e:
        messagebox.showerror("Error", f"Error removing files: {e}")
        return

    # Optionally clear text fields in the GUI
    folder_id_entry.delete(0, tk.END)
    service_file_entry.delete(0, tk.END)
    space_entry.delete(0, tk.END)

    messagebox.showinfo("Logged Out", "Cookies and config file have been removed.")

def start_download_and_upload():
    """Download all videos, then immediately upload them (in one go)."""
    folder_id = folder_id_entry.get().strip()
    service_file = service_file_entry.get().strip()
    if not folder_id or not service_file:
        messagebox.showerror("Error", "Please provide both Folder ID and Service JSON file.")
        return

    # Create a single queue to feed progress to check_progress_queue
    progress_queue = queue.Queue()

    def run_both():
        # Call download_videos logic
        download_videos(folder_id, service_file, progress_queue)

        # Then call upload_videos logic
        upload_videos(progress_queue)

        # Signal "complete"
        progress_queue.put(("complete", None))

    # Run in background so GUI doesn't freeze
    threading.Thread(target=run_both).start()
    # Keep checking progress_queue
    root.after(100, lambda: check_progress_queue(progress_queue))

# Function to fetch video files from Google Drive
# Update the get_gdrive_videos function
def get_gdrive_videos(drive_service, folder_id):
    """Fetch video files from Google Drive folder"""
    # List of common video MIME types
    video_mime_types = [
        'video/',  # This covers all video types generically
        'application/vnd.google-apps.video'  # Google Drive native video format
    ]
    
    # Build the query with explicit MIME type checks
    query = f"""
        '{folder_id}' in parents and (
            mimeType contains 'video/' or
            mimeType = 'application/vnd.google-apps.video'
        )
    """
    
    results = drive_service.files().list(
        q=query.strip(),
        fields="files(id, name, mimeType, fileExtension)",
        pageSize=1000
    ).execute()
    
    # Additional validation for returned files
    valid_files = []
    for file in results.get('files', []):
        # Check if it's a Google Drive native video file
        if file['mimeType'] == 'application/vnd.google-apps.video':
            valid_files.append(file)
            continue
            
        # Check for standard video files
        if (file['mimeType'].startswith('video/') and 
            file.get('fileExtension', '').lower() in {'mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv'}):
            valid_files.append(file)
    
    return valid_files

def download_videos(folder_id, service_file, progress_queue):
    credentials = service_account.Credentials.from_service_account_file(
        service_file,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    drive_service = build('drive', 'v3', credentials=credentials)
    videos = get_gdrive_videos(drive_service, folder_id)
    total_videos = len(videos)
    
    for i, video in enumerate(videos):
        progress_queue.put(("download", f"Downloading: {video['name']}", 0))
        download_video(drive_service, video['id'], video['name'])
        
        # Correct progress calculation
        progress = int(((i + 1) / total_videos) * 100)
        progress_text = f"Downloaded {i+1} of {total_videos}"
        progress_queue.put(("download", progress_text, progress))
    
    progress_queue.put(("populate_listbox", os.listdir(TEMPORARY_DOWNLOAD_DIR)))
    save_config()

# Simplified download function
def download_video(drive_service, file_id, file_name):
    file_path = os.path.join(TEMPORARY_DOWNLOAD_DIR, file_name)
    request = drive_service.files().get_media(fileId=file_id)
    with open(file_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    return file_path


# Function to upload videos
def upload_videos(progress_queue):
    save_config()
    """Check if loom_cookies.json is found. If not, warn user. Otherwise proceed with headless upload."""
    files_to_upload = os.listdir(TEMPORARY_DOWNLOAD_DIR)
    if not files_to_upload:
        progress_queue.put(("complete", None))
        return
    
    # If no cookies, we can't proceed with auto login
    if not os.path.exists(LOOM_COOKIES_FILE):
        messagebox.showerror("Error", "No loom_cookies.json found. Please log in first.")
        progress_queue.put(("complete", None))
        return

    # Load cookies from file
    try:
        with open(LOOM_COOKIES_FILE, "r") as f:
            stored_cookies = json.load(f)
    except Exception as e:
        messagebox.showerror("Error", f"Could not load cookies file: {e}")
        progress_queue.put(("complete", None))
        return

    with sync_playwright() as p:
        temp_profile_dir = tempfile.mkdtemp()
        print(f"Using temporary profile at: {temp_profile_dir}")
        # HEADLESS (or not)
        context = p.chromium.launch_persistent_context(
            temp_profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 720},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1280,720",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )

        # Add cookies before creating the page
        context.add_cookies(stored_cookies)
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://www.loom.com")

        page = context.new_page()
        page.evaluate("() => { delete window.navigator.webdriver; }")

        for i, filename in enumerate(files_to_upload):
            file_path = os.path.join(TEMPORARY_DOWNLOAD_DIR, filename)
            progress_queue.put(("upload", f"Uploading video {i+1} of {len(files_to_upload)}: {filename}", 0))
            space_url = space_entry.get().strip()  # Get space name from GUI input

            page.goto(space_url)
            time.sleep(5)

            # Click "New video"
            add_video_button = page.wait_for_selector('button:has-text("Add video")', timeout=30000)
            add_video_button.click(force=True)
            time.sleep(1)

            # Select "Upload a video" option using the full text match
            upload_option = page.wait_for_selector('li[role="option"]:has-text("Upload a video")', timeout=30000)
            upload_option.click(force=True)
            time.sleep(1)
            # Upload video
            with page.expect_file_chooser() as fc_info:
                page.keyboard.press(" ")
            file_chooser = fc_info.value
            file_chooser.set_files(file_path)
            # Wait for upload UI and start upload
            page.wait_for_selector("text=Upload 1 file", timeout=60000)
            upload_button = page.wait_for_selector("button.uppy-StatusBar-actionBtn--upload", timeout=60000)
            upload_button.click(force=True)
            # Track upload progress
            previous_percentage = 0
            while True:
                try:
                    status_element = page.wait_for_selector(".uppy-StatusBar-statusPrimary", timeout=30000)
                    status_text = status_element.inner_text().strip()
                    if "Uploading: " in status_text:
                        current_percentage = int(status_text.split(": ")[1].replace("%", ""))
                        if current_percentage != previous_percentage:
                            previous_percentage = current_percentage
                            progress_queue.put(("upload", f"Uploading video {i+1} of {len(files_to_upload)}: {filename}", current_percentage))
                    elif "Complete" in status_text:
                        progress_queue.put(("upload", f"Uploading video {i+1} of {len(files_to_upload)}: {filename}", 100))
                        break
                    time.sleep(1)
                except Exception as e:
                    print(f"Error tracking progress: {e}")
                    break
            # Wait for video processing
            page.wait_for_selector(".uppy-Dashboard-Item.is-complete", timeout=120000)
            # Get video link
            video_link_element = page.wait_for_selector(
                ".uppy-Dashboard-Item.is-complete .uppy-Dashboard-Item-previewLink",
                timeout=30000
            )
            video_url = video_link_element.get_attribute("href")
            page.goto(video_url)
            time.sleep(3)  # Let the new video appear in the list
            # Example: find the first visible "Share" button
            share_button = page.wait_for_selector('button[data-testid="share-modal-button"]', timeout=30000)
            share_button.click()
            time.sleep(2)
            dialog = page.locator("dialog.css-1gw7q29[role='dialog']")

            dialog.hover()
            dialog.locator("button.menu_shareTab_3H-", has_text="Embed").hover()
            dialog.locator("button.menu_shareTab_3H-", has_text="Embed").click()

            # 3) Wait for the thumbnail to appear under the "Embed" section
            thumbnail = page.wait_for_selector('img[alt="Video thumbnail"]', timeout=15000)
            thumbnail_src = thumbnail.get_attribute('src')
            print("Thumbnail src:", thumbnail_src)

            # -------------------------
            # OPTION A: Use Loom’s “Copy embed code” button (if available) 
            #           and read from clipboard
            # -------------------------
            copy_embed_btn = page.wait_for_selector('button.css-ask8uh:has-text("Copy embed code")', timeout=5000)
            copy_embed_btn.click()

            # read from the clipboard:
            embed_code = page.evaluate("navigator.clipboard.readText()")
            print("Embed Code from button:\n", embed_code)

            # Append to Excel and update GUI
            append_to_excel(filename, video_url, embed_code)
            progress_queue.put(("add_video", filename, video_url, "Added to the Excel sheet"))

            # Clean up
            os.remove(file_path)
        progress_queue.put(("complete", None))


# Browse button for service file
def browse_file():
    file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if file_path:
        service_file_entry.delete(0, tk.END)
        service_file_entry.insert(0, file_path)


# <--- NEW CODE: A "Login" button
def start_login():
    """Spawn a new thread so GUI doesn't freeze while user logs in."""
    def run_login():
        login_and_save_cookies()
    t = threading.Thread(target=run_login)
    t.start()
# Download Videos button
def start_download():
    folder_id = folder_id_entry.get().strip()
    service_file = service_file_entry.get().strip()
    if not folder_id or not service_file:
        messagebox.showerror("Error", "Please provide both Folder ID and Service JSON file.")
        return
    progress_queue = queue.Queue()
    download_thread = threading.Thread(target=download_videos, args=(folder_id, service_file, progress_queue))
    download_thread.start()
    root.after(100, lambda: check_progress_queue(progress_queue))

# Rename Selected button
def rename_selected():
    selection = upload_listbox.curselection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a video to rename.")
        return
    index = selection[0]
    old_name = upload_listbox.get(index)
    old_base, old_ext = os.path.splitext(old_name)
    
    # Fixed dialog without width parameter
    new_base = simpledialog.askstring(
        "Rename Video", 
        f"Enter new name (extension {old_ext} will be kept):\n",
        initialvalue=old_base,
        parent=root
    )
    
    if new_base and new_base != old_base:
        new_name = f"{new_base}{old_ext}"
        old_path = os.path.join(TEMPORARY_DOWNLOAD_DIR, old_name)
        new_path = os.path.join(TEMPORARY_DOWNLOAD_DIR, new_name)
        try:
            os.rename(old_path, new_path)
            upload_listbox.delete(index)
            upload_listbox.insert(index, new_name)
        except Exception as e:
            messagebox.showerror("Rename Error", f"Failed to rename file: {e}")

# Upload Videos button
def start_upload():
    if not os.listdir(TEMPORARY_DOWNLOAD_DIR):
        messagebox.showwarning("No Videos", "No videos to upload. Please download videos first.")
        return
    progress_queue = queue.Queue()
    upload_thread = threading.Thread(target=upload_videos, args=(progress_queue,))
    upload_thread.start()
    root.after(100, lambda: check_progress_queue(progress_queue))

# Update the check_progress_queue function
def check_progress_queue(progress_queue):
    try:
        while True:
            item = progress_queue.get_nowait()
            
            if item[0] == "complete":
                messagebox.showinfo("Complete", "Operation finished")
                progress_bar['value'] = 0
                
            elif item[0] == "populate_listbox":
                upload_listbox.delete(0, tk.END)
                for filename in item[1]:
                    upload_listbox.insert(tk.END, filename)
                progress_label.config(text="Download complete")
                
            elif item[0] == "add_video":
                # item = ("add_video", filename, video_url, "Added to the Excel sheet")
                tree.insert("", "end", values=(item[1], item[2], item[3]))


                
            elif item[0] in ("download", "upload"):
                _, text, value = item
                progress_label.config(text=text)
                progress_bar['value'] = value
                
            root.update_idletasks()
            
    except queue.Empty:
        pass
    root.after(100, lambda: check_progress_queue(progress_queue))



# GUI Setup
root = tk.Tk()
root.title("Loom Video Uploader")
root.geometry("620x600")
root.configure(bg='#f0f0f0')  # Main background color
root.resizable(False, False)
# Configure styles with unified background
style = ttk.Style()
style.theme_use('clam')

# Configure all elements to use the same background
style.configure(".", background='#f0f0f0', foreground='black')
style.configure("TButton", background='#e1e1e1')
style.configure("Horizontal.TProgressbar", background="green", troughcolor='#d0d0d0')
style.configure("Treeview", background='white', fieldbackground='white')
style.map("Treeview", background=[('selected', '#347083')])

# Frame styling
style.configure("TFrame", background='#f0f0f0')

# Folder ID input frame
input_frame = ttk.Frame(root, padding=10)
input_frame.pack(pady=5, fill='x')

# Load existing config
config = load_config()

# Folder ID
folder_id_label = ttk.Label(input_frame, text="Google Drive Folder ID:")
folder_id_label.grid(row=0, column=0, padx=5, sticky='w')
folder_id_entry = ttk.Entry(input_frame, width=50)
folder_id_entry.insert(0, config['folder_id'])
folder_id_entry.grid(row=0, column=1, padx=5, sticky='ew')

# Service File
service_file_label = ttk.Label(input_frame, text="Service Account JSON File:")
service_file_label.grid(row=1, column=0, padx=5, sticky='w')
service_file_entry = ttk.Entry(input_frame, width=50)
service_file_entry.insert(0, config['service_file'])
service_file_entry.grid(row=1, column=1, padx=5, sticky='ew')

# Space
space_label = ttk.Label(input_frame, text="Space URL:")
space_label.grid(row=2, column=0, padx=5, sticky='w')
space_entry = ttk.Entry(input_frame, width=50)
space_entry.insert(0, config['space'])
space_entry.grid(row=2, column=1, padx=5, sticky='ew')

# Browse button remains the same
browse_button = ttk.Button(input_frame, text="Browse", command=browse_file)
browse_button.grid(row=1, column=2, padx=5)

# Modify the upload_videos function
# Replace the space_selector line with:
space_name = space_entry.get()
space_selector = f'span.navigation_linkTitle_253:has-text("{space_name}")'

# Add save on exit
root.protocol("WM_DELETE_WINDOW", lambda: [save_config(), root.destroy()])

# Button container
button_frame = ttk.Frame(root, padding=10)
button_frame.pack(pady=5, fill='x')

# <--- HERE: add the new "Login" button
login_button = ttk.Button(button_frame, text="Login", command=start_login)
login_button.pack(side='left', padx=5)
# Add the new logout button
logout_button = ttk.Button(button_frame, text="Logout", command=logout)
logout_button.pack(side='left', padx=5)
download_button = ttk.Button(button_frame, text="Download", command=start_download)
download_button.pack(side='left', padx=5)
download_upload_button = ttk.Button(button_frame, text="Download & Upload", command=start_download_and_upload)
download_upload_button.pack(side='left', padx=5)
upload_buttons_frame = ttk.Frame(button_frame)
upload_buttons_frame.pack(side='right', padx=5)

rename_button = ttk.Button(upload_buttons_frame, text="Rename Selected", command=rename_selected)
rename_button.pack(side='left', padx=5)

upload_button = ttk.Button(upload_buttons_frame, text="Upload", command=start_upload)
upload_button.pack(side='left', padx=5)

# Upload list frame
list_frame = ttk.Frame(root, padding=10)
list_frame.pack(pady=5, fill='both', expand=True)

upload_label = ttk.Label(list_frame, text="Videos to Upload")
upload_label.pack(anchor='w')

upload_listbox = tk.Listbox(list_frame, selectmode="single", bg='white')
upload_listbox.pack(fill='both', expand=True)

# Progress indicators
progress_frame = ttk.Frame(root, padding=10)
progress_frame.pack(pady=5, fill='x')

progress_label = ttk.Label(progress_frame, text="")
progress_label.pack(anchor='w')

progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=300, mode="determinate")
progress_bar.pack(fill='x')

# Uploaded videos list
uploaded_frame = ttk.Frame(root, padding=10)
uploaded_frame.pack(pady=5, fill='both', expand=True)

uploaded_videos_label = ttk.Label(uploaded_frame, text="Uploaded Videos")
uploaded_videos_label.pack(anchor='w')

tree = ttk.Treeview(uploaded_frame, columns=("Title", "URL", "Embed Code"), show="headings", selectmode="none")
tree.heading("Title", text="Video Title")
tree.heading("URL", text="URL")
tree.heading("Embed Code", text="Embed Code")
tree.column("Title", width=150)
tree.column("URL", width=250)
tree.column("Embed Code", width=200)
tree.pack(fill='both', expand=True)

# Run the GUI
root.mainloop()
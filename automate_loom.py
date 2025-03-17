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
import shutil



PAUSE_FLAG = False

# Configuration constants
CONFIG_FILE = "loom_config.json"
LOOM_COOKIES_FILE = "loom_cookies.json"
TEMPORARY_DOWNLOAD_DIR = 'downloaded_videos'
os.makedirs(TEMPORARY_DOWNLOAD_DIR, exist_ok=True)

# Set browser path for frozen executable
if getattr(sys, 'frozen', False):
    exe_path = os.path.dirname(sys.executable)
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.join(exe_path, 'browsers')

# Helper functions
def load_config():
    config = {'folder_id': '', 'service_file': '', 'space': ''}
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

def update_excel_embed_code(video_url, new_embed_code):
    file_name = "uploaded_videos.xlsx"
    try:
        wb = load_workbook(file_name)
        ws = wb["Videos"]
        for row in ws.iter_rows(min_row=2):
            if row[1].value == video_url:
                row[2].value = new_embed_code
        wb.save(file_name)
        return True
    except Exception as e:
        print(f"Error updating Excel: {e}")
        return False



def login_and_save_cookies():
    """Launch non-headless browser, user logs in manually, then save cookies."""
    with sync_playwright() as p:
        # We'll use a fresh persistent context in a temp directory, or you can store permanently
        temp_profile_dir = tempfile.mkdtemp()
        print(f"[LOGIN] Using profile at: {temp_profile_dir}")
        progress_queue = queue.Queue()
        progress_queue.put(("logging in.." , None))
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
        time.sleep(10)
        messagebox.showinfo("Login Required",
            "Please login to Loom in the opened browser.\npress OK here when done."
        )

        # Once the user is presumably logged in, extract cookies:
        cookies = context.cookies()
        print("[LOGIN] Cookies extracted. Saving to file loom_cookies.json.")
        with open(LOOM_COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)

        context.close()
        progress_queue.put(("Status: Logged in" , None))
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




# Video processing functions
def extract_embed_code(page, progress_queue, title):
    try:
        page.wait_for_selector('button[data-testid="share-modal-button"]', timeout=60000).click()
        time.sleep(5)
        dialog = page.locator("dialog.css-1gw7q29[role='dialog']")
        dialog.locator("button.menu_shareTab_3H-", has_text="Embed").click()
        
        try:
            page.wait_for_selector('img[alt="Video thumbnail"]', timeout=90000)
        except:
            dialog = page.locator("dialog.css-1gw7q29[role='dialog']")
            dialog.locator("button.menu_shareTab_3H-", has_text="Embed").click()
        copy_btn = page.wait_for_selector('button.css-ask8uh:has-text("Copy embed code")', timeout=60000)
        copy_btn.click()
        embed_code = page.evaluate("navigator.clipboard.readText()")
        progress_queue.put(("embed_success", title, page.url, embed_code))
        return embed_code
    except Exception as e:
        progress_queue.put(("embed_error", page.url, str(e)))
        return None
    


def process_video_url(url, progress_queue, title):
    if not os.path.exists(LOOM_COOKIES_FILE):
        return None

    with open(LOOM_COOKIES_FILE, "r") as f:
        stored_cookies = json.load(f)
        
    with sync_playwright() as p:
        temp_profile_dir = tempfile.mkdtemp()
        context = p.chromium.launch_persistent_context(
            temp_profile_dir,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            ]
        )
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://www.loom.com")
        context.add_cookies(stored_cookies)

        page = context.new_page()
        try:
            page.goto(url)
            # Possibly track how long it's taking...
            # You can add your own "stuck" logic similarly.

            time.sleep(5)
            embed_code = extract_embed_code(page, progress_queue, title)
            return embed_code
        except Exception as e:
            progress_queue.put(("embed_error", url, str(e)))
            return None
        finally:
            context.close()
            shutil.rmtree(temp_profile_dir, ignore_errors=True)


def generate_embed_codes(progress_queue):
    max_retries = 3  # how many times to retry extracting an embed code

    try:
        wb = load_workbook("uploaded_videos.xlsx")
        ws = wb["Videos"]

        # 1) Identify which rows need embed codes, and collect Title & URL
        rows_to_process = []
        for row in ws.iter_rows(min_row=2):
            # row[0] = Title, row[1] = URL, row[2] = Embed Code
            title = row[0].value or ""
            url   = row[1].value or ""
            code  = row[2].value or ""
            if not code or "Couldn't Extract" in code:
                # We want to try extracting a code for these
                rows_to_process.append((title, url))

        # If none need extraction, we can simply signal done:
        if not rows_to_process:
            progress_queue.put(("complete", "All embed codes already present"))
            return

        # 2) Let GUI know how many we'll process
        progress_queue.put(("total_embeds", len(rows_to_process)))

        # 3) For each row needing code, do the extraction
        for i, (title, url) in enumerate(rows_to_process, start=1):
            progress_queue.put(("current_embed", i, url))

            attempts_left = max_retries
            embed_code = None

            while attempts_left > 0:
                try:
                    embed_code = process_video_url(url, progress_queue, title)
                    if embed_code:
                        # Success
                        break
                except Exception as e:
                    print(f"Embed extraction error for {url}: {e}")
                attempts_left -= 1
                if attempts_left > 0:
                    print(f"Retrying embed extraction for {url}...")

            # 4) Update Excel with final result: success or fail
            if embed_code:
                update_excel_embed_code(url, embed_code)
            else:
                embed_code = "Couldn't Extract - Retry Failed"
                update_excel_embed_code(url, embed_code)



    except Exception as e:
        progress_queue.put(("embed_error", "General Error", str(e)))
    finally:
        # 6) Signal done
        progress_queue.put(("complete", "Embed code generation completed"))



# GUI functions
def start_generate_embeds():
    if not os.path.exists("uploaded_videos.xlsx"):
        messagebox.showerror("Error", "No Excel file found")
        return
        
    # Create our progress queue for communication
    progress_queue = queue.Queue()

    # 1) Clear the TreeView right away
    progress_queue.put(("clear_tree", None))

    # 2) Launch thread to do the embed extraction
    threading.Thread(target=generate_embed_codes, args=(progress_queue,)).start()

    # 3) Keep checking queue
    root.after(100, lambda: check_progress_queue(progress_queue))


def pause_upload():
    global PAUSE_FLAG
    PAUSE_FLAG = True
    messagebox.showinfo("Paused", "Upload process will paused now")

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

def download_video(drive_service, file_id, file_name, on_progress=None):
    """Download a video with progress reporting."""
    file_path = os.path.join(TEMPORARY_DOWNLOAD_DIR, file_name)
    request = drive_service.files().get_media(fileId=file_id)
    with open(file_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status and on_progress:
                # Report progress percentage for this file
                percent = int(status.progress() * 100)
                on_progress(percent)
    return file_path

def pause_upload():
    global PAUSE_FLAG
    PAUSE_FLAG = True
    messagebox.showinfo("Paused", "Upload process will pause now")


def download_videos(folder_id, service_file, progress_queue):
    """Download each video with its own progress bar reset per video."""
    credentials = service_account.Credentials.from_service_account_file(
        service_file,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    drive_service = build('drive', 'v3', credentials=credentials)
    videos = get_gdrive_videos(drive_service, folder_id)
    
    total_videos = len(videos)

    for i, video in enumerate(videos):
        # Notify start of new video download
        progress_queue.put(("download", f"Starting download: {video['name']}", 0))

        def progress_callback(percent):
            """Update UI with per-video progress."""
            progress_queue.put(("download", f"Downloading: {video['name']} ({percent}%)", percent))

        # Download with progress tracking
        download_video(drive_service, video['id'], video['name'], progress_callback)

        # Notify completion of the video download
        progress_queue.put(("download", f"Downloaded: {video['name']} ✔", 100))
        time.sleep(1)  # Small delay for visual clarity
        progress_queue.put(("download", f"", 0))  # Reset progress bar for next video

    # Update UI with downloaded files
    progress_queue.put(("populate_listbox", os.listdir(TEMPORARY_DOWNLOAD_DIR))) 
    save_config()


def upload_videos(progress_queue):
    global PAUSE_FLAG
    PAUSE_FLAG = False  # reset each time

    # --- You can tune these values as you like ---
    max_retries = 3             # How many times to retry a file if stuck
    upload_timeout_seconds = 180  # If no progress for this many seconds, consider it stuck
    time_between_checks = 5       # How often to check progress (seconds)

    save_config()
    files_to_upload = os.listdir(TEMPORARY_DOWNLOAD_DIR)
    progress_queue.put(("populate_listbox", files_to_upload))

    if not files_to_upload:
        progress_queue.put(("complete", None))
        return
    
    if not os.path.exists(LOOM_COOKIES_FILE):
        messagebox.showerror("Error", "No loom_cookies.json found. Please log in first.")
        progress_queue.put(("Not logged in", None))
        return

    progress_queue.put(("Logging in..", None))
    try:
        with open(LOOM_COOKIES_FILE, "r") as f:
            stored_cookies = json.load(f)
    except Exception as e:
        messagebox.showerror("Error", f"Could not load cookies file: {e}")
        progress_queue.put(("Could not log in", None))
        return

    with sync_playwright() as p:
        # We'll iterate over the files by index so we can remove or retry them
        i = 0
        while i < len(files_to_upload):
            filename = files_to_upload[i]

            if PAUSE_FLAG:
                # user pressed "Pause"
                progress_queue.put(("pausing", None))
                break

            file_path = os.path.join(TEMPORARY_DOWNLOAD_DIR, filename)
            if not os.path.isfile(file_path):
                # If file was missing or already removed, skip it
                i += 1
                continue

            # Optional: get local file size (for approximate MB/s)
            file_size = os.path.getsize(file_path)

            attempts_left = max_retries
            success = False

            while attempts_left > 0 and not success:
                temp_profile_dir = tempfile.mkdtemp()
                try:
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
                            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                        ]
                    )
                    context.add_cookies(stored_cookies)
                    context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://www.loom.com")

                    page = context.new_page()
                    page.evaluate("() => { delete window.navigator.webdriver; }")

                    # Notify UI
                    progress_queue.put(("upload", f"Opening Loom workspace for {filename}...", 0))

                    space_url = space_entry.get().strip()
                    page.goto(space_url)
                    time.sleep(8)

                    add_video_button = page.wait_for_selector('button:has-text("Add video")', timeout=60000)
                    add_video_button.click(force=True)
                    time.sleep(3)
                    progress_queue.put(("upload", "Initiating upload...", 0))

                    upload_option = page.wait_for_selector('li[role="option"]:has-text("Upload a video")', timeout=60000)
                    upload_option.click(force=True)
                    time.sleep(3)

                    # File chooser
                    with page.expect_file_chooser() as fc_info:
                        page.keyboard.press(" ")
                    file_chooser = fc_info.value
                    file_chooser.set_files(file_path)

                    page.wait_for_selector("text=Upload 1 file", timeout=60000)
                    upload_button = page.wait_for_selector("button.uppy-StatusBar-actionBtn--upload", timeout=60000)
                    upload_button.click(force=True)

                    previous_percentage = 0
                    previous_time = time.time()  # for speed calc
                    last_progress_update = time.time()

                    # -- Track upload progress with a loop + timeout check --
                    while True:
                        if PAUSE_FLAG:
                            # user pressed pause mid-upload
                            context.close()
                            shutil.rmtree(temp_profile_dir, ignore_errors=True)
                            progress_queue.put(("pausing", None))
                            return

                        status_element = page.wait_for_selector(".uppy-StatusBar-statusPrimary", timeout=60000)
                        status_text = status_element.inner_text().strip()

                        if "Uploading: " in status_text:
                            # "Uploading: 97%"
                            current_percentage = int(status_text.split(": ")[1].replace("%", ""))

                            if current_percentage != previous_percentage:
                                # Update "last progress" time
                                now = time.time()
                                stuck_duration = now - last_progress_update
                                last_progress_update = now

                                # --- Approx upload speed calc (MB/s) ---
                                delta_percent = current_percentage - previous_percentage
                                bytes_uploaded_now = (delta_percent / 100.0) * file_size
                                delta_time = now - previous_time
                                # Avoid divide-by-zero
                                if delta_time < 0.1:
                                    delta_time = 0.1
                                speed_mbs = (bytes_uploaded_now / 1_000_000) / delta_time

                                previous_percentage = current_percentage
                                previous_time = now

                                # Send progress to UI
                                progress_queue.put((
                                    "upload",
                                    f"Uploading {filename}: {current_percentage}% "
                                    f"({speed_mbs:.2f} MB/s)",
                                    current_percentage
                                ))

                            # Check if stuck too long
                            if (time.time() - last_progress_update) > upload_timeout_seconds:
                                raise TimeoutError(f"Stuck uploading {filename} for too long.")

                        elif "Complete" in status_text:
                            progress_queue.put(("upload", f"{filename}: 100% Complete", 100))
                            break

                        time.sleep(time_between_checks)

                    # If we get here, presumably the upload completed
                    progress_queue.put(("upload", "Finished uploading. Extracting URL..", 0))

                    # Wait for processing
                    page.wait_for_selector(".uppy-Dashboard-Item.is-complete", timeout=120000)
                    video_link_element = page.wait_for_selector(
                        ".uppy-Dashboard-Item.is-complete .uppy-Dashboard-Item-previewLink",
                        timeout=30000
                    )
                    video_url = video_link_element.get_attribute("href")

                    append_to_excel(filename, video_url, "")
                    progress_queue.put(("add_video", filename, video_url, ""))

                    # Remove file from disk
                    os.remove(file_path)
                    progress_queue.put(("remove_file", filename))

                    context.close()
                    shutil.rmtree(temp_profile_dir, ignore_errors=True)

                    success = True  # break from retry loop

                except TimeoutError as toe:
                    # If we timed out, let's close and retry
                    context.close()
                    shutil.rmtree(temp_profile_dir, ignore_errors=True)
                    attempts_left -= 1
                    print(f"TimeoutError for {filename}: {toe}. Retrying...")

                    if attempts_left == 0:
                        # Give up
                        messagebox.showerror(
                            "Upload Stuck", 
                            f"{filename} got stuck too many times. Skipping this file."
                        )
                        # Optionally log in Excel as "Failed"
                        append_to_excel(filename, "Upload Stuck", "Could not complete upload")
                        progress_queue.put(("remove_file", filename))
                        if os.path.exists(file_path):
                            os.remove(file_path)
                
                except Exception as e:
                    # Some other error
                    print(f"Error uploading {filename}: {e}")
                    context.close()
                    shutil.rmtree(temp_profile_dir, ignore_errors=True)
                    # We can choose to break or retry. Let's break:
                    attempts_left = 0  
                    append_to_excel(filename, "Unknown", f"Upload error: {e}")
                    progress_queue.put(("remove_file", filename))
                    if os.path.exists(file_path):
                        os.remove(file_path)

            i += 1  # move to next file

        # Finished all files
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

def check_progress_queue(progress_queue):
    try:
        while True:
            item = progress_queue.get_nowait()
            if item[0] == "populate_listbox":
                upload_listbox.delete(0, tk.END)
                for fname in item[1]:
                    upload_listbox.insert(tk.END, fname)

            elif item[0] == "add_video":
                tree.insert("", "end", values=(item[1], item[2], item[3]))

            elif item[0] in ("download", "upload"):
                _, text, value = item
                progress_label.config(text=f"{text} ({value}%)")
                progress_bar['value'] = value

            elif item[0] == "remove_file":
                # Remove the file from the listbox
                filename = item[1]
                all_items = upload_listbox.get(0, tk.END)
                if filename in all_items:
                    idx = all_items.index(filename)
                    upload_listbox.delete(idx)

            elif item[0] == "complete":
                # If there's a message, show it; otherwise use default
                msg = item[1] if item[1] else "Operation Complete"
                messagebox.showinfo("Complete", msg)
                progress_bar['value'] = 0
                progress_label.config(text="Operation Complete")

            elif item[0] == "total_embeds":
                progress_bar['maximum'] = item[1]

            elif item[0] == "current_embed":
                progress_label.config(text=f"Processing {item[1]}/{progress_bar['maximum']}: {item[2]}")
                progress_bar['value'] = item[1]
            elif item[0] == "clear_tree":
                # remove all rows from the "Uploaded Videos" tree
                for row_id in tree.get_children():
                    tree.delete(row_id)

            elif item[0] == "embed_success":
                title = item[1]
                url   = item[2]
                code  = item[3]
                tree.insert("", "end", values=(title, url, code))


            elif item[0] == "embed_error":
                messagebox.showerror("Error", f"Failed to process {item[1]}: {item[2]}")

            elif item[0] == "pausing":
                progress_label.config(text="Upload paused")
                progress_bar['value'] = 0
                messagebox.showinfo("Paused", "Upload has been paused.")
                
            root.update_idletasks()
    except queue.Empty:
        pass
    root.after(100, lambda: check_progress_queue(progress_queue))




root = tk.Tk()
root.title("Loom Video Uploader")
root.geometry("850x650")  # Wider window
root.configure(bg='#f0f0f0')
root.resizable(False, False)

# Style configuration
style = ttk.Style()
style.theme_use('clam')
style.configure(".", background='#f0f0f0', foreground='black')
style.configure("TButton", background='#e1e1e1')
style.configure("Horizontal.TProgressbar", background="green", troughcolor='#d0d0d0')
style.configure("Treeview", background='white', fieldbackground='white')
style.map("Treeview", background=[('selected', '#347083')])

# Frames
input_frame = ttk.Frame(root, padding=10)
input_frame.pack(pady=5, fill='x')

# Load config
config = load_config()

# Input fields
ttk.Label(input_frame, text="Google Drive Folder ID:").grid(row=0, column=0, padx=5, sticky='w')
folder_id_entry = ttk.Entry(input_frame, width=60)
folder_id_entry.insert(0, config['folder_id'])
folder_id_entry.grid(row=0, column=1, padx=5, sticky='ew')

ttk.Label(input_frame, text="Service Account JSON File:").grid(row=1, column=0, padx=5, sticky='w')
service_file_entry = ttk.Entry(input_frame, width=60)
service_file_entry.insert(0, config['service_file'])
service_file_entry.grid(row=1, column=1, padx=5, sticky='ew')

ttk.Label(input_frame, text="Space URL:").grid(row=2, column=0, padx=5, sticky='w')
space_entry = ttk.Entry(input_frame, width=90)
space_entry.insert(0, config['space'])
space_entry.grid(row=2, column=1, padx=5, sticky='ew')

browse_button = ttk.Button(input_frame, text="Browse", command=browse_file)
browse_button.grid(row=1, column=2, padx=5)

# Existing buttons
button_frame = ttk.Frame(root)
button_frame.pack(pady=5)

login_button = ttk.Button(button_frame, text="Login", command=start_login)
logout_button = ttk.Button(button_frame, text="Logout", command=logout)
download_button = ttk.Button(button_frame, text="Download", command=start_download)
download_upload_button = ttk.Button(button_frame, text="Download & Upload", command=start_download_and_upload)
rename_button = ttk.Button(button_frame, text="Rename", command=rename_selected)
upload_button = ttk.Button(button_frame, text="Upload", command=start_upload)
pause_button = ttk.Button(button_frame, text="Pause", command=pause_upload)
generate_button = ttk.Button(button_frame, text="Generate Embeds", command=start_generate_embeds)

buttons = [login_button, logout_button, download_button, download_upload_button, rename_button, upload_button, pause_button, generate_button]
for btn in buttons:
    btn.pack(side='left', padx=5)

# List and progress elements remain the same
list_frame = ttk.Frame(root, padding=10)
list_frame.pack(pady=5, fill='both', expand=True)

upload_label = ttk.Label(list_frame, text="Videos to Upload")
upload_label.pack(anchor='w')

list_container = ttk.Frame(list_frame)
list_container.pack(fill='both', expand=True)

scrollbar = ttk.Scrollbar(list_container)
upload_listbox = tk.Listbox(list_container, selectmode="single", bg='white', yscrollcommand=scrollbar.set)
scrollbar.config(command=upload_listbox.yview)
upload_listbox.pack(side='left', fill='both', expand=True)
scrollbar.pack(side='right', fill='y')

# Progress elements
progress_frame = ttk.Frame(root, padding=10)
progress_frame.pack(pady=5, fill='x')

progress_label = ttk.Label(progress_frame, text="")
progress_label.pack(anchor='w')

progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=300, mode="determinate")
progress_bar.pack(fill='x')

# Uploaded videos treeview
uploaded_frame = ttk.Frame(root, padding=10)
uploaded_frame.pack(pady=5, fill='both', expand=True)

ttk.Label(uploaded_frame, text="Uploaded Videos").pack(anchor='w')

tree_container = ttk.Frame(uploaded_frame)
tree_container.pack(fill='both', expand=True)

tree_scroll = ttk.Scrollbar(tree_container)
tree = ttk.Treeview(tree_container, columns=("Title", "URL", "Embed Code"), show="headings", yscrollcommand=tree_scroll.set)
tree.heading("Title", text="Video Title")
tree.heading("URL", text="URL")
tree.heading("Embed Code", text="Embed Code")
tree.column("Title", width=200)
tree.column("URL", width=300)
tree.column("Embed Code", width=250)
tree.pack(side='left', fill='both', expand=True)
tree_scroll.pack(side='right', fill='y')

root.protocol("WM_DELETE_WINDOW", lambda: [save_config(), root.destroy()])
root.mainloop()
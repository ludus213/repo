import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from playwright.sync_api import sync_playwright
import threading
import time
import json # For potentially storing/loading cookies if needed, though not primary for this step

# --- Global Variables for Playwright context and page ---
# This allows us to keep the browser open and reuse the page if needed,
# or to properly close it when the app exits.
# playwright_context = None # No longer primary global, managed by browser instance
# playwright_page = None # No longer primary global, managed by self.playwright_page
roblox_cookie = None # Still used by some functions, consider refactoring
user_id = None # Will be fetched after login, global for now
csrf_token = None # Will be fetched after login, global for now

class RobloxUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Roblox Decal Uploader")
        self.root.geometry("550x550")

        self.roblox_security_cookie = None # Instance variable for the cookie
        self.user_groups = {}
        self.playwright_browser_persistent = None # Keeps browser instance
        self.playwright_page = None # Instance variable for the page
        # self.playwright_context = None # Instance variable for context if needed separately

        self.style = ttk.Style()
        self.style.theme_use('clam')
        dark_bg = "#2E2E2E"
        dark_fg = "#FFFFFF"
        dark_select_bg = "#4A4A4A"
        dark_entry_bg = "#3C3C3C"
        button_bg = "#5A5A5A"
        button_active_bg = "#6A6A6A"
        self.style.configure("TFrame", background=dark_bg)
        self.style.configure("TLabel", background=dark_bg, foreground=dark_fg, padding=5)
        self.style.configure("TButton", background=button_bg, foreground=dark_fg, padding=5, borderwidth=1)
        self.style.map("TButton", background=[('active', button_active_bg)], relief=[('pressed', 'sunken')])
        self.style.configure("TEntry", fieldbackground=dark_entry_bg, foreground=dark_fg, insertcolor=dark_fg, borderwidth=1, padding=5)
        self.style.configure("TCombobox", fieldbackground=dark_entry_bg, foreground=dark_fg, selectbackground=dark_select_bg, arrowcolor=dark_fg, borderwidth=1)
        self.style.map('TCombobox', fieldbackground=[('readonly', dark_entry_bg)], selectforeground=[('readonly', dark_fg)])
        self.root.configure(bg=dark_bg)

        main_frame = ttk.Frame(root, padding="10 10 10 10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        login_frame = ttk.LabelFrame(main_frame, text="Login Credentials", padding="10")
        login_frame.pack(fill=tk.X, pady=10)
        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.username_entry = ttk.Entry(login_frame, width=30)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.password_entry = ttk.Entry(login_frame, show="*", width=30)
        self.password_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.login_button = ttk.Button(login_frame, text="Login with Chromium", command=self.trigger_login_thread)
        self.login_button.grid(row=2, column=0, columnspan=2, pady=10)
        login_frame.columnconfigure(1, weight=1)

        upload_frame = ttk.LabelFrame(main_frame, text="Decal Upload", padding="10")
        upload_frame.pack(fill=tk.X, pady=10)
        ttk.Label(upload_frame, text="Select Group:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.group_var = tk.StringVar()
        self.group_dropdown = ttk.Combobox(upload_frame, textvariable=self.group_var, state="disabled", width=28)
        self.group_dropdown['values'] = ["Login to see groups"]
        self.group_dropdown.current(0)
        self.group_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.upload_button = ttk.Button(upload_frame, text="Select Image & Upload Decal", command=self.upload_decal, state=tk.DISABLED)
        self.upload_button.grid(row=1, column=0, columnspan=2, pady=10)
        upload_frame.columnconfigure(1, weight=1)

        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.status_text = tk.Text(status_frame, height=6, width=50, state=tk.DISABLED, wrap=tk.WORD, background=dark_entry_bg, foreground=dark_fg, relief="flat")
        self.status_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_status(self, message, error=False, success=False):
        self.status_text.config(state=tk.NORMAL)
        current_content = self.status_text.get(1.0, tk.END).strip()
        new_message = f"{current_content}\n{message}" if current_content else message
        self.status_text.delete(1.0, tk.END)
        tag_name = "status_message"
        if error: self.status_text.tag_configure(tag_name, foreground="red")
        elif success: self.status_text.tag_configure(tag_name, foreground="light green")
        else: self.status_text.tag_configure(tag_name, foreground=self.style.lookup("TLabel", "foreground"))
        self.status_text.insert(tk.END, new_message, tag_name)
        self.status_text.config(state=tk.DISABLED)
        self.status_text.see(tk.END)

    def trigger_login_thread(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if not username or not password:
            self.update_status("Username and Password cannot be empty.", error=True)
            return
        self.login_button.config(state=tk.DISABLED)
        self.update_status(f"Attempting to login as {username}...")
        login_thread = threading.Thread(target=self.perform_roblox_login, args=(username, password), daemon=True)
        login_thread.start()

    def perform_roblox_login(self, username, password):
        # global user_id, csrf_token # These are modified
        try:
            # If a browser is already open from a previous attempt, close it.
            if self.playwright_browser_persistent and self.playwright_browser_persistent.is_connected():
                try:
                    self.playwright_browser_persistent.close()
                    self.playwright_browser_persistent = None
                    self.playwright_page = None
                except Exception as e:
                    self.update_status(f"Minor error closing previous browser: {e}", error=True)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                self.playwright_browser_persistent = browser # Store new browser instance
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                self.playwright_page = context.new_page()

                self.update_status("Navigating to Roblox login page...")
                self.playwright_page.goto("https://www.roblox.com/login", timeout=60000)
                self.update_status("Filling login form...")
                self.playwright_page.fill("#login-username", username)
                self.playwright_page.fill("#login-password", password)
                self.playwright_page.click("#login-button")

                self.update_status("Please complete any 2FA or verification steps in the browser window.")
                self.update_status("Waiting for successful login (detection of homepage)...")
                self.playwright_page.wait_for_url("https://www.roblox.com/home", timeout=300000)
                self.update_status("Login detected! Extracting session information...", success=True)

                cookies = self.playwright_page.context.cookies()
                self.roblox_security_cookie = None
                for cookie_item in cookies:
                    if cookie_item['name'] == '.ROBLOSECURITY':
                        self.roblox_security_cookie = cookie_item['value']
                        self.update_status(f".ROBLOSECURITY cookie captured: ...{self.roblox_security_cookie[-10:]}", success=True)
                        break

                if not self.roblox_security_cookie:
                    raise ValueError("Failed to capture .ROBLOSECURITY cookie.")

                if not self.fetch_user_id_sync():
                    raise ValueError("Failed to fetch User ID.")

                if not self.refetch_csrf_token_sync(showMessage=True):
                    self.update_status("Warning: Failed to obtain CSRF token. Uploads may not work.", error=True) # Changed to warning

                global user_id # To read the global user_id set by fetch_user_id_sync
                if self.roblox_security_cookie and user_id:
                    self.fetch_user_groups_api()
                    self.login_button.config(state=tk.DISABLED) # Successfully logged in
                    self.update_status("Login successful. Browser remains open for uploads.", success=True)
                else:
                    raise ValueError("Missing cookie or user ID after login attempt.")

        except Exception as e:
            error_message = f"Login process error: {type(e).__name__} - {str(e)}"
            if "timeout" in str(e).lower() and hasattr(e, 'message') and "page.wait_for_url" not in e.message.lower():
                 error_message += "\n(Timeout waiting for login/2FA completion in browser?)"
            self.update_status(error_message, error=True)
            if self.playwright_browser_persistent and self.playwright_browser_persistent.is_connected():
                try: self.playwright_browser_persistent.close()
                except: pass
            self.playwright_browser_persistent = None
            self.playwright_page = None
            self.root.after(0, lambda: self.login_button.config(state=tk.NORMAL))


    def fetch_user_id_sync(self):
        global user_id # Modifies global user_id
        if not self.playwright_page:
            self.update_status("Playwright page not available for fetching user ID.", error=True)
            return False
        self.update_status("Fetching User ID...")
        try:
            response = self.playwright_page.request.get("https://users.roblox.com/v1/users/authenticated")
            if response.ok:
                user_data = response.json()
                fetched_user_id = user_data.get("id")
                if fetched_user_id:
                    user_id = fetched_user_id
                    self.update_status(f"Logged in User ID: {user_id}", success=True)
                    return True
            self.update_status(f"Failed to get user ID. Status: {response.status} - {response.text()[:100]}", error=True)
            return False
        except Exception as e:
            self.update_status(f"Error fetching user ID: {str(e)}", error=True)
            return False

    def fetch_user_groups_api(self):
        global user_id # Reads global user_id
        if not user_id: self.update_status("User ID not available for group fetch.", error=True); return
        if not self.roblox_security_cookie: self.update_status("Not logged in for group fetch.", error=True); return
        if not self.playwright_page: self.update_status("Playwright page not available for group fetch.", error=True); return

        self.update_status("Fetching user groups...")
        try:
            response = self.playwright_page.request.get(f"https://groups.roblox.com/v2/users/{user_id}/groups/roles")
            if response.ok:
                groups_data = response.json()
                if not groups_data or 'data' not in groups_data or not groups_data['data']:
                    self.update_status("No group data returned or data is empty.", error=False)
                    self.root.after(0, lambda: self.group_dropdown.config(values=["No groups found"], state="disabled"))
                    self.root.after(0, lambda: self.upload_button.config(state=tk.DISABLED))
                    return

                self.user_groups.clear()
                group_display_names = [f"{item['group']['name']} (ID: {item['group']['id']})"
                                       for item in groups_data['data'] if item.get('group')]
                for item in groups_data['data']: # Populate self.user_groups
                    if item.get('group'):
                         self.user_groups[f"{item['group']['name']} (ID: {item['group']['id']})"] = item['group']['id']

                if group_display_names:
                    self.root.after(0, lambda: self.group_dropdown.config(values=group_display_names, state="readonly"))
                    self.root.after(0, lambda: self.group_dropdown.current(0))
                    self.root.after(0, lambda: self.upload_button.config(state=tk.NORMAL))
                    self.update_status(f"Found {len(group_display_names)} groups.", success=True)
                else:
                    self.update_status("No groups found where you have a role.", error=False)
                    self.root.after(0, lambda: self.group_dropdown.config(values=["No groups found"], state="disabled"))
                    self.root.after(0, lambda: self.upload_button.config(state=tk.DISABLED))
            else:
                self.update_status(f"Failed to fetch groups. Status: {response.status} - {response.text()[:100]}", error=True)
        except Exception as e:
            self.update_status(f"Error fetching groups: {str(e)}", error=True)

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit? This will close the controlled browser window if it's open."):
            if self.playwright_browser_persistent and self.playwright_browser_persistent.is_connected():
                try: self.playwright_browser_persistent.close()
                except Exception as e: print(f"Error closing Playwright browser: {e}")
            self.root.destroy()

    def upload_decal(self):
        global csrf_token # Reads global csrf_token
        selected_group_str = self.group_var.get()
        if not selected_group_str or "Login to see groups" in selected_group_str or "No groups found" in selected_group_str:
            self.update_status("Please select a valid group first.", error=True); return
        group_id = self.user_groups.get(selected_group_str)
        if not group_id: self.update_status("Selected group ID not found.", error=True); return
        if not self.roblox_security_cookie: self.update_status("Not logged in.", error=True); return

        if not csrf_token:
            self.update_status("CSRF token missing. Attempting refresh...", error=True)
            if not self.refetch_csrf_token_sync(showMessage=True) or not csrf_token:
                self.update_status("Failed to get CSRF token for upload. Please try logging in again.", error=True); return

        filepath = filedialog.askopenfilename(title="Select Decal Image", filetypes=(("PNG", "*.png"), ("JPEG", "*.jpg;*.jpeg")))
        if not filepath: self.update_status("Image selection cancelled."); return

        self.update_status(f"Preparing to upload {filepath.split('/')[-1]} to group ID: {group_id}...")
        self.upload_button.config(state=tk.DISABLED)
        threading.Thread(target=self.perform_decal_upload, args=(filepath, group_id), daemon=True).start()

    def perform_decal_upload(self, filepath, group_id):
        global csrf_token # Reads global
        if not self.playwright_page or not self.playwright_page.context:
            self.update_status("Browser session not available for upload.", error=True)
            self.root.after(0, lambda: self.upload_button.config(state=tk.NORMAL)); return
        if not csrf_token: # Final check
            self.update_status("CSRF token still missing before upload request. Aborting.", error=True)
            self.root.after(0, lambda: self.upload_button.config(state=tk.NORMAL)); return

        try:
            with open(filepath, "rb") as img_file: image_data = img_file.read()
            image_name = filepath.split('/')[-1]
            asset_payload = {"assetType": "Decal", "creationContext": {"creator": {"groupId": group_id}},
                             "description": f"Uploaded: {image_name}", "displayName": image_name.split('.')[0]}
            self.update_status(f"Uploading '{image_name}' to group {group_id}...")
            headers = {"X-CSRF-TOKEN": csrf_token, "Cookie": f".ROBLOSECURITY={self.roblox_security_cookie}"}

            response = self.playwright_page.request.post(
                "https://apis.roblox.com/assets/v1/assets", headers=headers,
                multipart={"request": json.dumps(asset_payload),
                           "fileContent": {"name": image_name,
                                           "mimeType": "image/png" if filepath.endswith(".png") else "image/jpeg",
                                           "buffer": image_data}})
            if response.ok:
                res_data = response.json()
                asset_id = res_data.get("assetId") or (res_data.get("path","").split("/")[2] if "path" in res_data else None)
                if asset_id:
                    self.update_status(f"Decal '{image_name}' uploaded! Asset ID: {asset_id}", success=True)
                    self.update_status(f"View: https://www.roblox.com/library/{asset_id}/")
                else: self.update_status(f"Upload OK but Asset ID missing: {res_data}", success=True)
            else:
                err_body = response.text()
                self.update_status(f"Upload failed. Status: {response.status}", error=True)
                self.update_status(f"Details: {err_body[:200]}...", error=True)
                if response.status == 403:
                    self.update_status("403 Error: CSRF or Cookie likely invalid. Try re-login.", error=True)
                    if not self.refetch_csrf_token_sync(showMessage=True):
                         self.update_status("Auto-refresh of CSRF failed.",error=True)
        except Exception as e:
            self.update_status(f"Error during decal upload: {str(e)}", error=True)
        finally:
            self.root.after(0, lambda: self.upload_button.config(state=tk.NORMAL))

    def refetch_csrf_token_sync(self, showMessage=False):
        global csrf_token # Modifies global
        if not self.playwright_page:
            if showMessage: self.update_status("Page not available for CSRF fetch.", error=True)
            return False
        if not self.roblox_security_cookie:
            if showMessage: self.update_status("Cannot fetch CSRF: .ROBLOSECURITY cookie missing.", error=True)
            return False

        if showMessage: self.update_status("Attempting CSRF token refresh...")
        try:
            response = self.playwright_page.request.post(
                "https://auth.roblox.com/v2/logout", # Standard probe endpoint
                headers={"Cookie": f".ROBLOSECURITY={self.roblox_security_cookie}"}, data={},
                fail_on_status_code=False)
            if response.status == 403:
                new_csrf = response.headers.get('x-csrf-token')
                if new_csrf:
                    csrf_token = new_csrf
                    if showMessage: self.update_status(f"New CSRF token obtained: ...{new_csrf[-10:]}", success=True)
                    return True
                if showMessage: self.update_status("CSRF refresh: 403, but no x-csrf-token header.", error=True)
                return False
            if showMessage: self.update_status(f"CSRF refresh: Unexpected status {response.status}.", error=True)
            return False
        except Exception as e:
            if showMessage: self.update_status(f"Error during CSRF refresh: {str(e)}", error=True)
            return False

if __name__ == "__main__":
    root = tk.Tk()
    app = RobloxUploaderApp(root)
    root.mainloop()

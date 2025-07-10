import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from playwright.sync_api import sync_playwright
import threading
import time
import json
import atexit

# Global variables
user_id = None
csrf_token = None

class RobloxUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Roblox Decal Uploader")
        self.root.geometry("550x550")
        
        # Login thread Playwright instances (temporary)
        self.login_playwright_instance = None
        self.login_browser = None
        self.login_page = None
        
        # Main thread Playwright instances (for uploads)
        self.main_playwright_instance = None
        self.main_browser = None
        self.main_page = None
        
        # Session data
        self.roblox_security_cookie = None
        self.user_groups = {}
        self.session_cookies = []  # Store all cookies for session transfer
        
        # Register cleanup function
        atexit.register(self.cleanup_playwright)
        
        self.setup_ui()
        
    def setup_ui(self):
        # Dark theme styling
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
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Login frame
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
        
        # Upload frame
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
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.status_text = tk.Text(status_frame, height=6, width=50, state=tk.DISABLED, wrap=tk.WORD, 
                                 background=dark_entry_bg, foreground=dark_fg, relief="flat")
        self.status_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        # Set up cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def cleanup_playwright(self):
        """Clean up all Playwright resources"""
        try:
            # Cleanup login thread instances
            if self.login_page:
                self.login_page.close()
                self.login_page = None
            if self.login_browser:
                self.login_browser.close()
                self.login_browser = None
            if self.login_playwright_instance:
                self.login_playwright_instance.stop()
                self.login_playwright_instance = None
                
            # Cleanup main thread instances
            if self.main_page:
                self.main_page.close()
                self.main_page = None
            if self.main_browser:
                self.main_browser.close()
                self.main_browser = None
            if self.main_playwright_instance:
                self.main_playwright_instance.stop()
                self.main_playwright_instance = None
        except Exception as e:
            print(f"Error during Playwright cleanup: {e}")
    
    def update_status(self, message, error=False, success=False):
        def _update():
            self.status_text.config(state=tk.NORMAL)
            current_content = self.status_text.get(1.0, tk.END).strip()
            new_message = f"{current_content}\n{message}" if current_content else message
            self.status_text.delete(1.0, tk.END)
            
            tag_name = "status_message"
            if error:
                self.status_text.tag_configure(tag_name, foreground="red")
            elif success:
                self.status_text.tag_configure(tag_name, foreground="light green")
            else:
                self.status_text.tag_configure(tag_name, foreground=self.style.lookup("TLabel", "foreground"))
            
            self.status_text.insert(tk.END, new_message, tag_name)
            self.status_text.config(state=tk.DISABLED)
            self.status_text.see(tk.END)
        
        # Ensure UI updates happen on main thread
        if threading.current_thread() == threading.main_thread():
            _update()
        else:
            self.root.after(0, _update)
    
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
        global user_id, csrf_token
        
        try:
            # Clean up any existing login instances
            if self.login_page:
                try:
                    self.login_page.close()
                except:
                    pass
                self.login_page = None
            
            if self.login_browser:
                try:
                    self.login_browser.close()
                except:
                    pass
                self.login_browser = None
                
            if self.login_playwright_instance:
                try:
                    self.login_playwright_instance.stop()
                except:
                    pass
                self.login_playwright_instance = None
            
            # Initialize Playwright for login thread
            self.login_playwright_instance = sync_playwright().start()
            self.login_browser = self.login_playwright_instance.chromium.launch(headless=False)
            
            context = self.login_browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            self.login_page = context.new_page()
            
            self.update_status("Navigating to Roblox login page...")
            self.login_page.goto("https://www.roblox.com/login", timeout=60000)
            
            self.update_status("Filling login form...")
            self.login_page.fill("#login-username", username)
            self.login_page.fill("#login-password", password)
            self.login_page.click("#login-button")
            
            self.update_status("Please complete any 2FA or verification steps in the browser window.")
            self.update_status("Waiting for successful login (detection of homepage)...")
            
            # Wait for login success
            self.login_page.wait_for_url("https://www.roblox.com/home", timeout=300000)
            
            self.update_status("Login detected! Extracting session information...", success=True)
            
            # Extract ALL cookies for session transfer with proper formatting
            raw_cookies = self.login_page.context.cookies()
            self.session_cookies = []
            self.roblox_security_cookie = None
            
            for cookie in raw_cookies:
                # Ensure all required fields are present and properly formatted
                formatted_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie.get('domain', '.roblox.com'),
                    'path': cookie.get('path', '/'),
                    'expires': cookie.get('expires', -1),
                    'httpOnly': cookie.get('httpOnly', False),
                    'secure': cookie.get('secure', False),
                    'sameSite': cookie.get('sameSite', 'Lax')
                }
                self.session_cookies.append(formatted_cookie)
                
                if cookie['name'] == '.ROBLOSECURITY':
                    self.roblox_security_cookie = cookie['value']
                    self.update_status(f".ROBLOSECURITY cookie captured: ...{self.roblox_security_cookie[-10:]}", success=True)
            
            if not self.roblox_security_cookie:
                raise ValueError("Failed to capture .ROBLOSECURITY cookie.")
            
            # Fetch user ID using login thread
            if not self.fetch_user_id_login_thread():
                raise ValueError("Failed to fetch User ID.")
            
            # Fetch user groups using login thread
            if not self.fetch_user_groups_login_thread():
                self.update_status("Warning: Failed to fetch user groups.", error=True)
            
            # Schedule main thread setup
            self.root.after(0, self.setup_main_thread_playwright)
            
        except Exception as e:
            error_message = f"Login process error: {type(e).__name__} - {str(e)}"
            if "timeout" in str(e).lower():
                error_message += "\n(Timeout waiting for login/2FA completion in browser?)"
            
            self.update_status(error_message, error=True)
            self.root.after(0, lambda: self.login_button.config(state=tk.NORMAL))
    
    def fetch_user_id_login_thread(self):
        global user_id
        
        if not self.login_page:
            self.update_status("Login page not available for fetching user ID.", error=True)
            return False
        
        self.update_status("Fetching User ID...")
        
        try:
            response = self.login_page.request.get("https://users.roblox.com/v1/users/authenticated")
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
    
    def fetch_user_groups_login_thread(self):
        global user_id
        
        if not user_id:
            self.update_status("User ID not available for group fetch.", error=True)
            return False
        
        if not self.login_page:
            self.update_status("Login page not available for group fetch.", error=True)
            return False
        
        self.update_status("Fetching user groups...")
        
        try:
            response = self.login_page.request.get(f"https://groups.roblox.com/v2/users/{user_id}/groups/roles")
            
            if response.ok:
                groups_data = response.json()
                
                if not groups_data or 'data' not in groups_data or not groups_data['data']:
                    self.update_status("No group data returned or data is empty.")
                    return False
                
                self.user_groups.clear()
                group_display_names = []
                
                for item in groups_data['data']:
                    if item.get('group'):
                        group_name = f"{item['group']['name']} (ID: {item['group']['id']})"
                        group_display_names.append(group_name)
                        self.user_groups[group_name] = item['group']['id']
                
                if group_display_names:
                    self.update_status(f"Found {len(group_display_names)} groups.", success=True)
                    return True
                else:
                    self.update_status("No groups found where you have a role.")
                    return False
            else:
                self.update_status(f"Failed to fetch groups. Status: {response.status} - {response.text()[:100]}", error=True)
                return False
                
        except Exception as e:
            self.update_status(f"Error fetching groups: {str(e)}", error=True)
            return False
    
    def setup_main_thread_playwright(self):
        """Set up Playwright on main thread using session cookies"""
        try:
            self.update_status("Setting up main thread session...")
            
            # Initialize main thread Playwright
            self.main_playwright_instance = sync_playwright().start()
            self.main_browser = self.main_playwright_instance.chromium.launch(headless=False)  # Keep visible for debugging
            
            context = self.main_browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            # Add all session cookies to maintain login state
            try:
                context.add_cookies(self.session_cookies)
                self.update_status(f"Transferred {len(self.session_cookies)} cookies to main thread.", success=True)
            except Exception as e:
                self.update_status(f"Error transferring cookies: {str(e)}", error=True)
                raise e
            
            self.main_page = context.new_page()
            
            # Navigate to Roblox to activate the session
            self.main_page.goto("https://www.roblox.com/home", timeout=30000)
            
            # Validate session by checking if we're logged in
            if not self.validate_main_thread_session():
                raise Exception("Session validation failed - not properly logged in")
            
            # Get CSRF token for uploads
            if self.refetch_csrf_token_main_thread(showMessage=True):
                # Update UI elements
                if self.user_groups:
                    group_display_names = list(self.user_groups.keys())
                    self.group_dropdown.config(values=group_display_names, state="readonly")
                    self.group_dropdown.current(0)
                    self.upload_button.config(state=tk.NORMAL)
                else:
                    self.group_dropdown.config(values=["No groups found"], state="disabled")
                    self.upload_button.config(state=tk.DISABLED)
                
                self.login_button.config(state=tk.DISABLED)
                self.update_status("Login successful. Ready for uploads!", success=True)
            else:
                raise Exception("Failed to obtain CSRF token")
                
        except Exception as e:
            self.update_status(f"Error setting up main thread session: {str(e)}", error=True)
            self.login_button.config(state=tk.NORMAL)
    
    def validate_main_thread_session(self):
        """Validate that the main thread session is properly authenticated"""
        try:
            self.update_status("Validating session...")
            response = self.main_page.request.get("https://users.roblox.com/v1/users/authenticated")
            
            if response.ok:
                user_data = response.json()
                session_user_id = user_data.get("id")
                if session_user_id and session_user_id == user_id:
                    self.update_status("Session validation successful!", success=True)
                    return True
                else:
                    self.update_status(f"Session user ID mismatch: {session_user_id} vs {user_id}", error=True)
                    return False
            else:
                self.update_status(f"Session validation failed: {response.status}", error=True)
                return False
                
        except Exception as e:
            self.update_status(f"Error validating session: {str(e)}", error=True)
            return False
    
    def refetch_csrf_token_main_thread(self, showMessage=False):
        global csrf_token
        
        if not self.main_page:
            if showMessage:
                self.update_status("Main page not available for CSRF fetch.", error=True)
            return False
        
        if not self.roblox_security_cookie:
            if showMessage:
                self.update_status("Cannot fetch CSRF: .ROBLOSECURITY cookie missing.", error=True)
            return False
        
        if showMessage:
            self.update_status("Obtaining CSRF token for main thread...")
        
        try:
            # Use a different endpoint that's more reliable for CSRF token generation
            response = self.main_page.request.post(
                "https://auth.roblox.com/v2/login",
                headers={
                    "Cookie": f".ROBLOSECURITY={self.roblox_security_cookie}",
                    "Content-Type": "application/json"
                },
                data=json.dumps({}),
                fail_on_status_code=False
            )
            
            if response.status == 403:
                new_csrf = response.headers.get('x-csrf-token')
                if new_csrf:
                    csrf_token = new_csrf
                    if showMessage:
                        self.update_status(f"CSRF token obtained: ...{new_csrf[-10:]}", success=True)
                    return True
                
                if showMessage:
                    self.update_status("CSRF refresh: 403, but no x-csrf-token header.", error=True)
                return False
            
            if showMessage:
                self.update_status(f"CSRF refresh: Unexpected status {response.status}.", error=True)
            return False
            
        except Exception as e:
            if showMessage:
                self.update_status(f"Error during CSRF refresh: {str(e)}", error=True)
            return False
    
    def upload_decal(self):
        global csrf_token
        
        selected_group_str = self.group_var.get()
        if not selected_group_str or "Login to see groups" in selected_group_str or "No groups found" in selected_group_str:
            self.update_status("Please select a valid group first.", error=True)
            return
        
        group_id = self.user_groups.get(selected_group_str)
        if not group_id:
            self.update_status("Selected group ID not found.", error=True)
            return
        
        if not self.roblox_security_cookie:
            self.update_status("Not logged in.", error=True)
            return
        
        if not self.main_page:
            self.update_status("Main thread session not available.", error=True)
            return
        
        # Validate session before upload
        if not self.validate_main_thread_session():
            self.update_status("Session validation failed. Please re-login.", error=True)
            return
        
        if not csrf_token:
            self.update_status("CSRF token missing. Attempting refresh...", error=True)
            if not self.refetch_csrf_token_main_thread(showMessage=True) or not csrf_token:
                self.update_status("Failed to get CSRF token for upload. Please try logging in again.", error=True)
                return
        
        filepath = filedialog.askopenfilename(
            title="Select Decal Image",
            filetypes=(("PNG", "*.png"), ("JPEG", "*.jpg;*.jpeg"))
        )
        
        if not filepath:
            self.update_status("Image selection cancelled.")
            return
        
        self.update_status(f"Preparing to upload {filepath.split('/')[-1]} to group ID: {group_id}...")
        self.upload_button.config(state=tk.DISABLED)
        
        # Perform upload directly on main thread (no threading issues)
        self.perform_decal_upload(filepath, group_id)

    def perform_decal_upload(self, filepath, group_id):
        """Perform decal upload on main thread using main thread Playwright instance"""
        global csrf_token
        
        try:
            # Read image file
            with open(filepath, "rb") as img_file:
                image_data = img_file.read()
            
            image_name = filepath.split('/')[-1]
            
            asset_payload = {
                "assetType": "Decal",
                "creationContext": {"creator": {"groupId": group_id}},
                "description": f"Uploaded: {image_name}",
                "displayName": image_name.split('.')[0]
            }
            
            self.update_status(f"Uploading '{image_name}' to group {group_id}...")
            
            # Build headers with all necessary authentication
            headers = {
                "X-CSRF-TOKEN": csrf_token,
                "Cookie": f".ROBLOSECURITY={self.roblox_security_cookie}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # Debug: Log the request details
            self.update_status(f"Using CSRF token: ...{csrf_token[-10:]}")
            self.update_status(f"Using cookie: ...{self.roblox_security_cookie[-10:]}")
            
            # Perform the upload request using main thread page
            response = self.main_page.request.post(
                "https://apis.roblox.com/assets/v1/assets",
                headers=headers,
                multipart={
                    "request": json.dumps(asset_payload),
                    "fileContent": {
                        "name": image_name,
                        "mimeType": "image/png" if filepath.endswith(".png") else "image/jpeg",
                        "buffer": image_data
                    }
                }
            )
            
            if response.ok:
                res_data = response.json()
                asset_id = res_data.get("assetId") or (res_data.get("path", "").split("/")[2] if "path" in res_data else None)
                
                if asset_id:
                    self.update_status(f"Decal '{image_name}' uploaded successfully! Asset ID: {asset_id}", success=True)
                    self.update_status(f"View at: https://www.roblox.com/library/{asset_id}/")
                else:
                    self.update_status(f"Upload completed but Asset ID missing: {res_data}", success=True)
            else:
                err_body = response.text()
                self.update_status(f"Upload failed. Status: {response.status}", error=True)
                self.update_status(f"Details: {err_body[:200]}...", error=True)
                
                if response.status == 403:
                    self.update_status("403 Error: Authentication failed. Session may have expired.", error=True)
                    self.update_status("Please close the application and log in again.", error=True)
                    
        except Exception as e:
            self.update_status(f"Error during decal upload: {str(e)}", error=True)
        finally:
            self.upload_button.config(state=tk.NORMAL)
    
    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit? This will close all browser windows."):
            self.cleanup_playwright()
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RobloxUploaderApp(root)
    root.mainloop()

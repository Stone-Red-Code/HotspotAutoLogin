import json
import os
import sys
import argparse
import winreg
import requests
import time
import subprocess
import re
import socket
import pystray
import threading
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as messagebox
from urllib.parse import urlparse
from tkinter import Text, Scrollbar
from PIL import Image
from collections import deque
from datetime import datetime
import dns.resolver
dns.resolver.override_system_resolver(dns.resolver.Resolver())
dns.resolver.default_resolver = dns.resolver.Resolver()
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Change the current working directory to the program's directory.
# Works for both the script and a PyInstaller build, and is required when launched at Windows startup,
# where the working directory is not the program folder (so config.json and icon.ico would not be found).
if getattr(sys, "frozen", False):
    script_dir = os.path.dirname(sys.executable)
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Program Information
program_name = "HotspotAutoLogin"
version = "v1.90"
github_link = "https://github.com/denizsafak/HotspotAutoLogin"

# Command line arguments
#   --auto        Skip profile selection and auto-detect which profile to use from the connected network
#   --background  Don't open the log window at startup (used when starting with Windows)
arg_parser = argparse.ArgumentParser(add_help=False)
arg_parser.add_argument("--auto", action="store_true")
arg_parser.add_argument("--background", action="store_true")
args, _ = arg_parser.parse_known_args()
auto_mode = args.auto

# Start with Windows (HKCU Run key, no admin rights needed)
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --auto --background'
    # Use pythonw.exe so no console window is shown at startup
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    return f'"{pythonw}" "{os.path.abspath(__file__)}" --auto --background'

def is_autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            winreg.QueryValueEx(key, program_name)
            return True
    except OSError:
        return False

def set_autostart(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, program_name, 0, winreg.REG_SZ, get_autostart_command())
        else:
            try:
                winreg.DeleteValue(key, program_name)
            except FileNotFoundError:
                pass

# If autostart is enabled, keep the registered path up to date in case the program folder was moved
if is_autostart_enabled():
    try:
        set_autostart(True)
    except OSError:
        pass

# Function to center a window on the screen
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

def run_profile(event=None):
    global selected_profile
    refresh_profile_details()
    selected_index = listbox.curselection()
    if selected_index:
        selected_index = int(selected_index[0])
        selected_profile = profiles[selected_index]
        root.destroy()

# Run in auto mode: the profile is picked automatically based on the connected network
def run_auto():
    global auto_mode, selected_profile
    refresh_profile_details()
    if not profiles:
        messagebox.showerror("No Profiles", "Add at least one profile before using Auto mode.")
        return
    auto_mode = True
    selected_profile = None
    root.destroy()

def toggle_autostart():
    try:
        set_autostart(autostart_var.get())
    except OSError as e:
        autostart_var.set(is_autostart_enabled())
        messagebox.showerror("Start with Windows", f"Could not change the startup setting: {e}")

# Define a function to update the profile details
def update_profile_details(event):
    global selected_profile
    selected_index = listbox.curselection()
    if selected_index:
        selected_index = int(selected_index[0])
        selected_profile = profiles[selected_index]
        profile_name.config(text=f"Selected Profile: {selected_profile['name']}")
        profile_details.config(state=tk.NORMAL)
        profile_details.delete(1.0, tk.END)
        # Insert profile details as JSON with coloring
        profile_details.tag_configure("bold", font=("Courier New", 10, "bold"), foreground="#08872a")
        profile_details.tag_configure("normal", font=("Courier New", 10), foreground="#000000")
        profile_json = json.dumps({k: v for k, v in selected_profile.items() if k != 'name'}, indent=4)
        for line in profile_json.splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                profile_details.insert(tk.END, key + ':', "bold")
                profile_details.insert(tk.END, value + "\n", "normal")
            else:
                profile_details.insert(tk.END, line + "\n", "normal")
        profile_details.config(state=tk.DISABLED)
    else:
        profile_name.config(text="Selected Profile: ")
        profile_details.config(state=tk.NORMAL)
        profile_details.delete(1.0, tk.END)
        profile_details.config(state=tk.DISABLED)

# Function to refresh the profile details
def refresh_profile_details():
    global profiles
    # Get the index of the currently selected profile
    selected_index = listbox.curselection()
    selected_index = int(selected_index[0]) if selected_index else None
    # Reload configuration from file
    with open("config.json", "r") as f:
        config = json.load(f)
    profiles = config.get("profiles", [])
    listbox.delete(0, tk.END)  # Clear the listbox
    for profile in profiles:
        listbox.insert(tk.END, profile['name'])
    # Reselect the previously selected profile if it exists
    if selected_index is not None and selected_index < len(profiles):
        listbox.select_set(selected_index)  
        update_profile_details(None)

# Function to open the config file
def open_config():
    subprocess.Popen(["start", "config.json"], shell=True)

# Load configuration from file
with open("config.json", "r") as f:
    config = json.load(f)

# Get the list of profiles
profiles = config.get("profiles", [])
# Create the main window
root = tk.Tk()
if auto_mode:
    root.withdraw()  # Started with --auto, the profile selection window is not needed
root.title(f"Profile Selection - {program_name} {version}")
root.iconbitmap("icon.ico")
# Set a maximum size for the window
width = 850
height = 300
root.minsize(width, height)  # Adjust the values as needed
center_window(root, width, height)
# Create a frame for listing profiles
profiles_frame = tk.Frame(root)
profiles_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
# Create a frame to hold the listbox and its scrollbar
listbox_frame = tk.Frame(profiles_frame)
listbox_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
# Create a listbox to display available profiles
listbox = tk.Listbox(listbox_frame, selectmode=tk.SINGLE)
listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

def scan_wifi_ssids():
    ssids = []
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks"],
            capture_output=True,
            text=True,
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("SSID"):
                parts = line.split(" : ")
                if len(parts) == 2:
                    ssids.append(parts[1])
    except:
        pass
    return ssids

def add_new_profile():
    def show_context_menu(event):
        context_menu = tk.Menu(root, tearoff=0)
        context_menu.add_command(label="Cut", command=lambda: event.widget.event_generate("<<Cut>>"))
        context_menu.add_command(label="Copy", command=lambda: event.widget.event_generate("<<Copy>>"))
        context_menu.add_command(label="Paste", command=lambda: event.widget.event_generate("<<Paste>>"))
        context_menu.tk_popup(event.x_root, event.y_root)

    def get_current_connected_ssid():
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], text=True, startupinfo=startupinfo)
            match = re.search(r"^\s*SSID\s*:\s*(.+)$", output, re.MULTILINE)
            if match:
                return match.group(1).strip()
        except subprocess.CalledProcessError:
            pass
        return None

    def toggle_ethernet():
        if use_ethernet_var.get():
            ssid_combo.config(state="disabled")
        else:
            ssid_combo.config(state="normal")

    def refresh_wifi_list():
        ssid_list = scan_wifi_ssids()
        ssid_combo["values"] = ssid_list
        if ssid_list and not use_ethernet_var.get():
            ssid_var.set(ssid_list[0])

    def error_message(message):
        if message:
            error_label.config(text=message, bg="red")
            if not error_label.winfo_ismapped():
                error_label.pack(fill="x", pady=(5, 5))
                add_window.update_idletasks()
                add_window.geometry(f"{add_window.winfo_width()}x{add_window.winfo_height() + error_label.winfo_reqheight()+10}")
        else:
            if error_label.winfo_ismapped():
                add_window.geometry(f"{add_window.winfo_width()}x{add_window.winfo_height() - error_label.winfo_reqheight()+10}")
                error_label.pack_forget()

    def save_profile():
        raw_payload = payload_text.get("1.0", tk.END).rstrip("\n").strip(" ,")
        raw_headers = headers_text.get("1.0", tk.END).rstrip("\n").strip(" ,")
        # Validate inputs
        name = name_var.get().strip()
        ssid = ssid_var.get().strip()
        url = url_var.get().strip()
        internet_check_url = internet_check_url_var.get().strip()
        check_every_second = check_every_second_var.get().strip()
        dialog_width = dialog_width_var.get().strip()
        dialog_height = dialog_height_var.get().strip()

        if not name:
            error_message("Name cannot be empty.")
            return
        if any(profile['name'].strip().lower() == name.lower() for profile in profiles):
            error_message("Profile with this name already exists.")
            return
        if not ssid:
            error_message("SSID cannot be empty.")
            return
        if not url:
            error_message("Request URL cannot be empty.")
            return
        # Check if URL is valid
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            error_message("Invalid URL.")
            return
        if not raw_payload.strip():
            error_message("Payload cannot be empty.")
            return
        if not internet_check_url:
            error_message("internet_check_url_var cannot be empty.")
            return
        if not check_every_second:
            error_message("check_every_second cannot be empty.")
            return
        if not dialog_width:
            error_message("dialog_width cannot be empty.")
            return
        if not dialog_height:
            error_message("dialog_height cannot be empty.")
            return

        try:
            parsed_headers = json.loads(raw_headers)
        except json.JSONDecodeError:
            error_message("Headers must be valid JSON.")
            return

        if len(raw_payload.splitlines()) == 1:
            parsed_payload = raw_payload
        else:
            try:
                parsed_payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                error_message("Payload must be valid JSON.")
                return

        # Hide error message if any
        error_message("")
        new_profile = {
            "name": name,
            "url": url,
            "internet_check_url": internet_check_url,
            "payload": parsed_payload,
            "headers": parsed_headers,
            "check_every_second": int(check_every_second),
            "dialog_geometry": {"width": int(dialog_width), "height": int(dialog_height)}
        }
        if not use_ethernet_var.get():
            new_profile["ssid"] = ssid
        profiles.append(new_profile)
        config["profiles"] = profiles
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        listbox.insert(tk.END, name)
        add_window.destroy()

    def cancel():
        add_window.destroy()
    add_window = tk.Toplevel(root)
    add_window.title("Add New Profile")
    container = tk.Frame(add_window, padx=10, pady=5)
    container.pack(fill="both", expand=True)
    wifi_ssids = scan_wifi_ssids()
    connected_ssid = get_current_connected_ssid()
    if not connected_ssid and wifi_ssids:
        connected_ssid = wifi_ssids[0]
    if not connected_ssid:
        connected_ssid = "Enter SSID"

    def generate_unique_name():
        base_name = "New profile"
        existing_names = [profile['name'].strip().lower() for profile in profiles]
        if base_name.lower() not in existing_names:
            return base_name
        i = 2
        while f"{base_name} {i}".lower() in existing_names:
            i += 1
        return f"{base_name} {i}"
    
    name_var = tk.StringVar(value=generate_unique_name())
    ssid_var = tk.StringVar(value=connected_ssid)
    url_var = tk.StringVar()
    internet_check_url_var = tk.StringVar(value="8.8.8.8")
    check_every_second_var = tk.StringVar(value="600")
    dialog_width_var = tk.StringVar(value="1024")
    dialog_height_var = tk.StringVar(value="500")
    use_ethernet_var = tk.BooleanVar(value=False)
    # Name
    name_frame = tk.Frame(container)
    name_frame.pack(fill="x", pady=5)
    tk.Label(name_frame, text="Name:").pack(side="left")
    name_entry = tk.Entry(name_frame, textvariable=name_var)
    name_entry.pack(side="left", fill="x", expand=True)
    name_entry.bind("<Button-3>", show_context_menu)
    # SSID row
    ssid_frame = tk.Frame(container)
    ssid_frame.pack(fill="x", pady=5)
    tk.Label(ssid_frame, text="SSID:").pack(side="left")
    ssid_combo = ttk.Combobox(ssid_frame, textvariable=ssid_var, values=wifi_ssids)
    ssid_combo.pack(side="left", fill="x", expand=True)
    ssid_combo.bind("<Button-3>", show_context_menu)
    tk.Button(ssid_frame, text="Refresh", command=refresh_wifi_list).pack(side="left", padx=5)
    ethernet_chk = tk.Checkbutton(ssid_frame, text="Ethernet", variable=use_ethernet_var, command=toggle_ethernet)
    ethernet_chk.pack(side="left", padx=5)
    # URL
    url_frame = tk.Frame(container)
    url_frame.pack(fill="x", pady=5)
    tk.Label(url_frame, text="Request URL:").pack(side="left")
    url_entry = tk.Entry(url_frame, textvariable=url_var)
    url_entry.pack(side="left", fill="x", expand=True)
    url_entry.bind("<Button-3>", show_context_menu)
    # internet_check_url
    internet_frame = tk.Frame(container)
    internet_frame.pack(fill="x", pady=5)
    tk.Label(internet_frame, text="internet_check_url:").pack(side="left")
    internet_entry = tk.Entry(internet_frame, textvariable=internet_check_url_var)
    internet_entry.pack(side="left", fill="x", expand=True)
    internet_entry.bind("<Button-3>", show_context_menu)
    # payload
    tk.Label(container, text="payload:").pack(anchor="w")
    payload_frame = tk.Frame(container)
    payload_frame.pack(fill="both", pady=5, expand=True)
    payload_text = tk.Text(payload_frame, height=8)
    payload_text.pack(side="left", fill="both", expand=True)
    payload_text.bind("<Button-3>", show_context_menu)
    payload_scroll = tk.Scrollbar(payload_frame, command=payload_text.yview)
    payload_scroll.pack(side="right", fill="y")
    payload_text.config(yscrollcommand=payload_scroll.set)
    # headers
    tk.Label(container, text="headers:").pack(anchor="w")
    headers_frame = tk.Frame(container)
    headers_frame.pack(fill="both", pady=5, expand=True)
    headers_text = tk.Text(headers_frame, height=8)
    headers_text.pack(side="left", fill="both", expand=True)
    headers_text.bind("<Button-3>", show_context_menu)
    headers_scroll = tk.Scrollbar(headers_frame, command=headers_text.yview)
    headers_scroll.pack(side="right", fill="y")
    headers_text.config(yscrollcommand=headers_scroll.set)
    headers_text.insert(tk.END, """{
    "Content-Type": "application/x-www-form-urlencoded",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}""")
    # check_every_second
    check_frame = tk.Frame(container)
    check_frame.pack(fill="x", pady=5)
    tk.Label(check_frame, text="check_every_second:").pack(side="left")
    check_entry = tk.Entry(check_frame, textvariable=check_every_second_var)
    check_entry.pack(side="left", fill="x", expand=True)
    check_entry.bind("<Button-3>", show_context_menu)
    # dialog_geometry width and height
    dialog_geometry_frame = tk.Frame(container)
    dialog_geometry_frame.pack(fill="x", pady=5)
    tk.Label(dialog_geometry_frame, text="dialog_geometry:").pack(side="left")
    tk.Label(dialog_geometry_frame, text="width:").pack(side="left", padx=(0, 0))
    dialog_width_entry = tk.Entry(dialog_geometry_frame, textvariable=dialog_width_var, width=5)
    dialog_width_entry.pack(side="left")
    dialog_width_entry.bind("<Button-3>", show_context_menu)
    tk.Label(dialog_geometry_frame, text="height:").pack(side="left", padx=(5, 0))
    dialog_height_entry = tk.Entry(dialog_geometry_frame, textvariable=dialog_height_var, width=5)
    dialog_height_entry.pack(side="left")
    dialog_height_entry.bind("<Button-3>", show_context_menu)
    # Buttons
    button_frame = tk.Frame(container)
    button_frame.pack(fill="x", pady=5)
    cancel_button = tk.Button(
        button_frame,
        text="Cancel",
        command=cancel,
        padx=20,
        pady=5,
        fg="white",
        bg="grey",
        activebackground="#606060",
        activeforeground="white",
        relief=tk.RAISED,
        borderwidth=2,
    )
    cancel_button.pack(side=tk.LEFT, fill="x", padx=(0, 2), pady=(10, 0), expand=False)
    save_button = tk.Button(
        button_frame,
        text="Add",
        command=save_profile,
        padx=5,
        pady=5,
        fg="white",
        bg="#08872a",
        activebackground="#076921",
        activeforeground="white",
        relief=tk.RAISED,
        borderwidth=2,
    )
    save_button.pack(side=tk.LEFT, fill="x", padx=(2, 0), pady=(10, 0), expand=True)
    # Error message
    error_label = tk.Label(container, text="", bg="red", fg="white")
    # Make the window resizable
    add_window.columnconfigure(0, weight=1)
    add_window.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(0, weight=1)
    # Configure resizing for frames and text widgets
    name_frame.columnconfigure(1, weight=1)
    ssid_frame.columnconfigure(1, weight=1)
    url_frame.columnconfigure(1, weight=1)
    internet_frame.columnconfigure(1, weight=1)
    payload_frame.columnconfigure(0, weight=1)
    headers_frame.columnconfigure(0, weight=1)
    check_frame.columnconfigure(1, weight=1)
    dialog_geometry_frame.columnconfigure(1, weight=1)
    button_frame.columnconfigure(1, weight=1)
    # Calculate and set the minimum height based on the current height of the items
    add_window.update_idletasks()
    min_height = add_window.winfo_height()
    default_width = 400
    add_window.geometry(f"{default_width}x{min_height}")
    add_window.minsize(default_width, min_height)
    # Center the add_window on the root window
    root.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() // 2) - (default_width // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (min_height // 2)
    add_window.geometry(f"+{x}+{y}")

def remove_selected_profile():
    selected_index = listbox.curselection()
    if not selected_index:
        return
    selected_index = selected_index[0]
    selected_profile = profiles[selected_index]
    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the profile '{selected_profile['name']}'?"):
        profiles.pop(selected_index)
        config["profiles"] = profiles
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        listbox.delete(selected_index)
        profile_details.config(state=tk.NORMAL)
        profile_details.delete("1.0", tk.END)
        profile_details.config(state=tk.DISABLED)
        profile_name.config(text="Selected Profile: ")

# Add buttons under the listbox
button_frame = tk.Frame(profiles_frame)
button_frame.pack(side=tk.LEFT, pady=(0,5))

add_button = tk.Button(
    button_frame,
    text="Add new",
    command=add_new_profile,
    padx=5,
    pady=0,
    fg="white",
    bg="#08872a",
    activebackground="#076921",
    activeforeground="white",
    relief=tk.RAISED,
    borderwidth=2,
)
add_button.pack(side=tk.LEFT, padx=(0,5))

remove_button = tk.Button(
    button_frame,
    text="Remove",
    command=remove_selected_profile,
    padx=5,
    pady=0,
    fg="white",
    bg="grey",
    activebackground="#606060",
    activeforeground="white",
    relief=tk.RAISED,
    borderwidth=2,
)
remove_button.pack(side=tk.LEFT, padx=0)
for profile in profiles:
    listbox.insert(tk.END, profile['name'])
listbox.bind('<Delete>', lambda event: remove_selected_profile())
# Create a vertical scrollbar for the listbox
scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
listbox.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=listbox.yview)
# Bind the listbox selection event to update and refresh the profile details
listbox.bind('<<ListboxSelect>>', lambda event: (update_profile_details(event), refresh_profile_details()))
listbox.bind('<Return>', run_profile)  # Run the selected profile when the Enter key is pressed
# Create a frame for displaying profile details
details_frame = tk.Frame(root)
details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
# Create a frame for the profile name and the Refresh button
profile_name_frame = tk.Frame(details_frame)
profile_name_frame.pack(fill="x", pady=(0, 5))
# Create the label for the selected profile name
profile_name = tk.Label(profile_name_frame, text="Selected Profile: ", anchor="w")
profile_name.pack(side=tk.LEFT)
# Create a Text widget for displaying profile details with a fixed height and scrollbars
profile_details = Text(details_frame, wrap=tk.WORD, height=10, state=tk.DISABLED, exportselection=False)
profile_details.pack(fill="both", expand=True)
# Create a vertical scrollbar for the profile details Text widget
profile_scrollbar = Scrollbar(profile_details, command=profile_details.yview)
profile_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
# Link the profile details Text widget and scrollbar
profile_details.config(yscrollcommand=profile_scrollbar.set)
# Function to exit the application
def on_closing():
    root.destroy()
    os._exit(0)

root.protocol("WM_DELETE_WINDOW", on_closing)

# Create the "Refresh" button within the profile name frame
refresh_button = tk.Button(
    profile_name_frame,
    text="Refresh",
    command=refresh_profile_details,
    padx=5,
    pady=0,
    fg="white",
    bg="grey",
    activebackground="#606060",
    activeforeground="white",
    relief=tk.RAISED,
    borderwidth=2,
)
refresh_button.pack(side=tk.RIGHT)

# Create the "Github" button that redirects to github.com
github_button = tk.Button(
    profile_name_frame,
    text="Github",
    command=lambda: os.startfile(github_link),
    padx=5,
    pady=0,
    fg="white",
    bg="lightskyblue4",
    activebackground="lightsteelblue4",
    activeforeground="white",
    relief=tk.RAISED,
    borderwidth=2,
)
github_button.pack(side=tk.RIGHT, padx=(0, 5))

# Create the "Start with Windows" checkbox (starts in Auto mode in the background)
autostart_var = tk.BooleanVar(value=is_autostart_enabled())
autostart_check = tk.Checkbutton(
    profile_name_frame,
    text="Start with Windows (Auto)",
    variable=autostart_var,
    command=toggle_autostart,
)
autostart_check.pack(side=tk.RIGHT, padx=(0, 5))

# Create the "Config" button
config_button = tk.Button(
    details_frame,
    text="Config",
    command=open_config,
    padx=30,
    pady=10,
    fg="white",
    bg="grey",
    activebackground="#606060",
    activeforeground="white",
    relief=tk.RAISED,
    borderwidth=2,
)
config_button.pack(side=tk.LEFT, fill="x", padx=(0, 2), pady=(10, 0), expand=False)

# Create the "Auto" button (detects the profile from the connected network)
auto_button = tk.Button(
    details_frame,
    text="Auto",
    command=run_auto,
    padx=30,
    pady=10,
    fg="white",
    bg="lightskyblue4",
    activebackground="lightsteelblue4",
    activeforeground="white",
    relief=tk.RAISED,
    borderwidth=2,
)
auto_button.pack(side=tk.LEFT, fill="x", padx=2, pady=(10, 0), expand=False)

# Create the "Run" button
run_button = tk.Button(
    details_frame,
    text="Run",
    command=run_profile,
    padx=10,
    pady=10,
    fg="white",
    bg="#08872a",
    activebackground="#076921",
    activeforeground="white",
    relief=tk.RAISED,
    borderwidth=2,
)

run_button.pack(side=tk.LEFT, fill="x", padx=(2, 0), pady=(10, 0), expand=True)
# Configure weights for horizontal stretching
details_frame.pack_propagate(False)
# Start with no profile selected
selected_profile = None

# Select the first profile by default
if profiles:
    selected_profile = profiles[0]
    listbox.select_set(0)  # Highlight the first item in the list
    update_profile_details(None)  # Update the profile details

if auto_mode:
    root.destroy()
else:
    root.mainloop()

# Load the given profile's data into the variables used by the network checker
def apply_profile(profile):
    global selected_profile, payload, url, internet_check_url, ssid, check_every_second, dialog_geometry, headers, expected_ssid, expected_ssid_lower
    selected_profile = profile
    payload = profile.get('payload')
    url = profile.get('url', "")
    internet_check_url = profile.get('internet_check_url', "")
    ssid = profile.get('ssid', "") or "Ethernet"
    check_every_second = profile.get('check_every_second', 600)
    dialog_geometry = profile.get('dialog_geometry', {"width": 1024, "height": 500})
    headers = profile.get('headers', "")
    expected_ssid = ssid
    expected_ssid_lower = expected_ssid.lower()

# Access the selected profile's data after the window closes
if auto_mode:
    # The profile is chosen later, based on the connected network
    selected_profile = None
    expected_ssid = expected_ssid_lower = None
    check_every_second = 600
    dialog_geometry = profiles[0].get('dialog_geometry', {"width": 1024, "height": 500}) if profiles else {"width": 1024, "height": 500}
elif selected_profile:
    apply_profile(selected_profile)

# Function to send the request
def send_request():
    session = requests.Session()
    requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
    response = session.post(url, json.dumps(payload), headers=headers, allow_redirects=True, verify=False, timeout=10)
    response.raise_for_status()
    return response

# Function to check if internet is available
def is_internet_available():
    try:
        parsed = urlparse(internet_check_url)
        if not parsed.scheme:
            test_urls = [f"https://{internet_check_url}", f"http://{internet_check_url}"]
        else:
            test_urls = [internet_check_url]
        for url in test_urls:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return True
            except requests.RequestException as e:
                return False
        return False
    except Exception as e:
        return False
    
# Function to get all currently connected networks (for Windows)
# Returns (ethernet_connected, wifi_ssid, wifi_error)
def get_connected_networks():
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    ethernet_connected = False
    try:
        ethernet_output = subprocess.check_output(["netsh", "interface", "show", "interface"], startupinfo=startupinfo).decode("utf-8", errors="replace")
        for line in ethernet_output.splitlines():
            # Columns: Admin State, State, Type, Interface Name
            parts = line.split(None, 3)
            if len(parts) == 4 and parts[1] == "Connected" and "Ethernet" in parts[3] and not parts[3].startswith("vEthernet"):
                ethernet_connected = True  # vEthernet adapters (Hyper-V / WSL) are virtual and always "Connected"
                break
    except subprocess.CalledProcessError:
        pass
    wifi_ssid = None
    wifi_error = None
    try:
        wifi_output = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], startupinfo=startupinfo).decode("utf-8", errors="replace")
        match = re.search(r"^\s*SSID\s*:\s*(.+)$", wifi_output, re.MULTILINE)
        if match:
            wifi_ssid = match.group(1).strip()
    except subprocess.CalledProcessError as e:
        wifi_error = str(e)
    return ethernet_connected, wifi_ssid, wifi_error

# Function to get the currently connected SSID using system commands (for Windows)
def get_connected_network():
    ethernet_connected, wifi_ssid, wifi_error = get_connected_networks()
    if ethernet_connected:
        return "Ethernet"
    if wifi_error:
        return "Error: " + wifi_error
    return wifi_ssid or False

# Check whether the login portal's host can be reached from the current network
def is_portal_reachable(portal_url, timeout=3):
    parsed = urlparse(portal_url)
    if not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=timeout):
            return True
    except OSError:
        return False

# Reload profiles from config.json, so edits are picked up without restarting (auto mode)
def load_profiles():
    global profiles
    try:
        with open("config.json", "r") as f:
            profiles = json.load(f).get("profiles", [])
    except (OSError, json.JSONDecodeError):
        pass  # Keep using the last valid profiles
    return profiles

# Sleep for the given seconds, but check the connected networks every few seconds and return early
# if they changed (e.g. switching between Ethernet and Wi-Fi), so the new network is handled right away (auto mode)
NETWORK_POLL_SECONDS = 5
def wait_or_network_change(seconds, networks):
    deadline = time.time() + seconds
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return False
        time.sleep(min(NETWORK_POLL_SECONDS, remaining))
        ethernet_connected, wifi_ssid, _ = get_connected_networks()
        if (ethernet_connected, wifi_ssid) != tuple(networks):
            add_to_log("Network change detected. Checking again now...")
            return True

# Find the profile that belongs to the currently connected network (auto mode)
# Returns (profile, connected_network_name) or (None, None)
def find_matching_profile(ethernet_connected, wifi_ssid):
    # Wi-Fi: match by SSID. If several profiles share the SSID, prefer one whose portal is reachable.
    if wifi_ssid:
        candidates = [p for p in profiles if p.get('ssid', "").strip().lower() == wifi_ssid.lower()]
        if len(candidates) > 1:
            reachable = [p for p in candidates if is_portal_reachable(p.get('url', ""))]
            candidates = reachable or candidates
        if candidates:
            return candidates[0], wifi_ssid
    # Ethernet: profiles have no SSID, so use the one whose login portal is reachable on this network
    if ethernet_connected:
        for p in profiles:
            if not p.get('ssid') and is_portal_reachable(p.get('url', "")):
                return p, "Ethernet"
    return None, None
    
# Is connected to wifi
def is_connected_to_wifi():
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        wifi_output = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], startupinfo=startupinfo).decode("utf-8")
        wifi_lines = wifi_output.split("\n")
        for line in wifi_lines:
            if "SSID" in line:
                return True
        else:
            return False
    except subprocess.CalledProcessError:
        return False
    
# Function to exit the application
def exit_application(icon, item):
    icon.stop()
    os._exit(0)

# Queue to store log messages
log_messages = deque(maxlen=15)
log_dialog = None
log_text = None
log_dialog_open = False
# Get the dialog geometry from the config file
width = dialog_geometry["width"]
height = dialog_geometry["height"]
x = 0
y = 0

# Function to update the window's position and size variables
def update_window_geometry(event):
    global x, y, width, height
    x, y = event.x, event.y
    width, height = event.width, event.height

# Title of the log dialog, with the profile currently in use
def get_log_title():
    if auto_mode:
        name = selected_profile['name'] if selected_profile else "waiting for a known network"
        return f"Log Messages (Auto: {name})"
    return f"Log Messages ({selected_profile['name']})"

# Function to show the log dialog with the currently selected profile name
def show_log_dialog():
    global log_dialog, log_text, log_dialog_open, successful_logins_label
    if not log_dialog_open:
        log_dialog_open = True
        if log_dialog:
            log_dialog.title(get_log_title())  # Update title with profile name
            log_dialog.deiconify()
            update_log()
        else:
            log_dialog = tk.Tk()
            log_dialog.title(get_log_title())  # Update title with profile name
            log_text = tk.Text(log_dialog)
            log_frame = tk.Frame(log_dialog)
            log_frame.pack(fill=tk.BOTH, expand=True)
            log_text = tk.Text(log_frame, wrap=tk.WORD)
            log_text.pack(fill=tk.BOTH, expand=True)
            log_dialog.minsize(200, 120)
            # Create label for successful logins count
            successful_logins_label = tk.Label(log_dialog, text=f"Successful Logins: {successful_logins_count}", anchor="w", padx=5)
            successful_logins_label.place(x=0, rely=1.0, anchor=tk.SW, bordermode=tk.OUTSIDE)
            # Define tags for different styles
            log_text.tag_configure("green", foreground="green")
            log_text.tag_configure("red", foreground="red")
            log_text.tag_configure("bold_green", foreground="green", font=("Courier New", 10, "bold"))
            log_text.tag_configure("bold_red", foreground="red", font=("Courier New", 10, "bold"))
            update_log()
            log_dialog.protocol("WM_DELETE_WINDOW", hide_log_dialog)
            center_window(log_dialog, width, height)
            log_dialog.bind("<Configure>", update_window_geometry)
            log_dialog.mainloop()
    else:
        hide_log_dialog()

# Function to hide the log dialog
def hide_log_dialog():
    global log_dialog, log_text, log_dialog_open
    log_dialog_open = False
    if log_dialog:
        log_dialog.withdraw()
        log_dialog = None
        log_text = None

# Function to get the last log messages
def get_last_log_messages():
    global log_messages
    return list(log_messages)

# Function to update the log
def update_log():
    if log_text:
        log_text.delete(1.0, tk.END)
        for message in get_last_log_messages():
            log_text.insert(tk.END, message + "\n")

# Add a global variable to keep track of successful logins count
successful_logins_count = 0
successful_logins_label = None

# Function to add a message to the log
def add_to_log(message, style=None):
    global log_messages, successful_logins_count
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    log_messages.append((f"({timestamp}) {message}", style))
    update_log()  # Update the log window

# Function to update the log
def update_log():
    if log_text:
        if auto_mode and log_dialog:
            log_dialog.title(get_log_title())  # The profile can change in auto mode
        log_text.delete(1.0, tk.END)
        for message, style in get_last_log_messages():
            if style:
                log_text.insert(tk.END, message + "\n", style)
            else:
                log_text.insert(tk.END, message + "\n")
        update_successful_logins_count()  # Update the successful logins count

# Function to update the successful logins count label
def update_successful_logins_count():
    if log_dialog:
        if successful_logins_label:
            successful_logins_label.config(text=f"Successful Logins: {successful_logins_count}")

# Function to add a message to the log file (txt)
def save_to_file(message):
    # Get the current date and time
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    # Format the message with the timestamp
    formatted_message = f"({timestamp}) {message}\n"
    # Open the file in append mode and write the formatted message with utf-8 encoding
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(formatted_message)

# Create the system tray icon
def create_system_tray_icon():
    image = Image.open("icon.ico")
    menu = pystray.Menu(
        pystray.MenuItem('Show Log', show_log_dialog, default=True),
        pystray.MenuItem('Exit', exit_application)
    )
    icon = pystray.Icon("my_icon", image, "HotspotAutoLogin", menu)
    icon.run()

# Function to check network status
running = True
errorcount = 0
request_success = False
request_errorcount = 0
sleepcount = check_every_second
connected_ssid_lower = None
last_auto_message = None
def check_network_status():
    global running, errorcount, sleepcount, connected_ssid_lower, ssid, response, request_success, request_errorcount, successful_logins_count, last_auto_message, selected_profile
    # In auto mode the program keeps running (e.g. started with Windows), so it never exits on errors
    while running and (auto_mode or errorcount < 10):
        if auto_mode:
            if errorcount >= 10:
                sleepcount = 300
                message = "Too many errors. Pausing for {} seconds before trying again...".format(str(sleepcount))
                add_to_log(message, "bold_red")
                save_to_file(message)
                errorcount = 0
                time.sleep(sleepcount)
                continue
            # Detect which profile belongs to the connected network
            load_profiles()
            ethernet_connected, wifi_ssid, wifi_error = get_connected_networks()
            detected_profile, connected_ssid = find_matching_profile(ethernet_connected, wifi_ssid)
            if detected_profile is None:
                sleepcount = 30
                if wifi_error and not ethernet_connected:
                    message = "{}\nFailed to get SSID. If location services are disabled, please enable them. Checking again in {} seconds...".format(wifi_error, str(sleepcount))
                elif wifi_ssid or ethernet_connected:
                    network = " and ".join(n for n in [wifi_ssid, "Ethernet" if ethernet_connected else None] if n)
                    message = "Connected to {}, which does not match any profile. Waiting for a known network...".format(network)
                else:
                    message = "Not connected to any network. Waiting for a known network..."
                # Only log when the situation changes, so the log isn't flooded while idle
                if message != last_auto_message:
                    add_to_log(message, "red" if wifi_error else None)
                    last_auto_message = message
                selected_profile = None  # So the next known network is logged as a new detection
                wait_or_network_change(sleepcount, (ethernet_connected, wifi_ssid))
                continue
            last_auto_message = None
            if selected_profile is None or selected_profile.get('name') != detected_profile.get('name'):
                errorcount = 0
                request_success = False
                request_errorcount = 0
                apply_profile(detected_profile)
                message = "Detected network {}. Using profile '{}'.".format(connected_ssid, detected_profile.get('name'))
                add_to_log(message, "bold_green")
                save_to_file(message)
            else:
                apply_profile(detected_profile)  # Pick up config.json edits
        else:
            connected_ssid = get_connected_network()
        if isinstance(connected_ssid, str) and "error" in connected_ssid.lower():
            sleepcount = 60
            message = "{}\nFailed to get SSID. If location services are disabled, please enable them. Retrying in {} seconds...".format(connected_ssid, str(sleepcount))
            add_to_log(message, "bold_red")
            errorcount += 1
            time.sleep(sleepcount)
            continue
        if (connected_ssid):
            connected_ssid_lower = connected_ssid.lower()
        if (connected_ssid) and ((connected_ssid_lower == expected_ssid_lower)):
            # Not in auto mode: there, Wi-Fi may be a separate network the user wants to keep
            if not auto_mode and is_connected_to_wifi() and (connected_ssid == "Ethernet" and expected_ssid == "Ethernet"):
                message = "You are both connected to Wi-Fi and Ethernet. Disconnecting from Wi-Fi and continuing with Ethernet..."
                add_to_log(message)
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.check_output(['netsh', 'wlan', 'disconnect', 'interface=' + "Wi-Fi"], startupinfo=startupinfo).decode("utf-8")
                time.sleep(5)
            if (is_internet_available()):
                sleepcount = check_every_second
                request_success = False
                request_errorcount = 0
                message = "Connected to {} and internet connection is available. Checking again in {} seconds...".format(connected_ssid, str(sleepcount))
                errorcount = 0
                add_to_log(message, "bold_green")
            elif request_success and request_errorcount < 3:
                # If the request was successful but there is still no internet connection, wait for a few seconds and try again
                sleepcount = 60
                request_errorcount += 1
                message = "Even the request was successful, there is still no internet connection. There might be a problem with your network. If you are using a VPN, please check your VPN connection. Giving it some time and checking again in {} seconds... (Request Again: {}/3)".format(str(sleepcount), str(request_errorcount))
                add_to_log(message, "red")
                save_to_file(message)
            else:
                sleepcount = 5
                message = "Connected to {} but internet is down. Sending the request in {} seconds...".format(connected_ssid, str(sleepcount))
                add_to_log(message)
                save_to_file(message)
                time.sleep(sleepcount)
                try:                        
                    # Function to send request
                    response = send_request()
                    if response.ok:
                        errorcount = 0
                        sleepcount = 15
                        request_success = True
                        request_errorcount = 0
                        successful_logins_count += 1
                        message = "Request was successful. Checking the internet connection in {} seconds...".format(str(sleepcount))
                        add_to_log(message, "green")
                        save_to_file(message)
                except requests.exceptions.RequestException as e:
                    errorcount += 1
                    sleepcount = 3
                    request_success = False
                    if isinstance(e, requests.exceptions.HTTPError):
                        # Handle HTTP errors with different messages for different status codes
                        status_code = e.response.status_code
                        if status_code == 400:
                            message = "Request failed with 400 Bad Request error. Please check your payload and URL. Trying to reconnect to the network... (Errors: {}/10)".format(errorcount)
                        elif status_code == 404:
                            message = "Request failed with 404 Not Found error. Trying to reconnect to the network... (Errors: {}/10)".format(errorcount)
                        elif status_code == 500:
                            message = "Request failed with 500 Internal Server Error. Trying to reconnect to the network... (Errors: {}/10)".format(errorcount)
                        elif status_code == 503:
                            message = "Request failed with 503 Service Unavailable error. Trying to reconnect to the network... (Errors: {}/10)".format(errorcount)
                        else:
                            message = "Request failed with HTTP error ({}). \nTrying to reconnect to the network... (Errors: {}/10)".format(status_code, errorcount)
                    else:
                        message = "Request failed with error: {}.\nIf you are using a VPN, please disable it for now. Trying to reconnect to the network... (Errors: {}/10)".format(e, errorcount)
                    add_to_log(message, "red")
                    save_to_file(message)
                    time.sleep(sleepcount)
                    # If the payload URL is not reachable, try to reconnect to the network
                    if connected_ssid == "Ethernet":
                        try:
                            # Disable and enable the Ethernet adapter
                            message = "Disconnecting from Ethernet..."
                            add_to_log(message)
                            subprocess.check_output(['ipconfig', '/release', "Ethernet"], shell=True, text=True)
                            time.sleep(5)
                            subprocess.check_output(['ipconfig', '/renew', "Ethernet"], shell=True, text=True)
                            message = "Connected to Ethernet. Running the script again..."
                            add_to_log(message)
                            time.sleep(5)
                        except Exception as e:
                            errorcount += 1
                            message = "Failed to reconnect to Ethernet: {} (Errors: {}/10)".format(e, errorcount)
                            add_to_log(message, "red")
                            save_to_file(message)
                    else:
                        try:
                            # Disconnect and reconnect to the Wi-Fi network
                            message = "Disconnecting from {}...".format(ssid)
                            add_to_log(message)
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            subprocess.check_output(['netsh', 'wlan', 'disconnect', 'interface=' + "Wi-Fi"], startupinfo=startupinfo).decode("utf-8")
                            time.sleep(5)
                            subprocess.check_output(['netsh', 'wlan', 'connect', 'name=' + ssid], startupinfo=startupinfo).decode("utf-8")
                            message = "Connected to {}. Running the script again...".format(ssid)
                            add_to_log(message ,"green")
                            time.sleep(8)
                        except Exception as e:
                            errorcount += 1 
                            message = "Failed to reconnect to {}: {} (Errors: {}/10)".format(ssid, e, errorcount)
                            add_to_log(message, "red")
                            save_to_file(message)
                    continue
        else:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            wifi_output = subprocess.check_output(["netsh", "interface", "show", "interface"], startupinfo=startupinfo).decode("utf-8")
            wifi_lines = wifi_output.split("\n")
            wifi_enabled = False
            for line in wifi_lines:
                if "Wi-Fi" in line:
                    if "Enabled" in line:
                        wifi_enabled = True
                        break
            if connected_ssid == "Ethernet":
                sleepcount = 30
                message = "If you want to connect to {}, please unplug your ethernet cable or disconnect from {}. Checking again in {} seconds...".format(expected_ssid, connected_ssid, str(sleepcount))
                errorcount = 0
                add_to_log(message, "red")
            elif expected_ssid == "Ethernet":
                sleepcount = 30
                message = "Looks like your ethernet cable is not plugged in. Please plug in your ethernet cable. Checking again in {} seconds...".format(str(sleepcount))
                errorcount = 0
                add_to_log(message, "red")
            elif wifi_enabled:
                if (connected_ssid):
                    sleepcount = 10
                    message = "You are connected to {}, but you need to be connected to {}. Trying to connect {}...".format(connected_ssid, expected_ssid, expected_ssid)
                    add_to_log(message)
                else:
                    sleepcount = 10
                    message = "You are not connected to {}. Trying to connect {}...".format(expected_ssid, expected_ssid)
                    add_to_log(message, "red") 
                try:
                    result = subprocess.run(
                        ['netsh', 'wlan', 'connect', 'name=' + expected_ssid],
                        capture_output=True,
                        text=True,
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if result.returncode != 0:
                        if result.returncode == 1:
                            sleepcount = 20
                            message = "Could not find a Wi-Fi network with SSID: {}. If your Wi-Fi is disabled, please enable it. Checking again in {} seconds...".format(expected_ssid, str(sleepcount))
                            add_to_log(message ,"red")
                        else:
                            raise subprocess.CalledProcessError(result.returncode, result.args, result.stderr)
                    else:
                        message = "Connected to {}. Running the script again in {} seconds...".format(expected_ssid, str(sleepcount))
                        add_to_log(message, "green")
                except (subprocess.CalledProcessError, ValueError) as e:
                    errorcount += 1
                    sleepcount = 15
                    if isinstance(e, subprocess.CalledProcessError):
                        message = "Failed to connect to {}: {}. Trying again in {} seconds... (Errors:{}/10)".format(expected_ssid, e, str(sleepcount), errorcount)
                    else:
                        message = str(e) + ". Trying again in {} seconds... (Errors:{}/10)".format(str(sleepcount), errorcount)
                    add_to_log(message, "red")
                    save_to_file(message)
            elif wifi_enabled == False:
                sleepcount = 30
                errorcount += 1
                message = "You are not connected to Ethernet and your Wi-Fi is disabled. Please enable your Wi-Fi or plug in your ethernet cable. Checking again in {} seconds... (Errors: {}/10)".format(str(sleepcount), errorcount)
                add_to_log(message, "red")
                save_to_file(message)
            else:
                sleepcount = 30
                errorcount += 1
                message = "Something went wrong. Please check your Wi-Fi or Ethernet connection. Checking again in {} seconds... (Errors: {}/10)".format(str(sleepcount), errorcount)
                save_to_file(message)
                add_to_log(message, "red")
        if auto_mode:
            wait_or_network_change(sleepcount, (ethernet_connected, wifi_ssid))
        else:
            time.sleep(sleepcount)  # Sleep ... seconds before trying again
    message = "Maximum error count reached. Exiting in 5 seconds..."
    add_to_log(message, "bold_red")
    save_to_file(message)
    time.sleep(5)
    running = False
    os._exit(0)

if __name__ == '__main__':
    # Create a thread for the system tray icon
    tray_thread = threading.Thread(target=create_system_tray_icon)
    tray_thread.start()
    # Open Log Messages at startup (unless started in the background, e.g. with Windows)
    if not args.background:
        open_log_messages_startup = threading.Thread(target=show_log_dialog)
        open_log_messages_startup.start()
    # Start the network status checking in the main thread
    check_network_status()
    # Wait for all threads to finish
    tray_thread.join()
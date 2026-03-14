Dưới đây là file markdown đã được cập nhật thêm phần **Tech Stack** và các hướng dẫn cụ thể cho việc triển khai bằng **Tkinter**.

```markdown
# UI Design & Development Prompt: Smartfix - Central Command Dashboard (Tkinter Version)

**Title:** Design and Develop the "Smartfix - Central Command" Desktop Application using Tkinter.

## 1. Tech Stack (Công nghệ sử dụng)

*   **Language:** Python 3.x
*   **GUI Framework:** `tkinter` (Standard Python interface to the Tcl/Tk GUI toolkit).
*   **Style/Theme:** `ttk` (Themed Tkinter) for modern native widgets, combined with `tkinter.canvas` for custom layouts.
*   **Image Processing:** `Pillow` (PIL - Python Imaging Library) for handling image uploads and display (JPG, PNG resizing).
*   **State Management:** Python dictionaries/classes to handle intersection data and UI states.

## 2. Overall Layout (Tkinter Geometry)

*   **Root Window:** 
    *   Title: "Smartfix - Central Command"
    *   Geometry: Full screen or fixed large resolution (e.g., "1366x768").
    *   Background: Dark gray color (e.g., `#2c3e50` or hex equivalent).
*   **Main Container:** Use `ttk.PanedWindow` or `Frame` with `grid` layout system.
    *   Column 0 (Left): Weight 7 (70% width).
    *   Column 1 (Right): Weight 3 (30% width). 

## 3. Left Panel: Camera Upload Grid (Implementation Details)

*   **Widget:** A main Frame containing a 2x2 Grid.
*   **Grid Items (4 slots):**
    *   Each item is a Frame containing a Label or Canvas.
    *   **Placeholder State:** Display a Rectangle with dashed border (using Canvas) and an "Upload" icon/text.
    *   **Interaction:** Bind `<Button-1>` (Left Click) to each frame to trigger a file dialog (`filedialog.askopenfilename`).
    *   **Image Display:** When an image is selected, use `PIL.ImageTk.PhotoImage` to resize and display the image on the Canvas/Label.
*   **Badges:** Use `Label` widgets with specific background colors positioned at the top-left corner of each grid item.

## 4. Right Panel: Control Area (Implementation Details)

### Box 1: Control Area (Dropdown)
*   **Widget:** `ttk.Combobox`.
*   **Values:** ["Intersection 1 - Le Hong Phong", "Intersection 2 - Nguyen Trai", "Intersection 3 - Le Loi"].
*   **State:** "readonly".
*   **Event Binding:** Bind `<<ComboboxSelected>>` event to trigger the `handle_intersection_change` function (Reset logic).

### Box 2: Statistics
*   **Water Level:** Use `ttk.Progressbar` (mode='determinate' or vertical) or a custom Canvas rectangle.
*   **Total Cars:** A large `Label` with a bold font (e.g., Helvetica, 24, bold).
*   **Status:** Two Labels for "Accident" and "Emergency".

### Box 3: System Activation (Start Button) - *【NEW】*
*   **Widget:** `Button` or `ttk.Button`.
*   **Styling:** 
    *   **Disabled:** Grey background, `state="disabled"`.
    *   **Enabled:** Green background (`bg="green"`), active on hover.
*   **Logic:** 
    *   Track the number of uploaded images. When `uploaded_count == 4`, set button state to `normal`.
    *   **Command:** Calls the backend function to process images (mock data or AI integration).

### Box 4 & 5: Controls
*   **Traffic Light:** Standard `Button` widgets.
*   **Operation Mode:** `ttk.Checkbutton` or a styled Button acting as a toggle.

## 5. UX Behavior Description (Python Logic)

1.  **Initialization:**
    *   Load UI.
    *   Button "START" is disabled (`btn_start.config(state="disabled")`).

2.  **Image Upload Handling:**
    *   Create a list `image_refs = [None, None, None, None]`.
    *   When a user uploads an image to slot *i*: update `image_refs[i]`.
    *   Check condition: If all items in `image_refs` are not `None`, enable the START button.

3.  **Process Flow (On "START" Click):**
    *   Show loading indicator (optional).
    *   Run processing logic.
    *   Update Statistics Labels with results.

4.  **Reset Logic (On Dropdown Change):**
    *   Loop through the 4 image slots and reset them to the placeholder image/text.
    *   Clear `image_refs`.
    *   Reset Stats labels to "Total: 0", "Accident: No".
    *   Disable the START button again.

## 6. Code Snippet Structure (Suggestion)

```python
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

class SmartFixDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Smartfix - Central Command")
        # Setup grid layout
        # Initialize variables
        
    def setup_left_panel(self):
        # Create 2x2 grid for uploads
        pass

    def setup_right_panel(self):
        # Create Control, Stats, Buttons
        pass

    def upload_image(self, slot_index):
        # Handle file dialog and image display
        # Check if all 4 images are uploaded -> Enable Start Button
        pass

    def start_processing(self):
        # Handle the logic when START is clicked
        pass

    def reset_dashboard(self, event):
        # Handle logic when dropdown changes
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartFixDashboard(root)
    root.mainloop()
```
```
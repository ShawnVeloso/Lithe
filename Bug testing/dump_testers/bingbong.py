import time
import pyautogui

# Enable PyAutoGUI fail-safe: move mouse to top-left corner to abort immediately
pyautogui.FAILSAFE = True

def autoclicker(interval: float = 1.0) -> None:
    """
    Clicks the primary mouse button at a specified time interval (in seconds).
    
    To terminate execution, trigger the PyAutoGUI fail-safe by moving 
    the mouse cursor to any corner of the screen.
    """
    print(f"Autoclicker running. Interval: {interval}s. Drag mouse to screen corner to kill.")
    try:
        while True:
            pyautogui.click()
            time.sleep(interval)
    except pyautogui.FailSafeException:
        print("Autoclicker aborted via fail-safe.")

if __name__ == "__main__":
    autoclicker(1.0)

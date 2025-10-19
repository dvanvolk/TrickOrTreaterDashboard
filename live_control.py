def enable_live_status():
    # Code to enable live status and show the counter
    print("Live status enabled. Counter is now visible.")

def disable_live_status():
    # Code to disable live status and hide the counter
    print("Live status disabled. Counter is now hidden.")

def toggle_live_status(current_status):
    if current_status:
        disable_live_status()
        return False
    else:
        enable_live_status()
        return True

# Example usage
if __name__ == "__main__":
    live_status = False  # Initial status
    live_status = toggle_live_status(live_status)  # Toggle the live status
    live_status = toggle_live_status(live_status)  # Toggle again to disable
# Global variable to track live status
_live_status = False

def is_live():
    """Return the current live status"""
    return _live_status

def set_live(status):
    """Set the live status"""
    global _live_status
    _live_status = status
    if status:
        print("Live status enabled. Counter is now visible.")
    else:
        print("Live status disabled. Counter is now hidden.")

def toggle_live():
    """Toggle the live status and return the new status"""
    global _live_status
    _live_status = not _live_status
    if _live_status:
        print("Live status enabled. Counter is now visible.")
    else:
        print("Live status disabled. Counter is now hidden.")
    return _live_status

# Example usage
if __name__ == "__main__":
    print(f"Initial status: {is_live()}")
    toggle_live()
    print(f"After toggle: {is_live()}")
    toggle_live()
    print(f"After second toggle: {is_live()}")
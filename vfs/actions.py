"""Shared queue of drive actions."""

# COLLECT AND CLEAR DRIVE ACTIONS [

class DriveActionsList:
    actions = []
    
    # INITIALIZE DRIVE ACTIONS LIST [
    def __init__(self):
        pass
    # INITIALIZE DRIVE ACTIONS LIST ]
    # APPEND PENDING WORK OR FILE OPERATIONS [
    def append(self, action):
        self.actions.append(action)
    # APPEND PENDING WORK OR FILE OPERATIONS ]
    # CLEAR DRIVE ACTIONS LIST [
    def clear(self):
        self.actions.clear()
    # CLEAR DRIVE ACTIONS LIST ]

# COLLECT AND CLEAR DRIVE ACTIONS ]

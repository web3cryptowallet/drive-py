"""Shared queue of drive actions."""

# COLLECT AND CLEAR DRIVE ACTIONS [

class DriveActionsList:
    actions = []
    
    def __init__(self):
        pass

    def append(self, action):
        self.actions.append(action)

    def clear(self):
        self.actions.clear()

# COLLECT AND CLEAR DRIVE ACTIONS ]

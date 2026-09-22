"""Path normalization and size formatting."""

# IMPORT PATH NORMALIZATION AND SIZE FORMATTING DEPENDENCIES [

from itertools import islice

# IMPORT PATH NORMALIZATION AND SIZE FORMATTING DEPENDENCIES ]
# FORMAT BYTE COUNTS FOR DISPLAY [

def format_size(size, type):
    if size is None:
        return "N/A"

    units = ["bytes", "KB", "MB", "GB", "TB"] if type == 0 else ["", "KB", "MB", "GB", "TB"]

    size = float(size)

    for unit in units:
        if size < 1024:
            return f"{round(size):3d} {unit}"
        size /= 1024

    return f"{round(size):3d} PB"

# FORMAT BYTE COUNTS FOR DISPLAY ]
# NORMALIZE VIRTUAL PATH COMPONENTS [

def normalize_path(path):
    parts = path.replace("//", "/").lstrip("/").rstrip("/").split("/")

    path = "/".join(parts)

    return (path, parts) 

# NORMALIZE VIRTUAL PATH COMPONENTS ]
# GROUP ITERABLE ITEMS INTO BATCHES [

def batched(iterable, size):
    it = iter(iterable)
    while batch := list(islice(it, size)):
        yield batch

# GROUP ITERABLE ITEMS INTO BATCHES ]

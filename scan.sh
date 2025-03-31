#!/bin/bash

# Function to convert bytes to human readable format
convert_size() {
    local bytes=$1
    if [ $bytes -ge 1099511627776 ]; then
        echo "$(bc <<< "scale=2; $bytes/1099511627776") TB"
    elif [ $bytes -ge 1073741824 ]; then
        echo "$(bc <<< "scale=2; $bytes/1073741824") GB"
    elif [ $bytes -ge 1048576 ]; then
        echo "$(bc <<< "scale=2; $bytes/1048576") MB"
    else
        echo "$bytes Bytes"
    fi
}

# Initialize variables
LOGS_DIR=""
SCAN_PATHS=()
FILTER_DIRS=()

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i)
            FILTER_DIRS+=("$2")
            shift 2
            ;;
        *)
            if [ -z "$2" ]; then
                LOGS_DIR="$1"
            else
                SCAN_PATHS+=("$1")
            fi
            shift
            ;;
    esac
done

echo FILTER_DIRS: ${FILTER_DIRS[@]}
echo SCAN_PATHS: ${SCAN_PATHS[@]}
echo LOGS_DIR: $LOGS_DIR

# Check if we have at least 2 arguments (paths and logs directory)
if [ ${#SCAN_PATHS[@]} -lt 1 ] || [ -z "$LOGS_DIR" ]; then
    echo "Usage: $0 [-i filter_dir] path1 [path2 ...] logs_directory"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

# Initialize total size
total_size=0

# Build list of subdirectories from provided paths
SUBDIRS=()
for path in "${SCAN_PATHS[@]}"; do
    if [ -d "$path" ]; then
        # Add all immediate subdirectories
        for subdir in "$path"/*/; do
            if [ -d "$subdir" ]; then
                last_component=$(basename "$subdir")
                # Only add to SUBDIRS if no filters specified or if it matches a filter
                if [ ${#FILTER_DIRS[@]} -eq 0 ] || [[ " ${FILTER_DIRS[@]} " =~ " ${last_component} " ]]; then
                    SUBDIRS+=("$subdir")
                fi
            fi
        done
    fi
done

# Process each directory
for dir in "${SUBDIRS[@]}"; do
    # Get the last component of the path
    last_component=$(basename "$dir")
    
    # Run drive.py with -s flag and redirect output
    echo "Processing directory: $dir"
    ./drive.py -s "$dir" "$LOGS_DIR/$last_component"
    
    # Read and process the log file
    if [ -f "$LOGS_DIR/$last_component/llog-proc.sh" ]; then
        # Extract size from the llog-proc.sh file
        size=$(grep "src_size:" "$LOGS_DIR/$last_component/llog-proc.sh" | awk '{print $2}')
        if [ ! -z "$size" ]; then
            total_size=$((total_size + size))
            echo "Size for $last_component: $(convert_size $size)"
        fi
    fi
done

# Display total size
echo "----------------------------------------"
echo "Total size: $(convert_size $total_size)" 
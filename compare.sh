# Initialize variables
LOGS_DIR=""
SCAN_PATHS=()

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
#        -i)
#            FILTER_DIRS+=("$2")
#            shift 2
#            ;;
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

echo SCAN_PATHS: ${SCAN_PATHS[@]}
echo LOGS_DIR: $LOGS_DIR

# Check if we have at least 2 arguments (paths and logs directory)
if [ ${#SCAN_PATHS[@]} -lt 1 ] || [ -z "$LOGS_DIR" ]; then
    echo "Usage: $0 path [path ...] logs_directory"
    exit 1
fi

for path in ${SCAN_PATHS[@]}; do
    echo $path
done

FILES=()
for path in "${SCAN_PATHS[@]}"; do
    if [ -d "$path" ]; then
            # Add filtered dir
            # Add all immediate subdirectories
            for subdir in "$path"/*/; do
                FILE="${subdir}/llog-llogfiles.sh"
                if [ -f "$FILE" ]; then
                    FILES+=("$FILE")
                fi

#                if [ -d "$subdir" ]; then
#                    last_component=$(basename "$subdir")
                    # Only add to SUBDIRS if no filters specified or if it matches a filter
#                    if [ ${#FILTER_DIRS[@]} -eq 0 ] || [[ " ${FILTER_DIRS[@]} " =~ " ${last_component} " ]]; then
#                        SUBDIRS+=("$subdir")
#                        echo $subdir
#                    fi
#                fi
            done
        #fi
    fi
done

echo 777 ${FILES[@]}

CMD="./drive.py "
for file in "${FILES[@]}"; do
    echo $file
#    CMD+=" -f \"$file\"  "
    CMD+=" -f $file  "
done

CMD="$CMD $LOGS_DIR"
echo EXEC: $CMD

$CMD
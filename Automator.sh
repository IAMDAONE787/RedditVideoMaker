#!/bin/bash

# Log file path
LOG_FILE=~/RedditVideoMakerBot-master/logs/script_log.txt

# Project root and config for reading flags
PROJECT_ROOT=~/RedditVideoMakerBot-master
CONFIG_FILE="$PROJECT_ROOT/config.toml"

# Read offline_mode and offline_output_dir from config.toml (best-effort, optional)
OFFLINE_MODE=$(grep -E '^[[:space:]]*offline_mode[[:space:]]*=' "$CONFIG_FILE" 2>/dev/null | head -n1 | sed -E 's/.*=\s*//')
OFFLINE_OUTPUT_DIR=$(grep -E '^[[:space:]]*offline_output_dir[[:space:]]*=' "$CONFIG_FILE" 2>/dev/null | head -n1 | sed -E 's/.*=\s*"?(.*?)"?$/\1/')

if [[ -z "$OFFLINE_OUTPUT_DIR" ]]; then
  OFFLINE_OUTPUT_DIR="offline_results"
fi

# Function to log both to stdout and to a file
log() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "Script started."

# Sleep for a random amount of time between 2 minutes and 3 hours
 RANDOM_SLEEP=$((120 + RANDOM % 4800))  # Random time between 120 seconds (2 min) and 10800 seconds (1.4 hours)
 log "Sleeping for $RANDOM_SLEEP seconds."
 sleep $RANDOM_SLEEP


export PATH="$HOME/.local/bin:$HOME/bin:/usr/local/bin:/usr/bin:/bin"
export WORKON_HOME="$HOME/.virtualenvs"
export VIRTUALENVWRAPPER_PYTHON="$(which python3)"

cd /home/user/RedditVideoMakerBot-master

# Activate the first virtual environment for RedditVideoMakerBot
log "Activating the virtual environment for RedditVideoMakerBot."
source ~/RedditVideoMakerBot-master/venvDigger/bin/activate


#Run ElevenLabsKeyRotator
#python3 ~/RedditVideoMakerBot-master/elevenLabsKeyRotator.py 2>&1 | tee -a "$LOG_FILE"

sleep 60


# Run the Python script
log "Running main.py"
python3 ~/RedditVideoMakerBot-master/main.py 2>&1 | tee -a "$LOG_FILE"

# Sleep for 1 minute
log "Sleeping for 60 seconds."
sleep 60

# Find the latest created .mp4 file
log "Finding the latest .mp4 file in the results directory."
latest_file=$(ls -t ~/RedditVideoMakerBot-master/results/AmItheAsshole+relationship_advice+confession+tifu/*.mp4 | head -n 1)

if [[ -z "$latest_file" ]]; then
    log "No .mp4 files found! Exiting."
    deactivate  # Deactivate the virtual environment before exiting
    exit 1
else
    log "Found latest file: $latest_file"
fi

# Extract the file name without the .mp4 extension
filename_without_ext=$(basename "$latest_file" .mp4)
log "Extracted file name without extension: $filename_without_ext"

# Generate the word-by-word captions in the latest file with "_out"
log "Generating captions for $latest_file"
python3 ~/RedditVideoMakerBot-master/captionGen.py "$latest_file"  --font ~/RedditVideoMakerBot-master/fonts/Rubik-Black.ttf  2>&1 | tee -a "$LOG_FILE"

# Update the file path to add the "_out" at the end
latest_file="${latest_file%.mp4}_out.mp4"
log "Updated file name for the captioned version: $latest_file"

# If offline_mode is enabled, just copy the finished file and skip all uploads.
if [[ "$OFFLINE_MODE" == "true" || "$OFFLINE_MODE" == "True" ]]; then
  dest_dir="$PROJECT_ROOT/$OFFLINE_OUTPUT_DIR"
  mkdir -p "$dest_dir"
  cp "$latest_file" "$dest_dir/"
  log "offline_mode is enabled; saved $latest_file to $dest_dir and skipping all uploads."
  deactivate
  log "Script completed (offline mode)."
  exit 0
fi

# Upload to YouTube
log "Uploading $latest_file to YouTube."
python3 ~/RedditVideoMakerBot-master/uploaders/youtubeUpload.py "$latest_file" "$filename_without_ext" 2>&1 | tee -a "$LOG_FILE"

# Upload to Instagram
log "Uploading $latest_file to Instagram."
python3 ~/RedditVideoMakerBot-master/uploaders/instaUpload.py "$latest_file" "$filename_without_ext" 2>&1 | tee -a "$LOG_FILE"

# Deactivate the first virtual environment
log "Deactivating RedditVideoMakerBot virtual environment."
deactivate

# Activate the second virtual environment for TikTok uploader
log "Activating the virtual environment for TikTok uploader."
source ~/RedditVideoMakerBot-master/uploaders/TiktokAutoUploader/.tokvenv/bin/activate

# Copy to TiktokUploaderSourceFolder
log "Copying $latest_file to TikTok uploader folder."
cp "$latest_file" ~/RedditVideoMakerBot-master/uploaders/TiktokAutoUploader/VideosDirPath

# Upload to TikTok
log "Uploading to TikTok using TikTok uploader."
cd ~/RedditVideoMakerBot-master/uploaders/TiktokAutoUploader/
python3 cli.py upload --user crazystorylord -v "${filename_without_ext}_out.mp4" -t "$filename_without_ext" 2>&1 | tee -a "$LOG_FILE"

# Deactivate the second virtual environment
log "Deactivating TikTok uploader virtual environment."
deactivate

log "Script completed."

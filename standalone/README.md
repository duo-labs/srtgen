# srtGen Standalone 

## Quick Start Steps

The easiest was to install srtGen is as follows:

```
pip3 install -f requirements.txt
```

This will set up any required modeules not already present in the current python environment and we would reccomend using a fresh python virtual environment to avoid any version conflicts.

You will have to set up an S3 bucket with write privileges which is where the client will upload the extracted audio content to.

Make sure your local AWS credentials are setup and have sufficient privileges and then you can run a transcription with:

```
python 3  srtGen_standalone_cli.py ./test_data/tears_of_steel_30sec_test_video.mov -s YOUR_S3_BUCKET_NAME -o MY_SUBTITLE_FILE.srt
```

If transcription is not working for you it is most likely to be AWS permissions misconfiguration so please see below for more detailed setup instructions. More detailed usage instructions are in the Usage section below.

## Manual Installation & Setup

srtGen is written in Python 3 which most macOS and Linux systems will have installed already. Beyond Python 3 itself the only requirements for the standalone version of srtGen is [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html) and [ffmpeg](https://ffmpeg.org). 

You can install boto3 and it's dependencies easily with the following command:

```
python3 -m pip install boto3
```

`ffmpeg` is installed on most systems by default but there are a number of downloads available [here](https://ffmpeg.org/download.html) if it is not installed. Ensure the `ffmpeg` binary is installed at a location in your system PATH or directly set the `FFMPEG_BIN_PATH` variable to point at the binary's location. 

The scripts have only been tested on Linux and macOS so your mileage with Windows may vary.

## Configuration

The only configuration variable that should need to be set in the script itself is `FFMPEG_BIN_PATH` at the top of the script itself. By default this is set to just  `ffmpeg` to search the system PATH, if your ffmpeg binary is not in a location that is part of the system PATH then change `FFMPEG_BIN_PATH` to point directly to your binary. For example:

```
FFMPEG_BIN_PATH="/Users/hbadger/bin/ffmpeg"
```

In addition you will need to have your AWS credentials set up correctly locally to allow boto3 to use them. Details on setting up credentikals for AWS/boto3 can be found [here](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html).


## AWS Permissions

Ensure the AWS account you are using has the correct permissions to allow the upload of a file to the specified S3 bucket and the AWS Transcribe service. If the account does not have the correct permissions transcription will fail.


## Usage

Usage of `srtGen_standalone_cli` is quite straightforward, in it's simplest form a transcription can be generated with the following:

```
python 3  srtGen_standalone_cli.py movie_to_transcribe.mov -s my-srtgen-transcription-bucket -o file_to_save_subtitles_to.srt
```

There are a number of commandline options to control the script's execution:

* `-o` - The file that the generatwed subtitles should be saved to
* `-b` - Define the bitrate used to extract the audio from the video source (default is 48000 bps)
* `-m` - Path to save the extracted mp3 audio to, if no path is supplied a temporary file is used and deleted upon completion
* `-p` - The AWS profile to use. If you need to use non default credentials supply the name of the profile with this switch
* `-s` - The name of the S3 bucket to upload the extracted audio to
* `-v` - Verbose output



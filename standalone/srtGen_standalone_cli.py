#!/usr/bin/env python3

#######################################################################
##
## Name: srtGen_standalone_cl.py
## Author: Rich Smith (@iodboi)
## License: Apache 2.0
## Status: Sample code
##
#######################################################################


"""srtGen Standalone Client

This is a standalone script that extracts the audio from a source file 
(usually a movie), runs an AWS Transcribe job to transcribe the 
spoken words, and ouputs the results as a .srt formatted subtitle file.

This script requires the boto3 modules to be installed and for AWS
credentials with the appropriate privileges to be setup locally.

Usage
-----

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

Classes
-------

This script can also be used as a module and contains the following 
classes:

    * srtGenStandalone - Class that wraps all the functionality of transcription
    * srtGenError - Generic exception handler

Attributes
----------
FFMPEG_BIN_PATH (str): Path to the local ffpmeg binary that is used for 
audio extraction (default is 'ffmpeg')
"""

##Location of ffmpeg binary to use for audio extraction
FFMPEG_BIN_PATH = "ffmpeg"
## -----------------------------------------------------

import os
import sys
import time
import argparse
import tempfile
import subprocess
import urllib.request

import boto3
from botocore.exceptions import ClientError

from srtUtils import writeTranscriptToSRT

class srtGenError(Exception):
    """
    Generic exception wrapper
    """
    pass


class srtGenStandalone(object):
    """
    A class to wrap all the functionality required to extract audio, 
    upload to S3, schedule a Transcribe job, download the results, 
    and reformat into a .srt subtitle file.

    Methods
    -------
    extract_audio()
        Extracts an mp3 audio file from the source file

    upload_audio_to_s3()
        Uploads the extracted mp3 audio file to the S3 bucket

    run_transcribe_job()
        Configures and runs an AWS Transcribe job on the uploaded mp3

    wait_for_transcribe_job_to_complete()
        Polls the AWS Transcribe service to see if the Transcribe job 
        has completed

    download_transcript()
        Downloads the transcription results from AWS Transcribe

    generate_srt_file()
        Generate a .srt formatted subtitle file from the Transcribe 
        results
    """

    def __init__(self, aws_profile, s3_bucket_name):
        """
        Args
        ----------
        aws_profile (str): The name of the AWS credential profile to use
        s3_bucket (str): The name of the S3 bucket to upload the mp3's to
        """

        session = boto3.Session(profile_name=aws_profile)
        self.s3_client = session.client("s3")
        self.transcribe_client = session.client("transcribe")

        self.s3_bucket_name = s3_bucket_name

        self.transcript_file_uri = ""
        self.transcription_data = None
        self.tempfile_obj = None


    def __call__(self, in_filepath, srt_filepath, mp3_filepath=None, bitrate=48000):
        """
        Args
        ----------
        in_filepath (str): Path to the video/audio file to transcribe
        srt_filepath (str): Path where the generated .srt file should be written
        mp3_filepath (str): Path where to save extracted mp3 file. If 
        not specified termporary file used and deleted upon completion [optional]
        bitrate (int): The bitrate to use for the extracted mp3 (deafult is 48000)

        Returns
        -------
            bool: True on successful transcription, False in all other cases
        """

        self.timestamp =  str(time.time()).split(".")[0]

        ##Location from which source video is taken
        self.video_filepath = os.path.expandvars(os.path.expanduser(in_filepath))
    
        ##Location to write the extracted audio to
        if mp3_filepath:
            self.audio_filepath = os.path.expandvars(os.path.expanduser(mp3_filepath))
        else:
            ##If no mp3 path specified, create tempfile
            self.tempfile_obj = tempfile.TemporaryDirectory()
            self.audio_filepath = os.path.join(self.tempfile_obj.name, "%s_%s.mp3" % (os.path.splitext(os.path.split(self.video_filepath)[-1])[0], self.timestamp))

        ##Bitrate to use for audio extraction
        self.bitrate = bitrate

        ##Location to write .srt subtitle file to 
        self.srt_filepath = os.path.expandvars(os.path.expanduser(srt_filepath))


        print("[+] Transcribing audio from source file at: %s"%(self.video_filepath))

        try:

            ##Extract audio and transcode to correct bitrate and mp3 format as necersary (external ffmpeg used)
            self.extract_audio()

            ##Uplaod extracted aduio to specified S3 bucket
            self.upload_audio_to_s3()

            ##Setup and run AWS Transcribe job using the uploaded audio file as the source
            self.run_transcribe_job()

            ##Wait for the job to complete
            self.wait_for_transcribe_job_to_complete()

            ##Download the transcription results
            self.download_transcript()

            ##Create a subtitle file in the .srt format
            self.generate_srt_file()

            print("[+] Done!")
            return True

        except Exception as err:
            print("[-] Error encounted, %s \nexiting...."%(err))
            return False


    def extract_audio(self):
        """
        Extract an mp3 stream from a video file at the specified bitrate
         (default 48 kbps).

        Note: all this function does is shell out to ffmpeg so that 
        needs to be installed and accessible on the system path or
        you can specify a particular ffmpeg binary to use by setting
        the FFMPEG_BIN_PATH variable at the top of this script.

        Returns
        -------
            bool: True on success

        Raises
        ------
            subprocess.CalledProcessError: There was an error running the ffmpeg command
            
        """
        global FFMPEG_BIN_PATH

        print("[+] Using ffmpeg binary located at: %s"%(FFMPEG_BIN_PATH))
        print("[+] Extracting %d kbps audio stream from %s"%(self.bitrate/1000.0, self.video_filepath))

        print("[+] Writing extracted audio to: %s" % (self.audio_filepath))

        extract_cmd = [FFMPEG_BIN_PATH, "-y", "-loglevel", "error", "-stats", "-i", self.video_filepath, "-f", "mp3", "-ab", str(self.bitrate), "-vn", self.audio_filepath]

        try:
            subprocess.run(extract_cmd, capture_output=False, check=True)
        except subprocess.CalledProcessError as err:
            print("[-] Error extracting audio: %s"%(err))
            raise

        return True


    def upload_audio_to_s3(self):
        """
        Upload the extracted mp3 file to the specified S3 bucket

        Returns
        -------
            bool: True on success

        Raises
        ------
            botocore.exceptions.ClientError : There was an error 
            uploading the file to the specified S3 bucket
        """

        print("[+] Uploading extracted audio to S3 bucket: %s (this may take some time) ....."%(self.s3_bucket_name))
        try:
            response = self.s3_client.upload_file(self.audio_filepath, self.s3_bucket_name, os.path.split(self.audio_filepath)[-1])

        except ClientError as err:
            print("[-] Error uploading extracted audio to S3 bucket '%s': %s"%(self.s3_bucket_name, err))
            raise
        
        except Exception as err:
            print("[-] Unexpected error: %s"%(err))
            raise

        print("[+] Upload complete!")

        return True


    def run_transcribe_job(self):
        """
        Configure and start an AWS Transcribe job using the uploaded
        mp3 as the transcription source

        Returns
        -------
            bool: True on success

        Raises
        ------
            botocore.exceptions.ClientError : There was an error
            setting up the AWS Transcribe job
        """

        print("[+] Configurign and starting AWS Transcribe job")
        self.transcription_job_name = "AutoSubGen-%s-%s"%(os.path.split(self.video_filepath)[-1], self.timestamp)

        try:
            response = self.transcribe_client.start_transcription_job(TranscriptionJobName=self.transcription_job_name,
                                                                      LanguageCode = "en-US",
                                                                      Media={"MediaFileUri": "s3://%s/%s"%(self.s3_bucket_name, os.path.split(self.audio_filepath)[-1])},
                                                                      ContentRedaction={'RedactionType': 'PII','RedactionOutput': 'redacted_and_unredacted'})
        except ClientError as err:
            print("[-] Error setting up transcription job. Check the lambda has the correct Transcribe permissions. %s"%(err))
            raise

        except Exception as err:
            print("[-] Unexpected error: %s"%(err))
            raise


        print("[+] Transcription job running .....")
        return True


    def wait_for_transcribe_job_to_complete(self):
        """
        Periodically poll the AWS Transcribe service to see if
        the AWS Transcribe Job has completed yet. If there are
        3 consequetive errors getting job status we abort

        Returns
        -------
            bool: True on success

        Raises
        ------
            botocore.exceptions.ClientError : There was an error getting
            the status of the AWS Transcribe job
        """

        print("[+] Waiting for Transcribe job '%s' to complete " % (self.transcription_job_name),  end="")
        
        error_count = 0
        while True:

            try:

                response = self.transcribe_client.get_transcription_job(TranscriptionJobName=self.transcription_job_name )
                
                print(".", end="")
                if 'TranscriptFileUri' in response["TranscriptionJob"]["Transcript"]:
                    print("\n[+] Transcription complete!")
                    break
                error_count = 0
                time.sleep(10.0)
            
            except Exception as err:
                print("[-] Error getting results from Transcribe service: %s "%(err))
                
                ##Only raise an error if 3 or more http/network errors are received
                if error_count >=3:
                    raise

                error_count+=1
                continue

        try:
            self.transcript_file_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        except Exception as err:
            print("[-] Error parsing the response from AWS Transcribe. Cannot continue: %s"%(err))
            raise(srtGenError)

        return True


    def download_transcript(self):
        """
        Once the AWS transcribe job has completed download the results

        Returns
        -------
            bool: True on success

        Raises
        ------
            requests.exceptions : There was an error downlaoding the transcription
            results from the URL specified
        """

        try:
            print("[+] Downloading completed transcription results.....")
            response = urllib.request.urlopen(self.transcript_file_uri)
            transcript_data = response.read().decode("utf-8")

        except Exception as err:
            print("[-] Error downloading transcription results: %s"%(err)) 
            raise

        self.transcription_data = transcript_data
        
        return True


    def generate_srt_file(self):
        """
        Now take the transcript file and reformat it into an .srt file for use in video players
        :return:
        """

        print("[+] Creating srt file and writing to: %s"%(self.srt_filepath))

        # Create the SRT File for the original transcript and write it out - call out to aws open sourced code that does this
        try:
            writeTranscriptToSRT(self.transcription_data, 'en', self.srt_filepath)
        except Exception as err:
            print("[-] Error writing the genering the .srt subtitle file: %s"%(err))
            raise


## Implement a simple CLI
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("input_filepath", help="Location of the source file which should be transcribed")
    parser.add_argument("-o", "--srt-output", help="Location to save the .srt subtitle file that is generated. If none is specified it will just be printed to stdout")
    parser.add_argument("-b", "--bitrate", default=48000, type=int ,help="The bitrate ffmpeg will use to extract the audio from the source (default=48000 bps)")
    parser.add_argument("-m", "--mp3-output", help="Location of where the MP3 audio file should be extracted to, if none is given a temporary file is used and deleted at the end of the execution.")
    parser.add_argument("-p", "--aws-profile", help="AWS profile to use")
    parser.add_argument("-s", "--s3-bucket", help="S3 bucket to upload extracted audio to for transcription")
    #TODO
    parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    args = parser.parse_args()

    try:
        sgs = srtGenStandalone(aws_profile=args.aws_profile, s3_bucket_name=args.s3_bucket)
        sgs(args.input_filepath, args.srt_output, mp3_filepath=args.mp3_output, bitrate=args.bitrate)

    except srtGenError as err:
        sys.exit(-1)

    except Exception as err:

        print("[-] Unhandled exception: %s"%(err))
        raise
        sys.exit(-2)

    sys.exit(0)
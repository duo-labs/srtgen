#!/usr/bin/env python3

#######################################################################
##
## Name: srtGen_service_cli.py
## Author: Rich Smith (@iodboi)
## License: Apache 2.0
## Status: Sample code
##
#######################################################################

"""strGen Service Client

This is a script that generates a .srt subtitle file from the supplied
source file (usually a video) by using the transcription service 
deployed via the Chalice app to do most of the heavy lifting. The
advantage to this approach vs the standalone client is that the 
user executing this script does not need to have any permissions
on the AWS infrastructure itself. 

This service client extracts the audio from a source file 
(usually a movie), and then proceeds to contact the service to get an
S3 bucket to uplaod the mp3 to, schedule a transcription job, and 
reformat the results from that subscription to but in .srt format.
Finally the client downloads the subtitle file generated by the 
service.

This script requires the boto3 modules to be installed but does not 
require any local AWS credentials as boto is only used for uploading
the mp3 file via a pre-signed S3 URL obtained from the service.

Usage
-----

Usage of `srtGen_service_cli` is quite straightforward, in it's simplest form a transcription can be generated with the following:

```
python 3 srtGen_service_cli.py movie_to_transcribe.mov -s my-srtgen-transcription-bucket
```

There are a number of commandline options to control the script's execution:

* `-o` - The file that the generatwed subtitles should be saved to, if this is left blank the contents of the .srt is just printed to the screen
* `-b` - Define the bitrate used to extract the audio from the video source (default is 48000 bps)
* `-m` - Path to save the extracted mp3 audio to, if no path is supplied a temporary file is used and deleted upon completion
* `-v` - Verbose output

Classes
-------

This script can also be used as a module and contains the following 
classes:

    * srtGen - Class that wraps all the functionality of transcription via the service
    * srtGenError - Generic exception handler

Attributes
----------
MODULE_LOCATION (str): This is a dynamically generated absolute path showing where the 
executing script is located in the filesystem.
"""

import os
import sys
import time
import argparse
import requests
import tempfile
import subprocess
import configparser

import boto3
from botocore.exceptions import ClientError, ProfileNotFound

##The absolute path location of this file
MODULE_LOCATION = os.path.abspath(os.path.dirname(__file__))

class srtGenError(Exception):
    """
    Generic exception wrapper
    """
    pass

class srtGen(object):
    """
    A class to wrap all the functionality required to extract audio, 
    upload to S3, schedule a Transcribe job, download the results, 
    and reformat into a .srt subtitle file using the already deployed
    transcritpion service.

    Methods
    -------
    extract_audio()
        Extracts an mp3 audio file from the source file

    get_signed_s3_url_and_upload()
        Request a pre-signed S3 URL from the transcription service and
        use that URL to upload the extracted mp3 audio to S3 

    start_transcription()
        Configures and runs an AWS Transcribe job on the uploaded mp3

    download_srt()
        Wait until the transcription job is complete and download the
        generated .srt file

    save_display()
        Save and/or display the download .srt subtitle file
    """

    def __init__(self, config_filepath=None):
        """
        Args
        ----
        config_filepath (str): Filepath of configuration file to use 
        (default is 'MODULE_LOCATION/config.ini')
        """

        self.timestamp = str(time.time()).split(".")[0]

        ##Read config file - if non given assume a file called "config.ini" in the same dir as this script
        if not config_filepath:
            config_filepath = os.path.join(MODULE_LOCATION, "config.ini")

        self.config_parser = configparser.ConfigParser()
        self.config_parser.read(os.path.expandvars(os.path.expanduser(config_filepath)))

        ##AWS credential profile to use with boto
        # self.aws_profile = self.config_parser.get("srtGen","AWS_PROFILE")

        ##URL of the lambda service
        self.api_url = self.config_parser.get("srtGen","API_URL")

        ##Path to the local ffmpeg binary that will be used to extract an audio mp3
        self.ffmpeg_bin_path = self.config_parser.get("srtGen","FFMPEG_BIN_PATH")

        print("[+] Contacting service at: %s"%(self.api_url))
        print("[+] Using ffmpeg binary located at: %s"%(self.ffmpeg_bin_path))


    def __call__(self, in_filepath, mp3_filepath=None, srt_filepath=None,  bitrate=48000):
        """
        Main class that performs all of the steps to extract audio, 
        upload, schedule a trancribe job, & download the results as 
        an .srt subtitle file from the companion service running in 
        AWS lambda

        Args
        ----
        in_filepath (str): Path to the video/audio file to transcribe
        srt_filepath (str): Path where the generated .srt file should 
        be written
        mp3_filepath (str): Path where to save extracted mp3 file. If 
        not specified termporary file used and deleted upon completion 
        [optional]
        bitrate (int): The bitrate to use for the extracted mp3 
        (deafult is 48000)

        Returns
        -------
            bool: True on success, False otherwise
        """    

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

        ##Location to write srt file to
        if srt_filepath:
            self.srt_filepath = os.path.expandvars(os.path.expanduser(srt_filepath))
        else:
            self.srt_filepath = None

        print("[+] Transcribing audio from source file at: %s"%(self.video_filepath))
        try:

            ##Extract audio and transcode to correct bitrate and mp3 format as necersary (external ffmpeg used)
            self.extract_audio()

            ##Call our lamda to generate a pre-signed s3 url & use that to upload extracted audio
            self.get_signed_s3_url_and_upload()

            ##Call our lamda to setup & start transcription job using the upload audio
            self.start_transcription()

            #Poll and wait for the transcription job to complete
            self.download_srt()

            ## Save srt to local file specified and/or display it to the screen
            self.save_display_srt(display=True)

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
        print("[+] Extracting %d kbps audio stream from %s"%(self.bitrate/1000.0, self.video_filepath))
        
        print("[+] Writing extracted audio to: %s" % (self.audio_filepath))

        extract_cmd = [self.ffmpeg_bin_path, "-y", "-loglevel", "error", "-stats", "-i", self.video_filepath, "-f", "mp3", "-ab", str(self.bitrate), "-vn", self.audio_filepath]

        try:
            subprocess.run(extract_cmd, capture_output=False, check=True)
        except subprocess.CalledProcessError as err:
            print("[-] Error extracting audio: %s"%(err))
            raise

        return True


    def get_signed_s3_url_and_upload(self):
        """
        Call the lambda service to have a short lived S3 URL returned 
        that allows us to upload the audio file for subsequent 
        transcription while also bypassing the 10MB upload limite of 
        the AWS API Gateway
        
        Returns
        -------

            bool: True on Success

        Raises
        ------

            requests.exceptions.RequestException: There was an error 
            requesting a pre-signed S3 URL from the service

            srtGenError: There was an error parsing or processing the 
            request for a pre-sgned S3 URL
        """
        print("[+] Requesting upload URL")

        # Retrieve a presigned S3 POST URL
        try:
            response = requests.get("%s/get_audio_upload_url" % (self.api_url))
            #print(response.json)
            response.raise_for_status()

        except requests.exceptions.RequestException as err:
            print("[-] Error getting an upload URL from the service. Ensure you have your lambda at %s set up correctly."%(self.api_url))
            raise

        except Exception as err:
            print("[-] Unexpected error: %s"%(err))
            raise

        ##Call to the service completed but it indicated an error in it's response
        if response.json()["status"] == "error":
            print("[-] Error in response from service: %s"%(response.json()["response"]))
            raise srtGenError("Error in response from service: %s"%(response.json()["response"]))

        print("[+] Upload URL received")

        try:
            s3_data = response.json()["response"]

            ## Get the generated pre-signed URL
            self.s3_presigned_url = s3_data['url']

            ## Get the filename that was set for the pre-signed URL upload
            self.audio_uuid_filename = s3_data['fields']['key']

        except Exception as err:
            print("[-] Error parsing the response from the service: %s"(err))
            raise srtGenError("Error parsing the response from the service: %s"(err))

        print("[+] Uploading extracted audio to %s"%(self.audio_uuid_filename))
        ## now upload the generted audiofile to the temporary S3 URL and name the file as the UUID
        with open("%s"%(self.audio_filepath), 'rb') as f:
            files = {'file': ("%s" % (self.audio_uuid_filename), f)}

            try:
                http_response = requests.post(self.s3_presigned_url, data=s3_data['fields'], files=files)
                #http_response = requests.put(self.s3_presigned_url, data=f)
                http_response.raise_for_status()

            except requests.exceptions.RequestException as err:
                print("[-] Error uploading audio to the returned S3 URL. Check the lambda has the correct S3 permissions.")
                raise

            except Exception as err:
                print("[-] Unexpected error: %s"%(err))
                raise

        # If successful, returns HTTP status code 204 http_response.status_code
        if http_response.status_code == 204:
            print("[+] Upload successful")
        else:
            print("[-] Received an exepected HTTP response code %d when uploading"%(http_response.status_code))
            raise srtGenError("Received an exepected HTTP response code %d when uploading"%(http_response.status_code))

        return True


    def start_transcription(self):
        """
        Configure and start an AWS Transcribe job using the uploaded
        mp3 as the transcription source

        Returns
        -------
            bool: True on success

        Raises
        ------
            requests.exceptions.RequestException: There was an error 
            starting a Transcribe job
        """
        print("[+] Configuring and starting AWS Transcribe job")
        
        ## Pass the UUID to the lambda which will then setup & run the Transcription job using the
        ## previously updated file
        try:
            response = requests.get("%s/transcribe/%s" % (self.api_url, self.audio_uuid_filename))
        
        except requests.exceptions.RequestException as err:
            print("[-] Error setting up transcription job. Check the lambda has the correct Transcribe permissions. %s"%(err))
            raise

        except Exception as err:
            print("[-] Unexpected error: %s"%(err))
            raise

        try:
            ##Extract the transcription job name
            self.transcription_job_name = response.json()["response"]
            print("[+] Started Transcribe job %s"%(self.transcription_job_name))
        
        except Exception as err:
            print("[-] Error parsing the response from the service: %s"%(err))
            raise

        return True


    def download_srt(self):
        """
        Download the .srt formatted subtitle file from the service

        Returns
        -------
            bool: True on success

        Raises
        ------
            requests.exceptions.RequestException - There was an error 
            starting the Transcribe job
        """
        print("[+] Waiting for Transcribe job %s to complete: "%(self.transcription_job_name), end="")

        error_count = 0
        while True:
            try:
                response = requests.get("%s/results/%s" % (self.api_url, self.transcription_job_name))
                #print("%s"%(response.text))

                if response.json()["status"] == "running":
                    #print("Job %s still running"%(self.transcription_job_name))
                    sys.stdout.write(".")
                    sys.stdout.flush()
                    time.sleep(10.0)
                    continue

                elif response.json()["status"] == "error":
                    print("Error with Transcription Job %s"%(response.json()["response"]))
                    raise srtGenError()

                else:
                    print("DONE!\n[+] Transcibe job complete")
                    break


            except requests.exceptions.RequestException as err:
                print("[-] Error getting results from the service. Ensure you have your lambda at %s set up correctly."%(self.api_url))
                
                ##Only raise an error if 3 or more http/network errors are received
                if error_count >=3:
                    raise

                error_count+=1
                continue

            except Exception as err:
                print("[-] Unexpected error: %s"%(err))
                raise

        self.srt_data = response.json()["response"]
        print("[+] Transciption data downloaded")

        return True


    def save_display_srt(self, display = False):
        """
        Save the .srt file to the path specified and/or print to the screen

        Args
        ----
        display (bool): Whether to print the subtitle file to stdout 
        (default is False)

        Returns
        -------
            bool : True on success

        """
        print("[+] Finalising .srt subtitle data")

        if self.srt_filepath:
            print("[+] Saving file to: %s"%(self.srt_filepath))
            with open(self.srt_filepath, "w") as f:
                f.write(self.srt_data)

            print("[+] Written .srt subtitle file to %s"%(self.srt_filepath))
       
        elif display:
            print("[!] Full subtitle file below:")
            print("-"*40)
            print(self.srt_data)
            print("-"*40)

        return True

## Implement a simple CLI
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("input_filepath", help="Location of the source file which should be transcribed")
    parser.add_argument("-o", "--srt-output", help="Location to save the .srt subtitle file that is generated. If none is specified it will just be printed to stdout")
    parser.add_argument("-b", "--bitrate", default=48000, type=int ,help="The bitrate ffmpeg will use to extract the audio from the source (default=48000 bps)")
    parser.add_argument("-m", "--mp3-output", help="Location of where the MP3 audio file should be extracted to, if none is given a temporary file is used and deleted at the end of the execution.")
    #TODO
    parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    args = parser.parse_args()

    try:
        srt_gen_obj = srtGen()
        srt_gen_obj(args.input_filepath, mp3_filepath=args.mp3_output, srt_filepath=args.srt_output, bitrate=args.bitrate)

    except srtGenError as err:
        sys.exit(-1)

    except Exception as err:

        print("[-] Unhandled exception: %s"%(err))
        raise
        sys.exit(-2)

    sys.exit(0)
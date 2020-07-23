#######################################################################
##
## Name: app.py
## Author: Rich Smith (@iodboi)
## License: Apache 2.0
## Status: Sample code
##
#######################################################################

"""strGen Web Service

An example Chalice application that runs in an AWS lambda to do the 
heavy lifting of running a transcription job on an uploaded audio
sample.

This mode of operation that uses a service intermediary has the 
advantage of the end user not needing to have any permissions in
AWS, instead they just need permissions to call this web app,
and the web app running in AWS has the permissions to call the 
other AWS services.

Usage
-----
This application is intended to run as a Chalice web application
and needs to be deployed as such. Please RTFM located in the
srtGen_service.md file to see the configuration and deployment 
process.

Routes
------
    transcribe: Setup and initiate an AWS transcription job
    upload: Get a pre-signed S3 URL to upload the audio sample to
    results: Get the results of the transcription formatted as .srt

Functions
---------
    run_transcription_job: 

    check_if_transcription_job_complete:

    download_transcript:

    generate_srt_file:

Attributes
----------
S3_BUCKET_NAME (str): Name of the S3 bucket to generate pre-signed 
URLs for
EXPIRATION (int): The lifetime in seconds the pre-signed URL is 
valid for
"""

import time
import uuid
import urllib

import boto3
from botocore.exceptions import ClientError

from chalicelib.srtUtils import getPhrasesFromTranscript, getPhraseText
from chalice import Chalice, Response

#TODO add number of speakers switch
app = Chalice(app_name='srtGenService')
app.debug = True

## CHANGE THESE VARIABLES BEFORE DEPLOYMENT AS NEEDED
# The name of an S3 bucket to write the audio uploads to
S3_BUCKET_NAME = "autosubgen-iodboi"
# The time in seconds that the pre-signed url is valid for, 2 mins is the default
EXPIRATION = 120
##------------------------------------

@app.route("/transcribe/{audio_file_uuid}", methods=["GET"])
def transcribe(audio_file_uuid):
    """Setup and start a new AWS Transcribe job

    This is the endpoint that a client calls to configure and kick off 
    a new AWS Transcribe job. The supplied argument 'audio_file_uuid'
    is the identifier through which this Transcribe job is linked to 
    a previously uploaded mp3 file containing the audio to transcribe.

    If the job is successfully scheduled a HTTP 200 json blob with a 
    "status" value of "success" is returned to the user along with the
    name of the Transcribe job.

    If there is an error looking up the Transcribe job a HTTP 400
    json blob will be returned with a "status" value of "error". 

    Most of the real work of interacting with AWS is done in the 
    'run_transcribe_job' that this route calls

    Route
    -----
    url = /transcribe/{audio_file_uuid}

    Returns
    -------
        Response() HTTP 200: On success
        Response() HTTP 400: On failure
    """
    request = app.current_request

    timestamp = str(time.time()).split(".")[0]

    ## Transcripton job name
    transcription_job_name = "AutoSubGen_%s_%s"%(timestamp, uuid.uuid4().hex)

    ## Set up a new transcription job
    try:
        ret = run_transcribe_job(transcription_job_name, audio_file_uuid)
    except Exception as err:
        ##Log error and send HTTP 400 response
        print("[-] Unhandled Exception: %s"%(err))
        return Response(status_code=400,\
                    headers={'Content-Type': 'application/json'},\
                    body={'status': 'error',\
                    'response': "Error setting up transcription job %s"%(transcription_job_name)})

    ## Success - HTTP 200 response
    return Response(status_code=200,\
                    headers={'Content-Type': 'application/json'},\
                    body={'status': 'success',\
                    'response': ret["TranscriptionJob"]["TranscriptionJobName"]})


@app.route("/results/{transcription_job_name}", methods=["GET"])
def results(transcription_job_name):
    """Check whether Transcribe job has completed & return .srt

    This is the endpoint that a client calls to check whether the
    specified Transcribe job has completed. 
    
    If the job has not completed a HTTP 200 json blob with a "status"
    of "running" will be returned. 

    If the job has completed then the Transcribe results are taken
    and used to generate a .srt file that is returned to the user in
    a HTTP 200 json blob with a "status" value of "success".

    If there is an error looking up the Transcribe job a HTTP 400
    json blob will be returned with a "status" value of "error". 
    You will most likely see an error when the name of the supplied 
    Transcribe Job is incorrect / no longer available in Transcribe.

    Route
    -----
    url = /results/{transcription_job_name}

    Returns
    -------
        Response() HTTP 200: On success
        Response() HTTP 400: On failure
    """
    #todo save generated srt's to s3 for future retreval without regen

    print("results requested for %s"%(transcription_job_name))

    try:
        transcript_file_uri = check_if_transcribe_job_complete(transcription_job_name)

        if not transcript_file_uri:
            return Response(status_code=200,\
                    headers={'Content-Type': 'application/json'},\
                    body={'status': 'running',
                    'response' :""})

    except Exception as err:
        print("[-] Error %s"%(err))
        return Response(status_code=400, \
                    headers={'Content-Type': 'application/json'}, \
                    body={'status': 'error',\
                    'response': "Error getting information about transcription job %s. Check the job name is valid."%(transcription_job_name)})

    ##Download trnscription data 
    transcript_data = download_transcript(transcript_file_uri)

    ##Convert the transcription data into srt format
    srt_data = generate_srt_file(transcript_data)

    ##ToDo - caching of srt's

    return Response(status_code=200,\
                    headers={'Content-Type': 'application/json'},\
                    body={'status': 'success',\
                    'response': srt_data})
    

@app.route("/get_audio_upload_url", methods=["GET"])
def upload():
    """Generate a pre-signed S3 URL and return that to the caller 
    
    This function request a pre-signed S3 URL from AWS to allow
    the caller to upload their mp3 audio sample without having 
    to worrying about the 10MB max payload size of AWS API 
    Gateway or have direct permissions in AWS S3.

    
    If the request for a pre-sgned S3 URL is successful a HTTP 
    200 json blob with a "status" of "success" will be returned
    along with the pre-signed URL itself.

    If there is an error looking up the Transcribe job a HTTP 400
    json blob will be returned with a "status" value of "error". 

    Route
    -----
    url = /get_audio_upload_url

    Returns
    -------
        Response() HTTP 200: On success
        Response() HTTP 400: On failure
    """
    s3_client = boto3.client("s3")

    # Generate a random S3 key name
    audio_file_uuid = uuid.uuid4().hex

    fields = None
    conditions = None
    print("**** %s.mp3"%(audio_file_uuid))
    try:

        # Generate the presigned URL for put requests
        # presigned_url = s3_client.generate_presigned_url(ClientMethod='put_object',
        #     Params={"Bucket": S3_BUCKET_NAME, "Key": upload_key}, ExpiresIn=EXPIRATION)
        presigned_url = s3_client.generate_presigned_post(S3_BUCKET_NAME,
                                            "%s.mp3"%(audio_file_uuid),
                                            Fields=fields,
                                            Conditions=conditions,
                                            ExpiresIn=EXPIRATION)
    except ClientError as e:
        print("[-] Error: %s"%(e))
        return Response(status_code=400,
                    headers={'Content-Type': 'application/json'},
                    body={'status': 'error',
                    'response': "Error generating pre-signed S3 URL"})

    return Response(status_code=200,
                    headers={'Content-Type': 'application/json'},
                    body={'status': 'success',
                    'response': presigned_url})

##Functions below are not directly callable via the 'api' 

def run_transcribe_job(transcription_job_name, audio_file_uuid):
    """Call AWS to setup and run new Transcribe job

    This function creates a transcription job to run against the
    supplied 'audio_file_uuid' that has been uploaded to S3 and
    name that job 'transcription_job_name'. This job can be 
    reference by this name to get it's status and results.

    Raises
    ------
        requests.exceptions.ClientError - There was an error setting up job with AWS 

    Return
    ------
        Response() object: Request was successful

    """
    print("[+] Starting AWS Transcribe job")

    transcribe_client = boto3.client("transcribe")

    print("s3://%s/%s"%(S3_BUCKET_NAME, audio_file_uuid))

    try:
        response = transcribe_client.start_transcription_job(TranscriptionJobName=transcription_job_name,
                                                             LanguageCode="en-US",
                                                             Media={"MediaFileUri": "s3://%s/%s"%(S3_BUCKET_NAME, audio_file_uuid)})
    except ClientError as err:
        print("[-] ERROR: %s"%(err))
        reaise

    print("[+] Transcription job running .....")
    return response


def check_if_transcribe_job_complete(transcription_job_name):
    """Check if the specified AWS Transcribe job has completed yet

    Call the AWS API to see if the named Transcribe job is still 
    running or has completed.

    Returns
    -------
        None - Transcribe job not completed
        transcript_file_uri (str): URI pointing to the raw results of 
        the Transcribe job

    """
    transcribe_client = boto3.client("transcribe")

    response = transcribe_client.get_transcription_job(TranscriptionJobName=transcription_job_name )

    if 'TranscriptFileUri' in response["TranscriptionJob"]["Transcript"]:
        print("\n[+] Transcription complete!")

        transcript_file_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]

        return transcript_file_uri

    else:
        return None


def download_transcript(transcript_file_uri):
    """Download and decode Transcribe job results

    Download the Transcribe Job results from the 
    supplied URL and format them as a string

    Returns
    -------
    transcript_data (str): The transcription data
    """
    print("[+] Downloading completed transcript.....")
    response = urllib.request.urlopen(transcript_file_uri)
    transcript_data = response.read().decode("utf-8")

    return transcript_data


def generate_srt_file(transcript_data):
        """Take an AWS Transcript results and format it as .srt subtitles
        
        Now take the transcript file and reformat it into an .srt file for
        use in video players. This functions code was mostly taken 
        from the module srtUtils: 
        (https://github.com/aws-samples/aws-transcribe-captioning-tools/blob/master/src/srtUtils.py)
        
        Returns
        -------
        srt_data (str): String representing the contents of the srt subtitle file
        """
        srt_data = ""

        ##Modified from the standard strUtil functions to not require a file to write to  - TODO URL

        # Create the SRT File for the original transcript and write it out.
        phrases = getPhrasesFromTranscript( transcript_data )

        x = 1
        for phrase in phrases:

            # determine how many words are in the phrase
            length = len(phrase["words"])
            
            # write out the phrase number
            srt_data += str(x) + "\n"
            x += 1
            
            # write out the start and end time
            srt_data +=  phrase["start_time"] + " --> " + phrase["end_time"] + "\n"
                        
            # write out the full phase.  Use spacing if it is a word, or punctuation without spacing
            out = getPhraseText( phrase )

            # write out the srt file
            srt_data += out + "\n\n"
            
        return srt_data


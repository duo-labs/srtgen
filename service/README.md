# srtGen Service

## Quick Start Steps

The easiest was to install srtGen is as follows:

```
pip3 install -f requirements.txt
```

This will set up any required modeules not already present in the current python environment and we would reccomend using a fresh python virtual environment to avoid any version conflicts.

You will need to set up an S3 bucket that will be used to store the audio files that are uploaded for subscription. This bucket *does not* need to be publicly accessible and should be kept private, instead the service generates a pre-signed S3 URL to allow the client to upload their file to the private bucket. It is recommended that you create a new bucket for use solely with srtGen, once you have a bucket created set it's name on line 18 of `app.py`:

```
S3_BUCKET_NAME="my_S3_bucket_name_for_use_with_srtGen"
```

Once this is setup run the `deploy.py` script to set up the application in your AWS environment using the AWS credentials in a profile named `srtGen_deploy`, this script also generates an initial configuration for the service client:

```
python3 ./deploy.py

```

Now the application should be deployed and the URL of it's API set in `config.ini`. To produce a transcription it is as straight forward as:

```
python3 srtGen_service_cli.py ./test_data/tears_of_steel_30sec_test_video.mov
```

If transcription is not working for you it is most likely to be AWS permissions misconfiguration so please see below for more detailed setup instructions.


## Manual Installation

The service version of srtGen has two main components, the service portion which is at its core an AWS Lambda function and a client which runs locally to extract and upload the audio to the service and retrieve the subtitle file after it has been generated.

The service is written in Python and uses the [Chalice](https://aws.github.io/chalice/index) framework for easily building serverless apps. As part of the setup detailed below you will need to deploy the strGen service Chalice application, to do this you will need Chalice installed locally. Detailed installation docs are [here](https://aws.github.io/chalice/quickstart.html) but Chalice installation can be achieved with:

```
python3 -m pip install chalice
```

The client is also written in Python3 which most macOS and Linux systems will have installed already. Beyond Python 3 itself the only requirements for the client are [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html) [requests](https://requests.readthedocs.io/en/master/), and [ffmpeg](https://ffmpeg.org). 

You can install boto3 & requests easily with the following commands:

```
python3 -m pip install boto3 requests
```

`ffmpeg` is installed on most systems by default but there are a number of downloads available [here](https://ffmpeg.org/download.html) if it is not installed. Ensure the `ffmpeg` binary is installed at a location in your system PATH or directly set the `FFMPEG_BIN_PATH` variable to point at the binary's location. 

The scripts have only been tested on Linux and macOS so your mileage with Windows may vary.

## Configuration

The client has an config file in `.ini` format where a few parameters should be defined. 

* `API_URL` - The URL of the Chalice app, this will only be known *after* you have deployed the app (see below)
* `FFMPEG_BIN_PATH` - The path to the `ffmpeg` binary that will be used by the client to extract audio

By default this is set to just  `ffmpeg` to search the system PATH, if your ffmpeg binary is not in a location that is part of the system PATH then change `FFMPEG_BIN_PATH` to point directly to your binary. For example:

```
FFMPEG_BIN_PATH = /Users/hbadger/bin/ffmpeg
```

Finally you need to select the S3 bucket you want to use to save the uploaded audio files that will be transcribed. This bucket *does not* need to be publicly accessible and should be kept private, instead the service generates a pre-signed S3 URL to allow the client to upload their file to the private bucket. It is recommended that you create a new bucket for use solely with srtGen, once you have a bucket created set it's name on line 18 of `app.py`:

```
S3_BUCKET_NAME="my_S3_bucket_name_for_use_with_srtGen"
```
**If you fail to set this variable before deployment transcription will fail**


## Chalice App Deployment

### tl;dr

Once you have Chalice installed we need to setup a new user in your AWS environment to use to deploy the Chalice app. The new user should have at least the following permissions associated:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "iam:GetRole",
                "apigateway:PUT",
                "iam:ListRoles",
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:PutRolePolicy",
                "apigateway:DELETE",
                "iam:PassRole",
                "iam:DeleteRolePolicy",
                "apigateway:PATCH",
                "lambda:*",
                "apigateway:POST",
                "apigateway:GET",
                "iam:ListRolePolicies"
            ],
            "Resource": "*"
        }
    ]
}
```

Once created add the API credentials for the new user to your `~/.aws/credentials` file under a new profile named `srtgen_deploy` e.g.

```
[srtgen_deploy]
aws_access_key=AKXXXXXXXXXXXXXXX
aws_secret_access_key=SECRET_KEY_HERE
region=us-east-2
```
This is the profile we will use with chalice to deploy the app and **it is important that it is named `srtgen_deploy` otherwise the deployment scripts will fail**.

Once this is setup run the `deploy.py` script to set up the application in your AWS environment and generate an initial configuration for the service client:

```
python3 ./deploy.py

```

Now the application should be deployed and the URL of it's API set in `config.ini`. To produce a transcription it is as straight forward as:

```
python3 srtGen_service_cli.py transcription_test_video_30sec.mov
[+] Contacting service at: https://XXXXXXXXXXXX.execute-api.us-east-2.amazonaws.com/api/
[+] Using ffmpeg binary located at: ffmpeg
[+] Transcribing audio from source file at: transcription_test_video_30sec.mov
[+] Extracting 48 kbps audio stream from transcription_test_video_30sec.mov
[+] Writing extracted audio to: /var/folders/2r/5wvkylb97d93qb2njrt_pg5m0000gr/T/tmpxbp10zxu/transcription_test_video_30sec_1592945813.mp3
size=     176kB time=00:00:30.01 bitrate=  48.1kbits/s speed=63.2x
[+] Requesting upload URL
[+] Upload URL received
[+] Uploading extracted audio to 472b8e7881fd42e49e9e58a0a6d128ef.mp3
[+] Upload successful
[+] Configuring and starting AWS Transcribe job
[+] Started Transcribe job AutoSubGen_1592945816_88b05155d80d4cb2910bba5eab265778
[+] Waiting for Transcribe job AutoSubGen_1592945816_88b05155d80d4cb2910bba5eab265778 to complete: .....DONE!
[+] Transcibe job complete
[+] Transciption data downloaded
[+] Finalising .srt subtitle data
[!] Full subtitle file below:
----------------------------------------
1
00:00:01,389 --> 00:00:04,309
Look, CBO, we have to follow our

2
00:00:04,320 --> 00:00:06,769
passions. You have your robotics and I just want

3
00:00:06,769 --> 00:00:09,460
to be awesome his face. Why don't you just

4
00:00:09,460 --> 00:00:12,900
get me that you're by my robot hand? I'm

5
00:00:12,910 --> 00:00:16,420
freaked out, but it's all right. Fine.

6
00:00:16,640 --> 00:00:18,850
Freaked out of having nightmares that I'm think case.


----------------------------------------
[+] Done!
```


## Client Usage

Usage of `srtGen_service_cli` is quite straightforward, in it's simplest form a transcription can be generated with the following:

```
python 3 srtGen_service_cli.py movie_to_transcribe.mov -s my-srtgen-transcription-bucket
```

There are a number of commandline options to control the script's execution:

* `-o` - The file that the generatwed subtitles should be saved to, if this is left blank the contents of the .srt is just printed to the screen
* `-b` - Define the bitrate used to extract the audio from the video source (default is 48000 bps)
* `-m` - Path to save the extracted mp3 audio to, if no path is supplied a temporary file is used and deleted upon completion
* `-v` - Verbose output



### More Service Details

### Permissions

The most complicated part of setting up the service is making sure the various permissions, at the various layers, between various components are all set up correctly. Efforts were made to simplify this as much as possible but there is still room for mistakes so be careful and if things are not working probably start here to debug the issue.

The srtGen service has two main groups of permissions that are dealt with seperately _Chalice permissions_ (deploy time permissions) and _lambda permissions_ (runtime permissions). It is also be worth noting that the service itself has no concept of user level permissions, if a user is able to connect to the URL setup by Chalice then that user will be able to submit files for transcription and likely incur a charge from AWS. 

#### Chalice User Permissions

Chalice permissions are used when deploying the srtGen service to your AWS instance, the account used with Chalice needs to have permissions to interact with AWS Lambda, API Gateway, and IAM. As the Chalice framework continues to develop new permissions may be need but this set was used successfully at the time of writing:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "iam:GetRole",
                "apigateway:PUT",
                "iam:ListRoles",
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:PutRolePolicy",
                "apigateway:DELETE",
                "iam:PassRole",
                "iam:DeleteRolePolicy",
                "apigateway:PATCH",
                "lambda:*",
                "apigateway:POST",
                "apigateway:GET",
                "iam:ListRolePolicies"
            ],
            "Resource": "*"
        }
    ]
}
```

The account being used for Chalice deployment should have it's credentials in a profile in `~/.aws/credentials` that will be used to deploy the Chalice app (see below).

#### Lambda Role permissions

The lambda permissions are used at runtime and are effectively the permissions the Chalice app executes with. The permissions detailed below are applied via the role that is associated with the AWS Lambda function and allows the application code to do the following at a high level:

* Generate a pre-signed S3 URL to allow the client to upload it's audio for transcription without needing any AWS permissions
* Read the uploaded file from S3
* Setup and run an AWS Transcribe job
* Write logs to AWS Cloudwatch

The associated permissions required to achieve the above in json form look like 

Which in json form look like:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": [
                "s3:GetLifecycleConfiguration",
                "s3:CreateBucket",
                "iam:CreateRole",
                "s3:ListBucket",
                "iam:PutRolePolicy",
                "s3:GetBucketPolicy",
                "apigateway:DELETE",
                "s3:GetObjectAcl",
                "iam:PassRole",
                "iam:DeleteRolePolicy",
                "transcribe:StartTranscriptionJob",
                "apigateway:PATCH",
                "s3:PutLifecycleConfiguration",
                "s3:PutBucketAcl",
                "apigateway:GET",
                "s3:DeleteBucket",
                "iam:GetRole",
                "apigateway:PUT",
                "iam:ListRoles",
                "s3:GetBucketAcl",
                "s3:DeleteBucketPolicy",
                "s3:ListMultipartUploadParts",
                "s3:PutObject",
                "s3:GetObject",
                "transcribe:GetTranscriptionJob",
                "s3:ListAllMyBuckets",
                "lambda:*",
                "s3:PutBucketPolicy",
                "apigateway:POST"
            ],
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor2",
            "Effect": "Allow",
            "Action": "logs:CreateLogGroup",
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}

```



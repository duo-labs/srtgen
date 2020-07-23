## srtGen - Automatically generate .srt subtitle files

srtGen is a set of example scripts that makes it easier to use [AWS Transcribe](https://aws.amazon.com/transcribe/) to automatically generate subtitle files in `.srt` format from a video or audio source file.

There are two versions of srtGen, [standalone](https://github.com/MyNameIsMeerkat/srtGen/tree/master/standalone) and [service](https://github.com/MyNameIsMeerkat/srtGen/tree/master/service). The *standalone* example is good for developers or users who have their own AWS accounts and who can make authorized requests to AWS directly. The *service* example provides a layer of abstraction between the user and AWS in the form of an AWS lambda function, this means the end user needs no account or permissions for AWS beyond being able to contact the URL of the lambda function. The intent of the service mode example is for use cases such as organisations having an internal transcription service for their employees to use without needing any AWS privileges.

The srtGen project was initially developed to aid in the creation of subtitle files for security conference presentations that have a poor track record of making subtitles available, a blog post talking more about the project can be found [here](https://blog.duo.com/XXXTODOXXX).

We hope these examples prove useful in making subtitle files more widely available in the security community.

## Documentation

More detailed installation & configuration documentation for both srtGen standalone and service versions can be found in their respective sub directories.

## Test data

There is a small 30 second test file included with this project, it is from the open source movie [Tears of Steel](https://mango.blender.org/download/), the associated subtitle files that can be compared to your transcription output can be found [here](https://download.blender.org/demo/movies/ToS/subtitles/).

## Issues

Find a bug? Want more features? Find something missing in the documentation? Let us know! Please don't hesitate to [file an issue](https://github.com/duo-labs/srtGen/issues/new).

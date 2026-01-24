import os

# Configuration
STAC_URL = "https://explorer.digitalearth.africa/stac/search"

def setup_environment():
    """Sets up AWS environment variables for public bucket access."""
    os.environ['AWS_NO_SIGN_REQUEST'] = 'YES'
    os.environ['AWS_REGION'] = 'af-south-1'
    os.environ['AWS_S3_ENDPOINT'] = 's3.af-south-1.amazonaws.com'
    os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'

{
    "dev": {
        "app_function": "landcover.web.app",
        "aws_region": "us-east-1",
        "profile_name": "default",
        "project_name": "land-cover",
        "runtime": "python3.6",
        "s3_bucket": "zappa-marblecutter",
        "keep_warm": false,
        "memory_size": 3000,
        "aws_environment_variables": {
            "AWS_REQUEST_PAYER": "requester",
            "CPL_TMPDIR": "/tmp",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".vrt,.tif,.ovr,.msk",
            "GDAL_DATA": "/var/task/rasterio/gdal_data",
            "GDAL_DISABLE_READDIR_ON_OPEN": "TRUE",
            "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
            "GDAL_HTTP_VERSION": "2",
            "VSI_CACHE": "TRUE",
            "VSI_CACHE_SIZE": "536870912"
        }
    }
}
